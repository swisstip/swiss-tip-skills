"""Run an offline mock coordinator against a seeded Swiss TIP demo workspace.

This process makes no network or model calls. It watches for human decisions made in
the real admin console, then performs the coordinator-owned workflow transitions with
the real AutopilotService so the screen updates automatically.
"""

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

if __name__ == "__main__":
    print("Loading the real offline workflow engine for MOCK CLAUDE...", flush=True)

from swisstip.builder.autopilot.models import (
    Actor, ActorKind, ApprovalGate, AuthenticationKind, GateStatus, WorkflowState,
)
from swisstip.builder.autopilot.service import AutopilotService
from swisstip.builder.autopilot.store import WorkflowConflict
from swisstip.extraction.extract_cli import run_extraction
from swisstip.ingestion import gap_report
from swisstip.ingestion.download_cli import build_plan

from mock_demo import MARKER, submit_catalogue, write_json

MOCK_COORDINATOR = Actor(
    kind=ActorKind.COORDINATOR,
    actor_id="mock-claude-coordinator",
    authentication=AuthenticationKind.LOCAL_ASSERTED,
)


def say(message: str) -> None:
    timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
    print(f"[{timestamp}] MOCK CLAUDE: {message}", flush=True)


def require_mock_workspace(workspace: Path) -> Path:
    workspace = workspace.resolve()
    marker = workspace / MARKER
    if not marker.is_file():
        raise ValueError(f"refusing to coordinate unmarked directory {workspace}")
    data = json.loads(marker.read_text(encoding="utf-8"))
    if data.get("schema_version") != "swisstip.mock-demo/v1":
        raise ValueError(f"unsupported mock workspace marker in {workspace}")
    return workspace


def was_promoted(service: AutopilotService, gate: ApprovalGate) -> bool:
    return any(event.kind == "proposal.promoted" and event.gate == gate
               for event in service.store.events())


def has_event(service: AutopilotService, kind: str) -> bool:
    return any(event.kind == kind for event in service.store.events())


def write_mock_acquisition(workspace: Path, pack: str) -> None:
    run = workspace / ".local" / pack
    plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    retrieved_at = datetime.now(UTC).isoformat()
    results = []
    saved_bytes = 0
    for target in plan.get("targets", []):
        title = target.get("references", [{}])[0].get("label") or "Official guidance"
        raw = (
            "<!doctype html><html lang=\"de\"><head>"
            f"<title>{title} - MOCK DEMO</title></head><body><main>"
            "<h1>Starting a sole proprietorship in Canton Zurich</h1>"
            "<p>This offline mock response represents previously acquired official guidance.</p>"
            "<h2>Demonstration content</h2>"
            "<p>The governed pipeline binds, extracts, validates, and reviews these exact local bytes.</p>"
            "</main></body></html>"
        ).encode("utf-8")
        attempt = run / "pages" / target["url_id"] / "attempt-001"
        response = attempt / "response.html"
        response.parent.mkdir(parents=True, exist_ok=True)
        response.write_bytes(raw)
        snapshot = {
            "relative_path": response.relative_to(run).as_posix(),
            "requested_url": target["url"], "final_url": target["url"],
            "content_type": "text/html; charset=utf-8",
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes_downloaded": len(raw),
            "retrieved_at": retrieved_at, "status": 200, "review_flags": [],
        }
        manifest = {
            **target, "status": "saved", "http_status": 200, "snapshots": [snapshot],
            "report": {"requests_sent": 0, "bytes_downloaded": 0, "pages": [],
                       "skipped": [], "stop_reason": "offline-mock-fixture"},
        }
        write_json(attempt / "manifest.json", manifest)
        write_json(attempt.parent / "latest.json", manifest)
        results.append(manifest)
        saved_bytes += len(raw)
    write_json(run / "summary.json", {
        "schema_version": "swisstip.mock-acquisition-summary/v1",
        "target_count": len(results), "counts": {"saved": len(results), "pending": 0},
        "saved_bytes": saved_bytes, "results": results, "supplements": [],
        "network_usage": {"charged_requests": 0, "charged_bytes": 0},
    })
    write_json(run / "gap-report.json", gap_report.build_report(run))


def advance_once(workspace: Path, pack: str, actor=MOCK_COORDINATOR) -> bool:
    """Perform at most one coordinator-owned transition; return whether work changed."""
    service = AutopilotService(workspace, pack)
    workflow = service.status()

    if (workflow.state == WorkflowState.DISCOVERING_SOURCES
            and workflow.gates[ApprovalGate.SCOPE].status == GateStatus.APPROVED):
        if not was_promoted(service, ApprovalGate.SCOPE):
            say("A1 is human-approved. Promoting the verified scope artifact.")
            service.promote(ApprovalGate.SCOPE, actor, workflow.revision)
            return True
        if workflow.gates[ApprovalGate.CATALOGUE].status == GateStatus.UNOPENED:
            say("Source discovery is complete offline. Submitting one bounded official source for A2.")
            submit_catalogue(service, workflow)
            say("A2 catalogue proposal submitted. Waiting for the human decision in the control room.")
            return True

    if (workflow.state == WorkflowState.AWAITING_DOWNLOAD_CONFIRMATION
            and workflow.gates[ApprovalGate.CATALOGUE].status == GateStatus.APPROVED):
        if not was_promoted(service, ApprovalGate.CATALOGUE):
            say("A2 is human-approved. Promoting the exact catalogue and inventory bytes.")
            service.promote(ApprovalGate.CATALOGUE, actor, workflow.revision)
            return True
        run = workspace / ".local" / pack
        plan_path = run / "plan.json"
        plugin_path = run / "plugin-plan.json"
        if not plan_path.is_file() or not plugin_path.is_file():
            pack_dir = workspace / "releases" / pack
            plan = build_plan(pack_dir / "sources.json", pack_dir / "sources.md",
                              scan_set=None, source_ids=None, workers=1)
            write_json(plan_path, plan)
            write_json(plugin_path, {"enabled": [], "sources": []})
            service.report_progress(
                actor, "MOCK CLAUDE prepared the exact offline acquisition plan",
                {"targets": len(plan.get("targets", [])), "network_calls": 0}, workflow.revision)
            say("The acquisition plan is bound and visible. Waiting for human network confirmation.")
            return True

    if workflow.state == WorkflowState.ACQUIRING:
        if not has_event(service, "checkpoint.acquisition"):
            say("Network plan confirmed. Replaying one local mock response with zero network requests.")
            write_mock_acquisition(workspace, pack)
            service.complete_acquisition(actor, workflow.revision)
            say("Offline acquisition reports are bound. Starting deterministic extraction next.")
            return True

    if workflow.state == WorkflowState.EXTRACTING:
        if not has_event(service, "checkpoint.extraction"):
            say("Extracting and validating the exact local response bytes with the real pipeline.")
            run = workspace / ".local" / pack
            code, summary = run_extraction(run, workers=1, force=True, prune_superseded=True,
                                           log=lambda message: say(str(message)))
            if code:
                raise ValueError(f"offline mock extraction failed: {summary}")
            service.complete_extraction(actor, workflow.revision)
            say("Deterministic extraction passed. Preparing the A3 exception review.")
            return True
        if workflow.gates[ApprovalGate.EXCEPTIONS].status == GateStatus.UNOPENED:
            service.submit(ApprovalGate.EXCEPTIONS, "No material acquisition exceptions",
                           {"outstanding": 0, "mock": True}, actor, workflow.revision)
            say("A3 proposal submitted with zero outstanding exceptions. Waiting for the human decision.")
            return True

    if (workflow.state == WorkflowState.GENERATING_KNOWLEDGE
            and workflow.gates[ApprovalGate.EXCEPTIONS].status == GateStatus.APPROVED
            and not any(event.kind == "progress.reported"
                        and event.summary == "MOCK CLAUDE reached offline knowledge generation"
                        for event in service.store.events())):
        service.report_progress(actor, "MOCK CLAUDE reached offline knowledge generation",
                                {"network_calls": 0, "model_calls": 0}, workflow.revision)
        say("A3 is human-approved. The interactive offline walkthrough is complete at A4 generation.")
        return True

    return False


def run(workspace: Path, pack: str, interval: float, once: bool = False) -> int:
    workspace = require_mock_workspace(workspace)
    service = AutopilotService(workspace, pack)
    workflow = service.status()
    say(f"Watching {pack} at state {workflow.state.value}. No network or model calls will be made.")
    last_waiting = None
    while True:
        try:
            changed = advance_once(workspace, pack)
        except WorkflowConflict:
            say("The workflow changed concurrently; reloading the verified state.")
            changed = True
        if once:
            return 0
        if not changed:
            workflow = service.status()
            waiting = (workflow.state, workflow.revision)
            if waiting != last_waiting:
                say(f"Waiting at {workflow.state.value} (revision {workflow.revision}).")
                last_waiting = waiting
        time.sleep(interval)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", type=Path, default=Path(".local/swisstip-team-demo"))
    parser.add_argument("--pack", default="demo-01-scope")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="seconds between workflow checks; default 2")
    parser.add_argument("--once", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval must be greater than zero")
    try:
        return run(args.workspace, args.pack, args.interval, args.once)
    except KeyboardInterrupt:
        print("\nMOCK CLAUDE stopped.", flush=True)
        return 0
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
