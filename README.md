# lambda_api

[![Tests](https://github.com/Team766/lambda_api/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/Team766/lambda_api/actions/workflows/tests.yml)

Minimal Python CLI + helpers for the **Lambda Cloud API** (https://cloud.lambda.ai/api/v1).

## Install

Using the workspace venv (recommended):

- `pip install -r requirements.txt`
- `pip install -e .`

## Auth

Set your API key:

- `export LAMBDA_API_KEY=...`

Or put it in a `.env` file in the project directory:

- create `.env` containing `LAMBDA_API_KEY=...`

The CLI will automatically load `.env` if present. You can also pass a specific file:

- `lambda-api --dotenv /path/to/.env instances list --json`

## Commands

### List running instances

- `lambda-api instances list --json`

### List available images

List machine images you can reference in your launch JSON:

- `lambda-api images list --json`

To launch using a specific image, set one of the following in your launch JSON:

- By id: `"image": {"id": "<IMAGE_ID>"}`
- By family: `"image": {"family": "<IMAGE_FAMILY>"}`

### Alert on instances running longer than 24 hours

Best-effort start time inference:

1. Prefer an instance tag containing an ISO8601 start time (default tag key: `started-at`).
2. Optionally fallback to scanning audit events (heuristic).

Example:

- `lambda-api instances long-running --hours 24 --fail-on-findings --fallback-audit-events`

Exit codes:
- `0`: ok (or findings but `--fail-on-findings` not set)
- `1`: findings present and `--fail-on-findings` set
- `2`: error talking to API / config error

## Discord bot integration (simple)

From a Discord bot, you can shell out and parse JSON:

- run `lambda-api instances long-running --hours 24 --json`
- if exit code is `1`, post an alert with the returned `long_running` list

## Notes on reliability

The Instances API responses shown in the public docs do **not** include a created/started timestamp.
If you need rock-solid “age” tracking, the most reliable approach is to ensure instances are launched with a tag like:

- key: `started-at`
- value: `2025-12-17T12:34:56Z`

This tool will use that tag when present.

### Launch (start) an instance

Launch a new instance using the Lambda Cloud launch endpoint.

This CLI requires a JSON file containing the request body for `POST /instance-operations/launch`.

Example `launch.json`:

```json
{
	"region_name": "us-west-2",
	"instance_type_name": "gpu_1x_a10",
	"ssh_key_names": ["my-ssh-key-name"],
	"quantity": 1
}
```

Run:

- `lambda-api instances launch launch.json --json`

Notes:
- The CLI automatically injects a `started-at` tag at launch time (unless you already provided one).
- Output is JSON (success envelope) and suitable for bot parsing.

### Shutdown (terminate) an instance

Terminate an instance by its id:

- `lambda-api instances shutdown <INSTANCE_ID> --json`
