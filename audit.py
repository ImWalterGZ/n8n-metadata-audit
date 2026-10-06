#!/usr/bin/env python3
"""Offline n8n metadata diagnostics. No credentials, network, or workflow execution."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import sys


def parse_time(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, dict) and "id" in payload:
        return [payload]
    raise ValueError("Expected an array, an API data array, or a single workflow export.")


def normalize_workflow(w):
    """Allowlist metadata; discard credentials, parameters, pinData and connections."""
    if not isinstance(w, dict) or not w.get("id"):
        raise ValueError("Every workflow needs an id.")
    nodes = w.get("nodes")
    inspected = bool(w.get("inspected")) or isinstance(nodes, list)
    result = {"id": str(w["id"]), "name": str(w.get("name") or w["id"]),
              "active": w.get("active") if isinstance(w.get("active"), bool) else None,
              "inspected": inspected}
    if inspected:
        settings = w.get("settings") or {}
        result["error_workflow"] = w.get("error_workflow", settings.get("errorWorkflow"))
        if result["error_workflow"] is not None:
            result["error_workflow"] = str(result["error_workflow"])
        result["has_error_trigger"] = w.get("has_error_trigger", any(
            n.get("type") == "n8n-nodes-base.errorTrigger" and not n.get("disabled")
            for n in (nodes or [])))
        result["continues_on_error_count"] = len(w.get("continues_on_error", [])) if nodes is None else sum(
            n.get("onError") == "continueRegularOutput" and not n.get("disabled") for n in nodes)
    elif "has_error_trigger" in w:
        result["has_error_trigger"] = w["has_error_trigger"]
    return result


def normalize_execution(e):
    if not isinstance(e, dict) or not e.get("id"):
        raise ValueError("Every execution needs an id.")
    workflow = e.get("workflow_id", e.get("workflowId"))
    if workflow is None:
        raise ValueError("Every execution needs a workflow id.")
    return {"id": str(e["id"]), "workflow_id": str(workflow),
            "status": str(e.get("status") or "unknown"),
            "started_at": e.get("started_at", e.get("startedAt")),
            "stopped_at": e.get("stopped_at", e.get("stoppedAt"))}


def diagnose(snapshot):
    workflows = [normalize_workflow(w) for w in snapshot.get("workflows", [])]
    if len({w["id"] for w in workflows}) != len(workflows):
        raise ValueError("Duplicate workflow IDs make inventory ambiguous.")
    inventory = {w["id"]: w for w in workflows}
    execution_map = {}
    for e in snapshot.get("executions", []):
        row = normalize_execution(e)
        if row["id"] in execution_map and execution_map[row["id"]] != row:
            raise ValueError("Conflicting duplicate execution IDs.")
        execution_map[row["id"]] = row
    executions = list(execution_map.values())
    coverage = snapshot.get("coverage", {})
    start = parse_time(coverage.get("error_window_start"))
    cutoff = parse_time(snapshot.get("captured_at"))
    findings = []

    def add(code, w, text, level="review"):
        findings.append({"code": code, "level": level, "workflow_id": w["id"],
                         "workflow_name": w["name"], "description": text})

    for w in workflows:
        if w["active"] is not True or not w["inspected"]:
            continue
        handler = w.get("error_workflow")
        if not handler and not w.get("has_error_trigger"):
            add("NO_ERROR_WORKFLOW", w, "No designated error workflow or enabled local Error Trigger was found. Check other alert mechanisms before changing anything.")
        if handler and handler not in inventory:
            add("HANDLER_NOT_IN_INVENTORY", w, "The designated error workflow is absent from this inventory; verify access and inventory completeness.")
        elif handler and inventory[handler].get("has_error_trigger") is False:
            add("HANDLER_WITHOUT_TRIGGER", w, "The inspected error workflow has no enabled Error Trigger.")
        if w.get("continues_on_error_count", 0):
            add("CONTINUES_AFTER_ERROR", w, f"{w['continues_on_error_count']} enabled node(s) continue on the regular output after an error. A success status alone does not establish business success.")
        # An inactive error workflow can still handle errors. Do not flag active=false.

    failures = Counter()
    missing_times = 0
    for e in executions:
        if e["status"] not in {"error", "crashed"}:
            continue
        when = parse_time(e["started_at"])
        if not when:
            missing_times += 1
            continue
        if (start and when < start) or (cutoff and when > cutoff):
            continue
        failures[e["workflow_id"]] += 1
    for workflow_id, count in sorted(failures.items()):
        w = inventory.get(workflow_id, {"id": workflow_id, "name": workflow_id})
        add("OBSERVED_FAILURES", w, f"{count} retained failed execution(s) observed in the supplied window. This is an observed count, not a failure rate.", "observed")
    complete = bool(coverage.get("error_window_complete")) and start is not None and cutoff is not None and missing_times == 0
    reported_count = coverage.get("error_count")
    if reported_count is not None and sum(failures.values()) != reported_count:
        complete = False
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "synthetic_demo": snapshot.get("synthetic_demo") is True,
            "captured_at": snapshot.get("captured_at"),
            "summary": {"workflow_count": len(workflows),
                        "active_workflow_count": sum(w["active"] is True for w in workflows),
                        "unknown_active_count": sum(w["active"] is None for w in workflows),
                        "inspected_active_count": sum(w["active"] is True and w["inspected"] for w in workflows),
                        "observed_failed_execution_count": sum(failures.values()),
                        "execution_metadata_count": len(executions),
                        "failure_window_complete": complete,
                        "workflow_inventory_complete": bool(coverage.get("workflow_inventory_complete"))},
            "window_start": coverage.get("error_window_start"), "findings": findings,
            "limitations": ["Only supplied metadata was examined; no workflow was executed or changed.",
                            "Retained execution history may omit pruned records or unsaved failures.",
                            "No uptime, business outcome, alert delivery, or failure rate is inferred.",
                            "Error workflow activation alone does not establish whether error handling works.",
                            "No schedule freshness check is made without a client-approved schedule contract."]}


def render_html(report):
    esc = lambda value: escape(str(value), quote=True)
    cards = "".join(f'<div class="stat"><strong>{esc(v)}</strong><span>{esc(k.replace("_", " "))}</span></div>'
                    for k, v in report["summary"].items() if k in {"workflow_count", "active_workflow_count", "inspected_active_count", "observed_failed_execution_count"})
    findings = "".join(f'<tr><td>{esc(f["level"])}</td><td>{esc(f["workflow_name"])}</td><td>{esc(f["description"])}</td></tr>' for f in report["findings"])
    limits = "".join(f"<li>{esc(v)}</li>" for v in report["limitations"])
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>n8n Metadata Audit</title>
<style>body{{font:17px/1.6 system-ui,sans-serif;background:#101719;color:#e5eeee;margin:0}}main{{max-width:1100px;margin:auto;padding:48px 24px}}h1{{font-size:clamp(32px,6vw,62px);line-height:1.1}}small,.muted{{color:#b3c1c1}}.stats{{display:flex;flex-wrap:wrap;gap:12px;margin:30px 0}}.stat{{background:#203033;border-radius:10px;padding:18px;min-width:170px;flex:1}}.stat strong{{display:block;font-size:38px;color:#b4f5cc}}.stat span{{font-size:14px}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;vertical-align:top;padding:14px 10px;border-bottom:1px solid #3b4c4e}}.table{{overflow:auto}}td:first-child{{color:#b4f5cc}}@media(max-width:600px){{main{{padding:28px 16px}}table{{min-width:650px}}}}</style>
<main><small>OFFLINE DIAGNOSTIC · METADATA ONLY</small>{'<p><strong>SYNTHETIC DEMO — fictional workflows and executions.</strong></p>' if report.get('synthetic_demo') else ''}<h1>Know what needs<br>your attention.</h1><p class="muted">Snapshot: {esc(report.get('captured_at') or 'not supplied')}<br>Observed failures from: {esc(report.get('window_start') or 'supplied history; start unspecified')}</p><div class="stats">{cards}</div>
<p>Error window complete in supplied evidence: <strong>{esc(report['summary']['failure_window_complete'])}</strong>. Counts do not measure uptime.</p><div class="table"><table><thead><tr><th>Evidence</th><th>Workflow</th><th>Finding</th></tr></thead><tbody>{findings or '<tr><td colspan="3">No findings from supplied metadata. This does not prove system health.</td></tr>'}</tbody></table></div><h2>Scope of this report</h2><ul>{limits}</ul><p class="muted">Independent tool. Not affiliated with n8n GmbH. Report may contain private workflow names; share intentionally.</p></main></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--snapshot", type=Path, help="Normalized metadata snapshot")
    inputs.add_argument("--workflows", type=Path, help="n8n workflow export or API response")
    parser.add_argument("--executions", type=Path, help="Optional execution metadata JSON")
    parser.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args(argv)
    try:
        if args.snapshot:
            snapshot = json.loads(args.snapshot.read_text())
        else:
            snapshot = {"captured_at": datetime.now(timezone.utc).isoformat(), "workflows": rows(json.loads(args.workflows.read_text())), "executions": [], "coverage": {}}
        if args.executions:
            snapshot["executions"] = rows(json.loads(args.executions.read_text()))
            snapshot.setdefault("coverage", {})["error_window_complete"] = False
        report = diagnose(snapshot)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
        (args.output / "audit.html").write_text(render_html(report))
        print(json.dumps(report["summary"]))
        print(f"Report: {args.output.resolve() / 'audit.html'}")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"Audit could not complete ({type(error).__name__}). Check input structure and file permissions.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
