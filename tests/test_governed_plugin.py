import importlib.util
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from swisstip.builder.autopilot.models import ApprovalGate, Proposal, ReviewMode, WorkflowState
from swisstip.builder.autopilot.service import AutopilotService
from swisstip.concepts.providers.config import load_config
from swisstip.core.acceptance import AcceptanceFile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "build-knowledge-base"


def load_script(name):
    path = SKILL / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"skill_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class GovernedPluginTests(unittest.TestCase):
    def test_governed_scaffold_creates_workflow_and_no_release_draft(self):
        scaffold = load_script("scaffold")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            original = __import__("sys").argv
            try:
                __import__("sys").argv = [
                    "scaffold.py", "--workspace", str(workspace), "--pack", "test-pack",
                    "--title", "Test pack", "--scope", "Self-employment in Zurich",
                    "--assistant-model", "claude-test-model",
                    "--frontier-model", "claude-review-model"]
                self.assertEqual(scaffold.main(), 0)
            finally:
                __import__("sys").argv = original
            workflow = AutopilotService(workspace, "test-pack").status()
            self.assertEqual(workflow.state, WorkflowState.DRAFTING_SCOPE)
            self.assertEqual(workflow.review_mode, ReviewMode.FULL_REVIEW)
            self.assertFalse((workspace / "releases" / "test-pack").exists())
            config = load_config(workspace / "config" / "semantic-models.toml")
            self.assertEqual(config["profiles"]["assistant_exchange"]["model"], "claude-test-model")
            self.assertEqual(config["profiles"]["frontier-review"]["adapter"], "exchange")
            self.assertEqual(config["profiles"]["frontier-review"]["model"], "claude-review-model")
            doctor = load_script("doctor")
            doctor.results.clear()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                doctor.check_pack(workspace, "test-pack")
            self.assertFalse(any(state == "MISSING" for state, _, _ in doctor.results))
            self.assertIn("governed drafts remain under .local", output.getvalue())

    def test_skill_contract_uses_current_paths_and_statuses(self):
        reader = (ROOT / "agents" / "kb-reader.md").read_text(encoding="utf-8")
        schema = (SKILL / "references" / "curation-schema.md").read_text(encoding="utf-8")
        self.assertIn("text/reading/<id>.md", reader)
        self.assertNotIn("text/documents/<id>.md", reader)
        self.assertIn("model-candidate-automated-review", schema)
        self.assertNotIn("| `model-candidate` |", schema)
        self.assertIn("coverage_policy: enforce", schema)
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("A3 has no promoted file", skill)

    def test_fast_track_scaffold_requires_a_distinct_frontier_model(self):
        scaffold = load_script("scaffold")
        for frontier in (None, "claude-test-model"):
            with self.subTest(frontier=frontier), tempfile.TemporaryDirectory() as directory:
                arguments = [
                    "scaffold.py", "--workspace", directory, "--pack", "test-pack",
                    "--title", "Test pack", "--scope", "A topic",
                    "--assistant-model", "claude-test-model", "--review-mode", "fast-track",
                    "--delegation-profile", "frontier-review",
                ]
                if frontier:
                    arguments.extend(["--frontier-model", frontier])
                original = __import__("sys").argv
                try:
                    __import__("sys").argv = arguments
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                        scaffold.main()
                finally:
                    __import__("sys").argv = original
                self.assertEqual(raised.exception.code, 2)

    def test_regression_template_cases_have_expected_answers_and_valid_decline_expectation(self):
        text = (SKILL / "templates" / "regression.yaml").read_text(encoding="utf-8")
        self.assertNotIn("expect_concept: null", text)
        self.assertEqual(text.count("expected_answer:"), 7)

    def test_acceptance_template_fields_match_current_model_names(self):
        text = (SKILL / "templates" / "acceptance.yaml").read_text(encoding="utf-8")
        for field in ("case_id:", "question:", "expected_answer:", "steps:"):
            self.assertIn(field, text)
        self.assertIn("schema_version: swiss-tip-acceptance/v1", text)

    def test_mock_demo_seeds_real_offline_workflow_scenes(self):
        demo = load_script("mock_demo")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "demo"
            packs = demo.seed(workspace)
            self.assertEqual(packs, ["demo-01-scope", "demo-02-catalogue",
                                     "demo-03-network", "demo-04-fast-track"])
            states = {pack: AutopilotService(workspace, pack).status() for pack in packs}
            self.assertEqual(states["demo-01-scope"].state, WorkflowState.AWAITING_SCOPE_APPROVAL)
            self.assertEqual(states["demo-02-catalogue"].state, WorkflowState.AWAITING_CATALOGUE_APPROVAL)
            self.assertEqual(states["demo-03-network"].state, WorkflowState.AWAITING_DOWNLOAD_CONFIRMATION)
            self.assertEqual(states["demo-04-fast-track"].state, WorkflowState.AWAITING_CATALOGUE_APPROVAL)
            service = AutopilotService(workspace, "demo-04-fast-track")
            proposal = Proposal.model_validate_json(service.store.read_artifact(
                states["demo-04-fast-track"].gates[ApprovalGate.CATALOGUE].proposal))
            self.assertEqual(proposal.delegation_uses[0].handling.value, "applied")
            self.assertFalse(any((workspace / "releases" / pack / "release.json").exists()
                                 for pack in packs))

    def test_mock_demo_serve_hands_off_to_real_console(self):
        demo = load_script("mock_demo")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "demo"
            with patch.object(demo, "seed", return_value=["demo-01-scope"]) as seed_mock, \
                    patch("swisstip.admin_console.app.main", return_value=0) as console_main, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = demo.main([
                    "--workspace", str(workspace), "--reset", "--serve", "--port", "8877",
                    "--actor", "Demo operator",
                ])
            self.assertEqual(result, 0)
            seed_mock.assert_called_once()
            self.assertEqual(seed_mock.call_args.args, (workspace, True))
            self.assertTrue(callable(seed_mock.call_args.kwargs["report"]))
            console_main.assert_called_once_with([
                "--packs-dir", str(workspace.resolve()), "--host", "127.0.0.1", "--port", "8877",
                "--actor", "Demo operator",
            ])

    def test_mock_claude_reacts_to_human_scope_approval(self):
        demo = load_script("mock_demo")
        mock_claude = load_script("mock_claude")
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "demo"
            demo.seed(workspace)
            service = AutopilotService(workspace, "demo-01-scope")
            pending = service.status()
            human = demo.Actor(kind=demo.ActorKind.HUMAN, actor_id="Demo reviewer",
                               authentication=demo.AuthenticationKind.LOCAL_ASSERTED)
            service.decide(ApprovalGate.SCOPE, demo.Decision.APPROVE,
                           pending.gates[ApprovalGate.SCOPE].proposal.sha256,
                           "Approved in test", human, pending.revision)

            self.assertTrue(mock_claude.advance_once(workspace, "demo-01-scope"))
            self.assertTrue(mock_claude.advance_once(workspace, "demo-01-scope"))

            workflow = service.status()
            self.assertEqual(workflow.state, WorkflowState.AWAITING_CATALOGUE_APPROVAL)
            self.assertEqual([event.kind for event in service.store.events()][-3:], [
                "proposal.approve", "proposal.promoted", "proposal.submitted",
            ])

            pending = service.status()
            service.decide(ApprovalGate.CATALOGUE, demo.Decision.APPROVE,
                           pending.gates[ApprovalGate.CATALOGUE].proposal.sha256,
                           "Official source boundary accepted", human, pending.revision)
            self.assertTrue(mock_claude.advance_once(workspace, "demo-01-scope"))
            self.assertTrue(mock_claude.advance_once(workspace, "demo-01-scope"))
            awaiting_network = service.status()
            self.assertEqual(awaiting_network.state, WorkflowState.AWAITING_DOWNLOAD_CONFIRMATION)
            self.assertTrue((workspace / ".local/demo-01-scope/plan.json").is_file())

            service.confirm_download(human, awaiting_network.revision)
            self.assertTrue(mock_claude.advance_once(workspace, "demo-01-scope"))
            self.assertTrue(mock_claude.advance_once(workspace, "demo-01-scope"))
            self.assertTrue(mock_claude.advance_once(workspace, "demo-01-scope"))

            pending_a3 = service.status()
            self.assertEqual(pending_a3.state, WorkflowState.AWAITING_EXCEPTION_APPROVAL)
            self.assertEqual([event.kind for event in service.store.events()][-4:], [
                "checkpoint.download-confirmation", "checkpoint.acquisition",
                "checkpoint.extraction", "proposal.submitted",
            ])
            text = workspace / ".local/demo-01-scope/text"
            index = json.loads((text / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index), 1)
            self.assertEqual(index[0]["status"], "extracted")
            summary = json.loads((workspace / ".local/demo-01-scope/summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["network_usage"], {"charged_requests": 0, "charged_bytes": 0})

    def test_mock_claude_refuses_an_unmarked_workspace(self):
        mock_claude = load_script("mock_claude")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "unmarked directory"):
                mock_claude.require_mock_workspace(Path(directory))

    def test_real_discovery_demo_builds_a_bounded_valid_catalogue(self):
        discovery = load_script("real_discovery_demo")
        child_urls = {
            "ch-sem-residence":
                "https://www.sem.admin.ch/sem/de/home/themen/aufenthalt/eu_efta.html",
            "zh-residence":
                "https://www.zh.ch/de/migration-integration/aufenthalt/aufenthalt-fuer-euefta-staatsangehoerige.html",
            "zurich-city-arrival":
                "https://www.stadt-zuerich.ch/de/lebenslagen/einwohner-services/umziehen-melden/wegzug.html",
        }
        results = []
        for seed in discovery.SEEDS:
            results.append({
                "seed": seed,
                "saved": [
                    {"final_url": seed["url"], "title": seed["title"], "depth": 0,
                     "response": f"discovery/{seed['source_id']}/seed.html"},
                    {"final_url": child_urls[seed["source_id"]], "title": "Relevant child page",
                     "depth": 1, "response": f"discovery/{seed['source_id']}/child.html"},
                ],
                "report": {"stop_reason": "frontier-exhausted"},
            })

        selected = discovery.select_pages(results)

        self.assertEqual(len(selected), 6)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            catalogue, inventory, _ = discovery.write_catalogue_drafts(
                workspace, discovery.DEFAULT_PACK, selected, results)
            plan = discovery.build_plan(catalogue, inventory, scan_set=None,
                                        source_ids=None, workers=1)
        self.assertEqual(len(plan["targets"]), 6)
        self.assertEqual({__import__("urllib.parse").parse.urlsplit(item["url"]).hostname
                          for item in plan["targets"]},
                         {"www.sem.admin.ch", "www.zh.ch", "www.stadt-zuerich.ch"})
        self.assertTrue(all(item["allowed_path_prefixes"] for item in plan["targets"]))


if __name__ == "__main__":
    unittest.main()
