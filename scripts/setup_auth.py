#!/usr/bin/env python3
import argparse
import getpass
import json
import re
import secrets
import shutil
import subprocess
import sys

from gateway.auth import hash_api_token_secret, hash_dashboard_password

TOKEN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9-]{1,64}$")
NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,20}$")


def _aws_command(profile: str, region: str, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["aws", "--profile", profile, "--region", region, *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "AWS CLI command failed")
    return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()


def _get_api_token_hashes(
    profile: str, region: str, parameter_name: str
) -> dict[str, str]:
    result = _aws_command(
        profile,
        region,
        "ssm",
        "get-parameter",
        "--name",
        parameter_name,
        "--with-decryption",
        "--query",
        "Parameter.Value",
        "--output",
        "text",
        check=False,
    )
    if "ParameterNotFound" in result:
        return {}
    if not result.startswith("{"):
        raise RuntimeError(result)

    try:
        token_hashes = json.loads(result)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{parameter_name} does not contain valid JSON") from exc
    if not isinstance(token_hashes, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in token_hashes.items()
    ):
        raise RuntimeError(
            f"{parameter_name} must contain a JSON object of token hashes"
        )
    return token_hashes


def _put_parameter(
    profile: str, region: str, name: str, value: str, type_: str
) -> None:
    _aws_command(
        profile,
        region,
        "ssm",
        "put-parameter",
        "--name",
        name,
        "--type",
        type_,
        "--value",
        value,
        "--overwrite",
    )


def _dashboard_password() -> str:
    password = getpass.getpass("Dashboard password: ")
    if not password:
        raise RuntimeError("dashboard password must not be empty")
    if password != getpass.getpass("Confirm dashboard password: "):
        raise RuntimeError("dashboard passwords did not match")
    return password


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or rotate the gateway API token and dashboard credentials in SSM."
    )
    parser.add_argument(
        "namespace", help="Gateway deployment namespace, such as dev or staging"
    )
    parser.add_argument("--profile", default="gw", help="AWS CLI profile (default: gw)")
    parser.add_argument(
        "--region", default="us-east-1", help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--token-id", default=None, help="Stable API token ID shown in logs"
    )
    parser.add_argument("--dashboard-username", default="admin")
    parser.add_argument(
        "--skip-dashboard-password",
        action="store_true",
        help="Preserve the existing dashboard username and password hash",
    )
    parser.add_argument(
        "--replace-api-tokens",
        action="store_true",
        help="Remove existing API token hashes instead of adding a token for staged rotation",
    )
    args = parser.parse_args()

    if shutil.which("aws") is None:
        raise RuntimeError("aws CLI is required")
    if not NAMESPACE_PATTERN.fullmatch(args.namespace):
        raise RuntimeError(
            "namespace must be 2-21 chars: lowercase letters, numbers, hyphens; start with a letter"
        )
    if not args.dashboard_username:
        raise RuntimeError("dashboard username must not be empty")

    token_id = args.token_id or secrets.token_hex(8)
    if not TOKEN_ID_PATTERN.fullmatch(token_id):
        raise RuntimeError("token ID must contain 1-64 letters, numbers, or hyphens")

    parameter_prefix = f"/gw-{args.namespace}/auth"
    token_hashes_parameter = f"{parameter_prefix}/api-token-hashes"
    dashboard_password_hash = (
        None
        if args.skip_dashboard_password
        else hash_dashboard_password(_dashboard_password())
    )
    token_secret = secrets.token_urlsafe(32)
    token_hashes = (
        {}
        if args.replace_api_tokens
        else _get_api_token_hashes(args.profile, args.region, token_hashes_parameter)
    )
    token_hashes[token_id] = hash_api_token_secret(token_secret)

    if dashboard_password_hash is not None:
        _put_parameter(
            args.profile,
            args.region,
            f"{parameter_prefix}/dashboard-username",
            args.dashboard_username,
            "String",
        )
        _put_parameter(
            args.profile,
            args.region,
            f"{parameter_prefix}/dashboard-password-hash",
            dashboard_password_hash,
            "SecureString",
        )

    _put_parameter(
        args.profile,
        args.region,
        token_hashes_parameter,
        json.dumps(token_hashes, sort_keys=True, separators=(",", ":")),
        "SecureString",
    )

    print("Authentication parameters updated.")
    print("Store this API token now; it will not be shown again:")
    print(f"gw_{token_id}_{token_secret}")
    print("Force a new ECS deployment to load the updated values.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
