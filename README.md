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

## Recurring diagnostic reports — proposed pilot

For an agency or business that wants someone to review the reports and organize the next actions, the proposed pilot is **$149 USD total per month**, including any applicable taxes and provider fees, for:

- Four reviews per monthly service period, covering up to 10 workflows on one instance.
- One prioritized monthly summary with evidence and recommended next actions.
- Up to 60 minutes of asynchronous technical triage per service period.

This is periodic review of metadata supplied by the client, not continuous monitoring. Changes, new builds, hosting, API usage and emergency support are outside the pilot. There is no automatic billing or renewal: each month requires a new acceptance. Cancellation can be requested at any time; future work and charges stop. Written seller identity, invoice arrangements, data handling, delivery dates and refund terms must be agreed before accepting payment. No paid service has launched and no customer results are claimed.

To express interest, [open a non-confidential inquiry](https://github.com/ImWalterGZ/n8n-metadata-audit/issues/new?template=service-inquiry.yml). Include only a rough workflow count and your general goal. A private communication channel will be agreed before discussing an actual system. Expressing interest creates no purchase commitment.

## Verify

```sh
python3 -m unittest discover -s tests -v
```

MIT licensed. Independent software; not affiliated with n8n GmbH. This repository contains original diagnostic code, not n8n software or customer workflows.
