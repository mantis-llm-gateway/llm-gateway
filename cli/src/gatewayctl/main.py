from __future__ import annotations

import configparser
import ipaddress
import os
import re
import subprocess
from pathlib import Path
from textwrap import dedent
from typing import Any

import typer

app = typer.Typer(
    help="Deploy and operate the Mantis gateway.",
    no_args_is_help=False,
)

AWS_PROFILE = "gw"
AWS_REGION = "us-east-1"
ROOT_HINT = "Make sure you are running this CLI tool from the root of the Mantis gateway repo."
VALID_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,20}$")
VALID_TOKEN_ID_RE = re.compile(r"^[a-zA-Z0-9-]{1,64}$")


@app.command()
def deploy() -> None:
    render_ascii_mantis()
    typer.echo("Make sure to run this CLI tool from the root of the Mantis gateway repo.")
    check_gw_profile()

    root_dir = Path.cwd()
    infra_dir = root_dir / "infra"
    tfvars_path = infra_dir / "terraform.tfvars"
    bootstrap_script = root_dir / "scripts" / "bootstrap_state_bucket.sh"
    setup_auth_script = root_dir / "scripts" / "setup_auth.sh"
    deploy_script = root_dir / "scripts" / "deploy.sh"

    namespace = prompt_required_name("AWS namespace")
    run_script([str(bootstrap_script), namespace], root_dir, root_hint=True)
    typer.echo(
        "\nReminder: restrict access to the bootstrapped state bucket using bucket policies "
        "or IAM roles."
    )
    run_terraform_init(namespace, root_dir)

    owner = prompt_required_name("AWS owner")
    cache_auth_token = generate_cache_auth_token()
    tfvars = collect_tfvars(owner, namespace, cache_auth_token)
    write_tfvars(tfvars_path, tfvars)
    api_token_id = prompt_required_token_id("API token ID")
    typer.echo(
        "\nCreating gateway authentication parameters in SSM. Store the printed API token; "
        "it will not be shown again."
    )
    run_script(
        [
            str(setup_auth_script),
            namespace,
            "--profile",
            AWS_PROFILE,
            "--region",
            AWS_REGION,
            "--token-id",
            api_token_id,
        ],
        root_dir,
        root_hint=True,
    )

    terraform_apply = run_command(
        ["terraform", "-chdir=infra", "apply"],
        root_dir,
        root_hint=True,
    )
    if terraform_apply.returncode != 0:
        typer.echo(ROOT_HINT, err=True)
        raise typer.Exit(terraform_apply.returncode)

    wait_for_docker_daemon()
    run_script([str(deploy_script)], root_dir, root_hint=False)

    terraform_output = run_command(
        ["terraform", "-chdir=infra", "output"],
        root_dir,
        root_hint=True,
    )
    if terraform_output.returncode != 0:
        raise typer.Exit(terraform_output.returncode)

    typer.echo(
        "\nTo destroy all Terraform-managed infrastructure from your environment, run "
        "`terraform -chdir=infra destroy` from the root of this Mantis gateway."
    )


def render_ascii_mantis() -> None:
    art = dedent(
        r"""                                     _                _
                                      '-.          ,-'
                                         '.      ,'
                                           \    /
                                           _|__|_
                                          (,\--/,)
                                          /\Y  Y/
                                        ."  `><'
                                      ."    /|
                                     /  /  // .-"'y".
                                  _."  /  // / -//-//
                               _."l   /| || / ,// //
                            _."  / ',/ | |," ,// //
                .-.      _."   ."  ."  | `  ,//-//
               //'.'. _."   _."/ |/    "._."// //
              //  _\ \  _,-" _|  Y          ^  ^
             //_."  \'\" /  / \  \._
            //"    _.\ \|  /   "----|====-.
         _.//   _." \_\___/        ||     \\
      .-" //_.-" \_."              ||      \\
   _."   //" \__,"                 ||       \\
 ."   __//>.-"                     ||        "----
"---"" //                           \           mozz
------------------------------------------------
        """
    ).strip("\n")
    typer.echo(art)


def check_gw_profile() -> None:
    credentials_path = Path.home() / ".aws" / "credentials"
    parser = configparser.RawConfigParser()
    parser.read(credentials_path)

    has_profile = parser.has_section(AWS_PROFILE)
    has_access_key = has_profile and bool(
        parser.get(AWS_PROFILE, "aws_access_key_id", fallback="").strip()
    )
    has_secret_key = has_profile and bool(
        parser.get(AWS_PROFILE, "aws_secret_access_key", fallback="").strip()
    )

    if has_access_key and has_secret_key:
        return

    typer.echo(
        "There is no `gw` profile in your AWS credentials file. An AWS profile is a "
        "named set of credentials stored locally on your machine. Create your `gw` "
        "profile using this command and then run this tool again:\n"
        "```sh\n"
        "aws configure --profile gw\n"
        "```"
    )
    raise typer.Exit(1)


def prompt_required_name(name: str) -> str:
    while True:
        value = typer.prompt(f"Enter {name}").strip()
        if VALID_NAME_RE.fullmatch(value):
            return value
        typer.echo(
            f"{name} must be 2-21 chars: lowercase letters, numbers, hyphens; start with a letter."
        )


def prompt_required_token_id(name: str) -> str:
    while True:
        value = typer.prompt(f"Enter {name}").strip()
        if VALID_TOKEN_ID_RE.fullmatch(value):
            return value
        typer.echo(f"{name} must be 1-64 chars: letters, numbers, or hyphens.")


def generate_cache_auth_token() -> str:
    result = subprocess.run(
        ["openssl", "rand", "-hex", "32"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        typer.echo(result.stderr, err=True)
        raise typer.Exit(result.returncode)
    return result.stdout.strip()


def wait_for_docker_daemon() -> None:
    while True:
        try:
            result = subprocess.run(
                ["docker", "info"],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            typer.echo(
                "Docker is required to build and push the gateway image. Install Docker "
                "and run this tool again.",
                err=True,
            )
            raise typer.Exit(1) from exc

        if result.returncode == 0:
            return

        typer.echo(
            "\nDocker is not running or this shell cannot access it. Start Docker, then "
            "press Enter to continue."
        )
        typer.prompt("Press Enter when Docker is ready", default="", show_default=False)


def show_https_readme_instructions() -> None:
    typer.echo(
        "\nThe below options are related to HTTPS."
        " To configure HTTPS and Cloudflare DNS, follow the instructions under the"
        '" Configure HTTPS and Cloudflare DNS" section in the README.\n'
    )


def collect_tfvars(owner: str, namespace: str, cache_auth_token: str) -> dict[str, Any]:
    tfvars: dict[str, Any] = {
        "owner": owner,
        "namespace": namespace,
        "cache_auth_token": cache_auth_token,
        "aws_region": AWS_REGION,
        "aws_profile": AWS_PROFILE,
    }

    optional_values = {
        "ecs_desired_count": prompt_optional_number("ecs_desired_count", 0),
        "container_image_tag": prompt_optional_string("container_image_tag", "latest"),
        "log_retention_days": prompt_optional_number("log_retention_days", 14),
        "cache_node_type": prompt_optional_string("cache_node_type", "cache.t4g.micro"),
        "allowed_http_cidrs": prompt_allowed_http_cidrs(),
    }
    show_https_readme_instructions()
    optional_values.update(
        {
            "enable_https": prompt_optional_bool(
                "enable_https",
                False,
            ),
            "acm_certificate_arn": prompt_optional_nullable_string(
                "acm_certificate_arn",
            ),
            "gateway_domain_name": prompt_optional_nullable_string(
                "gateway_domain_name",
            ),
        }
    )

    for key, value in optional_values.items():
        if value is not None:
            tfvars[key] = value

    return tfvars


def prompt_optional_string(name: str, default: str) -> str | None:
    value = typer.prompt(
        f'{name}. Press enter to save default value "{default}"',
        default="",
        show_default=False,
    ).strip()
    return value or None


def prompt_optional_nullable_string(name: str) -> str | None:
    value = typer.prompt(
        f'{name}. Press enter to save default value "null',
        default="",
        show_default=False,
    ).strip()
    return value or None


def prompt_optional_number(name: str, default: int) -> int | None:
    while True:
        value = typer.prompt(
            f'{name}. Press enter to save default value "{default}"',
            default="",
            show_default=False,
        ).strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            typer.echo(f"{name} must be a whole number.")


def prompt_optional_bool(name: str, default: bool) -> bool | None:
    default_text = str(default).lower()
    while True:
        value = (
            typer.prompt(
                f'{name}. Press enter to save default value "{default_text}"',
                default="",
                show_default=False,
            )
            .strip()
            .lower()
        )
        if not value:
            return None
        if value in {"true", "t", "yes", "y", "1"}:
            return True
        if value in {"false", "f", "no", "n", "0"}:
            return False
        typer.echo(f'{name} must be "true" or "false".')


def prompt_allowed_http_cidrs() -> list[str] | None:
    while True:
        value = typer.prompt(
            'allowed_http_cidrs. Press enter to save default value ["0.0.0.0/0"]. '
            "Using this default value makes the Mantis gateway accessible to the entire internet",
            default="",
            show_default=False,
        ).strip()
        if not value:
            return None
        cidrs = parse_allowed_http_cidrs(value)
        invalid_cidrs = [cidr for cidr in cidrs if not is_valid_ipv4_cidr(cidr)]
        if invalid_cidrs:
            typer.echo(
                "allowed_http_cidrs contains invalid IPv4 CIDR values: " + ", ".join(invalid_cidrs)
            )
            continue
        if cidrs:
            return cidrs
        typer.echo("allowed_http_cidrs must include at least one CIDR value.")


def parse_allowed_http_cidrs(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [cidr.strip().strip("\"'") for cidr in value.split(",") if cidr.strip()]


def is_valid_ipv4_cidr(cidr: str) -> bool:
    try:
        ipaddress.IPv4Network(cidr)
    except ValueError:
        return False
    return True


def write_tfvars(path: Path, values: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key} = {format_hcl_value(value)}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    typer.echo(f"\nWrote Terraform values to {path}.")


def format_hcl_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(format_hcl_value(item) for item in value) + "]"
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def command_env() -> dict[str, str]:
    return {
        **os.environ,
        "AWS_PROFILE": AWS_PROFILE,
        "AWS_REGION": AWS_REGION,
    }


def run_script(command: list[str], cwd: Path, root_hint: bool) -> None:
    try:
        result = subprocess.run(command, cwd=cwd, env=command_env())
    except FileNotFoundError as exc:
        if root_hint:
            typer.echo(ROOT_HINT, err=True)
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if result.returncode == 0:
        return
    if root_hint:
        typer.echo(ROOT_HINT, err=True)
    raise typer.Exit(result.returncode)


def run_command(
    command: list[str],
    cwd: Path,
    root_hint: bool,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, env=command_env(), text=True)
    except FileNotFoundError as exc:
        if root_hint:
            typer.echo(ROOT_HINT, err=True)
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def run_terraform_init(namespace: str, root_dir: Path) -> None:
    try:
        account_id_result = subprocess.run(
            [
                "aws",
                "--profile",
                AWS_PROFILE,
                "--region",
                AWS_REGION,
                "sts",
                "get-caller-identity",
                "--query",
                "Account",
                "--output",
                "text",
            ],
            cwd=root_dir,
            env=command_env(),
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if account_id_result.returncode != 0:
        typer.echo(account_id_result.stderr, err=True)
        raise typer.Exit(account_id_result.returncode)

    account_id = account_id_result.stdout.strip()
    bucket_name = f"gw-{namespace}-{account_id}-{AWS_REGION}-terraform-state"
    command = [
        "terraform",
        "-chdir=infra",
        "init",
        "-migrate-state",
        f"-backend-config=bucket={bucket_name}",
        f"-backend-config=key={namespace}/terraform.tfstate",
        f"-backend-config=region={AWS_REGION}",
        f"-backend-config=profile={AWS_PROFILE}",
        "-backend-config=encrypt=true",
        "-backend-config=use_lockfile=true",
    ]
    result = run_command(command, root_dir, root_hint=True)
    if result.returncode != 0:
        typer.echo(ROOT_HINT, err=True)
        raise typer.Exit(result.returncode)


@app.callback(invoke_without_command=True)
def app_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        deploy()
