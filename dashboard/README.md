# Gateway Dashboard

React/Vite UI for editing the LLM Gateway routing config.

## Setup

```sh
npm ci
```

## Development

Start the dashboard dev server:

```sh
npm run dev
```

The Vite dev server proxies `/config` requests to `http://localhost:8000`.
Run the gateway separately from `../gateway`.

## Checks

```sh
npm test
npm run lint
npm run build
```

The repository pre-commit hook runs `npm --prefix dashboard run lint` for dashboard
JavaScript and TypeScript changes.

## Config Reloads

The dashboard saves config changes to AWS Systems Manager Parameter Store through the
gateway API. The running gateway does not hot-reload config into its FastAPI context.
After saving, the API returns `reload_required: true` when the persisted config differs
from the active config. Apply the saved config by manually restarting the deployed
service, for example with `aws ecs update-service --force-new-deployment`.
