# n8n Metadata Audit

Turn an n8n workflow export and execution metadata into a readable diagnostic report. Runs offline, with Python's standard library only.

**No API keys. No network calls. No workflow execution or modification.**

## Try the synthetic demo

Python 3.10 or newer:

```sh
python3 audit.py --snapshot demo/snapshot.json --output reports/demo
```

Open `reports/demo/audit.html`. Every name and execution in the demo is fictional.

## Audit your own exports locally

```sh
python3 audit.py --workflows /path/to/workflows.json --output reports/local
```

Optionally include execution metadata:

```sh
python3 audit.py --workflows /path/to/workflows.json --executions /path/to/executions.json --output reports/local
```

Workflow input can be an n8n export array, one exported workflow, or an API response containing a `data` array. Execution input accepts an array or an API `data` array. Only execution ID, workflow ID, status and timestamps are used. The tool ignores credential references, node parameters, connection graphs, pinned data and execution payloads in its output. It does **not** sanitize the original input file: keep that file private.

The output includes:

- Retained failed executions observed in the supplied time window.
- Inspected active workflows without a designated error workflow or enabled local Error Trigger.
- Referenced error handlers absent from the supplied inventory.
- Inspected handlers without an enabled Error Trigger.
- Nodes configured to continue through the regular output after an error.
- Explicit limits on inventory and execution-history coverage.

These are diagnostic findings for review. Other alerting mechanisms may exist. An inactive error handler is not automatically treated as broken. The tool does not infer uptime, business success, failure rates or schedule freshness. A blank report is not proof of health.

Reports retain workflow names and IDs, so they can still contain confidential metadata. Run locally and share intentionally. Do not upload workflow exports, API keys, customer information or execution payloads to GitHub issues.

## Commercial service status

The original proposed diagnostic-report pilot has been withdrawn. This tool remains free under the MIT license. No paid service has launched and no customer results are claimed.

For a non-confidential inquiry about a specific automation problem, use the repository issue form. Do not upload workflow exports, credentials, customer information or execution payloads. Scope and commercial terms would need to be agreed separately before any paid work.

## Verify

```sh
python3 -m unittest discover -s tests -v
```

MIT licensed. Independent software; not affiliated with n8n GmbH. This repository contains original diagnostic code, not n8n software or customer workflows.
