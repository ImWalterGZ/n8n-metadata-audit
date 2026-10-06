import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit import diagnose, normalize_workflow, render_html


class AuditTests(unittest.TestCase):
    def snapshot(self):
        return json.loads((Path(__file__).resolve().parents[1] / "demo/snapshot.json").read_text())

    def test_demo_findings_and_inactive_handler(self):
        r = diagnose(self.snapshot())
        self.assertEqual(r["summary"]["observed_failed_execution_count"], 1)
        self.assertTrue(r["synthetic_demo"])
        self.assertIn("SYNTHETIC DEMO", render_html(r))
        self.assertTrue(r["summary"]["failure_window_complete"])
        self.assertEqual({f["code"] for f in r["findings"]}, {"OBSERVED_FAILURES", "NO_ERROR_WORKFLOW", "CONTINUES_AFTER_ERROR"})
        self.assertFalse(any(f["workflow_id"] == "demo-orders" and f["code"] != "OBSERVED_FAILURES" for f in r["findings"]))

    def test_no_credentials_or_node_payloads_in_reports(self):
        s = self.snapshot()
        s["workflows"][0]["credentials"] = {"token": "DO_NOT_LEAK"}
        s["workflows"][0]["nodes"] = [{"type": "http", "parameters": {"password": "DO_NOT_LEAK"}}]
        s["executions"][0]["data"] = {"customer_phone": "DO_NOT_LEAK"}
        r = diagnose(s)
        self.assertNotIn("DO_NOT_LEAK", json.dumps(r) + render_html(r))

    def test_html_escapes_workflow_names(self):
        s = self.snapshot()
        s["workflows"][0]["name"] = '<script>alert("x")</script>'
        html = render_html(diagnose(s))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_duplicate_executions_are_counted_once(self):
        s = self.snapshot()
        s["executions"].append(s["executions"][0].copy())
        self.assertEqual(diagnose(s)["summary"]["observed_failed_execution_count"], 1)

    def test_partial_history_is_not_complete(self):
        s = self.snapshot()
        s["coverage"]["error_window_complete"] = False
        self.assertFalse(diagnose(s)["summary"]["failure_window_complete"])

    def test_missing_or_outside_timestamp_not_counted_as_window_failure(self):
        s = self.snapshot()
        s["executions"][0]["started_at"] = "2026-09-01T00:00:00Z"
        self.assertEqual(diagnose(s)["summary"]["observed_failed_execution_count"], 0)
        self.assertFalse(diagnose(s)["summary"]["failure_window_complete"])
        s["executions"][0]["started_at"] = None
        self.assertFalse(diagnose(s)["summary"]["failure_window_complete"])

    def test_unknown_workflows_not_accused_of_missing_handler(self):
        s = self.snapshot()
        s["workflows"] = [{"id": "unknown", "name": "Unknown", "active": True}]
        self.assertFalse(any(f["code"] == "NO_ERROR_WORKFLOW" for f in diagnose(s)["findings"]))

    def test_duplicate_inventory_rejected(self):
        s = self.snapshot()
        s["workflows"].append(s["workflows"][0].copy())
        with self.assertRaises(ValueError):
            diagnose(s)

    def test_export_parameters_discarded(self):
        w = normalize_workflow({"id": "1", "nodes": [], "pinData": {"secret": "LEAK"}})
        self.assertNotIn("pinData", w)


if __name__ == "__main__":
    unittest.main()
