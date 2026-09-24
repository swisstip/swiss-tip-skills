"""Seed an offline governed-workflow demo and optionally run the real control room.

    python mock_demo.py --workspace .local/swisstip-team-demo --reset --serve

The mock makes no network or model calls. It creates four independent packs at useful
human decision points: A1 scope, A2 catalogue, network confirmation, and fast-track
support review. Every workflow artifact, event, approval and promotion is produced by
the real Swiss TIP service.
"""

import argparse
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

if __name__ == "__main__":
    print("Loading the real offline workflow engine...", flush=True)

from swisstip.builder.autopilot.models import (
    Actor, ActorKind, ApprovalGate, AuthenticationKind, Decision, DecisionClass,
    DelegationVerdict, PromotionSpec, ReviewMode,
)
from swisstip.builder.autopilot.service import AutopilotService
from swisstip.ingestion.download_cli import build_plan

HERE = Path(__file__).resolve().parent
MARKER = ".swisstip-mock-demo.json"
TOPIC = "Starting as a self-employed sole proprietor in Canton Zurich"
QUESTIONS = [
    "How do I register a sole proprietorship in Canton Zurich?",
    "When must I register with the commercial register?",
    "How do I register for social insurance as self-employed?",
]
OUT_OF_SCOPE = ["Individual legal advice", "Live processing times", "Tax calculations"]

COORDINATOR = Actor(kind=ActorKind.COORDINATOR, actor_id="mock-claude-coordinator",
                    authentication=AuthenticationKind.LOCAL_ASSERTED)
SETUP_HUMAN = Actor(kind=ActorKind.HUMAN, actor_id="Mock setup - pre-approved step",
                    authentication=AuthenticationKind.LOCAL_ASSERTED)


def scope_details() -> dict:
    return {"scope_statement": TOPIC, "out_of_scope": OUT_OF_SCOPE, "questions": QUESTIONS}


def catalogue_data(source_id="zh-self-employment", title="Canton Zurich self-employment",
                   notes="Official cantonal starting point for the mock demonstration.") -> dict:
    url = "https://www.zh.ch/de/wirtschaft-arbeit/erwerbstaetigkeit/selbstaendigkeit.html"
    return {
        "schema_version": "source-catalog/v1",
        "artifact_id": "mock-self-employment-sources",
        "version": "demo-1",
        "knowledge_space_id": "mock-self-employment-zurich",
        "title": "Mock official sources",
        "status": "SOURCES_ONLY",
        "scope": {"country_code": "CH", "canton_codes": ["CH-ZH"],
                  "description": TOPIC, "exclusions": OUT_OF_SCOPE},
        "planning_topics": [{"topic_id": "starting", "label": "Starting a sole proprietorship"}],
        "language_discovery": {"preferred_seed_language": "de"},
        "crawl_profiles": {},
        "scan_sets": {"all": [source_id]},
        "sources": [{
            "definition": {
                "source_id": source_id, "start_url": url, "allowed_hosts": ["www.zh.ch"],
                "allowed_path_prefixes": ["/de/wirtschaft-arbeit/"],
                "canonical_authority": "Canton Zurich", "jurisdiction": "CH-ZH", "language": "de",
            },
            "title": title, "authority_level": "cantonal", "source_kind": "official_guidance",
            "priority": "P0", "topic_hints": ["starting"],
            "discovery": {"method": "official_page_link", "reference_url": url,
                          "located_on": date.today().isoformat()},
            "scan_status": "ready", "notes": notes,
        }],
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def initialize_scope(workspace: Path, pack: str, mode=ReviewMode.FULL_REVIEW) -> tuple[AutopilotService, object]:
    kwargs = {}
    if mode == ReviewMode.FAST_TRACK:
        prompt = HERE.parents[2] / "agents" / "kb-frontier-reviewer.md"
        schema = HERE.parent / "templates" / "frontier-review-response.schema.json"
        kwargs = dict(delegation_profile="frontier-review", delegation_model="mock-review-model",
                      delegation_prompt_sha256=hashlib.sha256(prompt.read_bytes()).hexdigest(),
                      delegation_response_schema_sha256=hashlib.sha256(schema.read_bytes()).hexdigest())
    service = AutopilotService(workspace, pack)
    workflow = service.initialize(f"[MOCK DEMO] {TOPIC}", mode, COORDINATOR, **kwargs)
    drafts = workspace / ".local" / pack / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    scope = drafts / "scope.md"
    scope.write_text(
        "# MOCK DEMO - proposed scope\n\n"
        f"{TOPIC}.\n\n## Questions\n" + "".join(f"- {item}\n" for item in QUESTIONS)
        + "\n## Out of scope\n" + "".join(f"- {item}\n" for item in OUT_OF_SCOPE),
        encoding="utf-8")
    pending = service.submit(
        ApprovalGate.SCOPE, "Three target questions and explicit exclusions", scope_details(),
        COORDINATOR, workflow.revision, artifacts={"scope-document": scope}, promotions=[
            PromotionSpec(artifact="scope-document", destination=f"docs/{pack}-acceptance-questions.md")])
    return service, pending


def approve_and_promote(service: AutopilotService, gate: ApprovalGate, workflow):
    proposal = workflow.gates[gate].proposal
    approved = service.decide(gate, Decision.APPROVE, proposal.sha256,
                              "Pre-approved only to position this clearly labelled mock scene.",
                              SETUP_HUMAN, workflow.revision)
    return service.promote(gate, COORDINATOR, approved.revision)


def submit_catalogue(service: AutopilotService, workflow, *, delegated=False):
    workspace, pack = service.root, service.pack
    drafts = workspace / ".local" / pack / "drafts"
    title = "Canton Zurich self-employment"
    notes = "Official cantonal starting point for the mock demonstration."
    data = catalogue_data(title=title, notes=notes)
    if delegated:
        subject = drafts / "source-metadata.json"
        write_json(subject, {"source_id": "zh-self-employment", "title": title, "notes": notes})
        prepared = service.prepare_delegation(
            DecisionClass.SOURCE_METADATA, "zh-self-employment", subject, [],
            "Independent check of descriptive source metadata", "mock-proposer-model",
            "mock-proposal-request-1", COORDINATOR, workflow.revision)
        item = next(reference for reference in service.store.events()[-1].artifacts
                    if reference.schema_version == "swisstip.autopilot-delegation-item/v2")
        reviewer = Actor(kind=ActorKind.FRONTIER_MODEL, actor_id="mock-review-model",
                         authentication=AuthenticationKind.MODEL_RESPONSE)
        policy = service.store.load_policy()
        workflow = service.record_delegated_decision(
            item.sha256, DelegationVerdict.APPROVE,
            "The title and notes are descriptive only and match the supplied official-source packet.",
            "mock-claude-subscription", "mock-review-model", "mock-review-model",
            policy.delegation_prompt_sha256, policy.delegation_response_schema_sha256,
            reviewer, prepared.revision)
    catalogue = drafts / "sources.json"
    inventory = drafts / "sources.md"
    write_json(catalogue, data)
    inventory.write_text(
        "# MOCK DEMO - source inventory\n\n"
        "The executable URL and its host/path boundary are in `sources.json`.\n",
        encoding="utf-8")
    return service.submit(
        ApprovalGate.CATALOGUE, "One official cantonal source with an explicit boundary",
        {"sources": 1, "mock": True}, COORDINATOR, workflow.revision,
        artifacts={"catalogue": catalogue, "inventory": inventory}, promotions=[
            PromotionSpec(artifact="catalogue", destination=f"releases/{pack}/sources.json"),
            PromotionSpec(artifact="inventory", destination=f"releases/{pack}/sources.md")])


def seed(workspace: Path, reset: bool = False, *, report=lambda _message: None) -> list[str]:
    workspace = workspace.resolve()
    marker = workspace / MARKER
    if workspace.exists() and reset:
        if not marker.is_file():
            raise ValueError(f"refusing to reset unmarked directory {workspace}")
        shutil.rmtree(workspace)
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError(f"mock workspace already exists; rerun with --reset: {workspace}")
    workspace.mkdir(parents=True, exist_ok=True)
    write_json(marker, {"schema_version": "swisstip.mock-demo/v1", "topic": TOPIC})

    packs = []
    _, _ = initialize_scope(workspace, "demo-01-scope")
    packs.append("demo-01-scope")
    report("Seeded demo-01-scope (awaiting A1 scope approval).")

    service, scope = initialize_scope(workspace, "demo-02-catalogue")
    scope = approve_and_promote(service, ApprovalGate.SCOPE, scope)
    submit_catalogue(service, scope)
    packs.append("demo-02-catalogue")
    report("Seeded demo-02-catalogue (awaiting A2 catalogue approval).")

    service, scope = initialize_scope(workspace, "demo-03-network")
    scope = approve_and_promote(service, ApprovalGate.SCOPE, scope)
    catalogue = submit_catalogue(service, scope)
    catalogue = approve_and_promote(service, ApprovalGate.CATALOGUE, catalogue)
    pack_dir = workspace / "releases" / service.pack
    run = workspace / ".local" / service.pack
    plan = build_plan(pack_dir / "sources.json", pack_dir / "sources.md",
                      scan_set=None, source_ids=None, workers=1)
    write_json(run / "plan.json", plan)
    write_json(run / "plugin-plan.json", {"enabled": [], "sources": []})
    packs.append("demo-03-network")
    report("Seeded demo-03-network (awaiting network-plan confirmation).")

    service, scope = initialize_scope(workspace, "demo-04-fast-track", ReviewMode.FAST_TRACK)
    scope = approve_and_promote(service, ApprovalGate.SCOPE, scope)
    submit_catalogue(service, scope, delegated=True)
    packs.append("demo-04-fast-track")
    report("Seeded demo-04-fast-track (awaiting A2 with delegated metadata review).")
    return packs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", type=Path, default=Path(".local/swisstip-team-demo"))
    parser.add_argument("--reset", action="store_true", help="replace a workspace created by this script")
    parser.add_argument("--serve", action="store_true", help="run the real admin-console control room")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--actor", default="Team demo reviewer")
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    print(f"Seeding four offline workflow scenes in {workspace}...", flush=True)
    try:
        packs = seed(args.workspace, args.reset, report=lambda message: print(message, flush=True))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Mock workspace: {workspace}", flush=True)
    for pack in packs:
        print(f"  http://127.0.0.1:{args.port}/packs/{pack}/workflow", flush=True)
    print("No network or model calls were made. Every scene is clearly marked MOCK DEMO.", flush=True)
    if not args.serve:
        print("Run the same command with --reset --serve to start the control room.", flush=True)
        return 0
    print("Loading and starting the real admin-console control room...", flush=True)
    from swisstip.admin_console.app import main as console_main
    return console_main([
        "--packs-dir", str(workspace), "--host", "127.0.0.1", "--port", str(args.port),
        "--actor", args.actor,
    ])


if __name__ == "__main__":
    raise SystemExit(main())
