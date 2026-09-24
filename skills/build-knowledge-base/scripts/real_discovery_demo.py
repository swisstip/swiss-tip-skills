"""Run a bounded real-web discovery demo inside a marked mock workspace.

The script crawls three official authority boundaries, auto-approves the source
workflow as an explicitly simulated human, performs governed acquisition and real
text extraction, and stops where model-authored knowledge generation would begin.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit

if __name__ == "__main__":
    print("Loading the real discovery and governed workflow engines...", flush=True)

from swisstip.builder.autopilot.models import (
    Actor, ActorKind, ApprovalGate, AuthenticationKind, Decision, PromotionSpec,
    ReviewMode,
)
from swisstip.builder.autopilot.service import AutopilotService
from swisstip.extraction.extract_cli import run_extraction
from swisstip.ingestion import acquisition, gap_report
from swisstip.ingestion.acquisition import CurlOpener, CurlResponse
from swisstip.ingestion.crawler import CrawlLimits, SafeCrawler, SourceDefinition
from swisstip.ingestion.download_cli import build_plan, main as download_main
from swisstip.ingestion.review_decisions import REVIEW_SCHEMA, observation_fingerprint

MARKER = ".swisstip-mock-demo.json"
DEFAULT_PACK = "demo-real-residence-registration"
TOPIC = "Registering residence after arrival in the Canton of Zurich and the City of Zurich"
QUESTIONS = [
    "Which federal residence requirements apply after arrival in Switzerland?",
    "Which residence matters are handled by the Canton of Zurich migration authority?",
    "How does a person register an arrival with the City of Zurich?",
    "Which official steps, authorities and documents should a newcomer verify?",
]
OUT_OF_SCOPE = [
    "Individual legal advice or eligibility decisions",
    "Municipal procedures outside the City of Zurich",
    "Citizenship, naturalisation and pre-arrival visa applications",
    "Unverified fees, processing times or document requirements",
]

COORDINATOR = Actor(kind=ActorKind.COORDINATOR, actor_id="real-discovery-demo-coordinator",
                    authentication=AuthenticationKind.LOCAL_ASSERTED)
AUTO_APPROVER = Actor(kind=ActorKind.HUMAN, actor_id="Mock demo auto-approver",
                      authentication=AuthenticationKind.LOCAL_ASSERTED)

DISCOVERY_LIMITS = CrawlLimits(
    max_depth=1, max_pages=6, max_requests=10, max_total_bytes=6_000_000,
    max_response_bytes=2_000_000, max_duration_seconds=90,
    request_timeout_seconds=20, delay_seconds=1, max_redirects=4,
    max_links_per_page=120, max_queued_urls=160, max_failures=4,
)

SEEDS = [
    {
        "source_id": "ch-sem-residence",
        "url": "https://www.sem.admin.ch/sem/de/home/themen/aufenthalt.html",
        "hosts": ["www.sem.admin.ch", "sem.admin.ch"],
        "prefixes": ["/sem/de/home/themen/aufenthalt.html", "/sem/de/home/themen/aufenthalt"],
        "authority": "State Secretariat for Migration (SEM)",
        "authority_level": "federal", "jurisdiction": "CH",
        "title": "SEM residence requirements", "keywords": ["anmeld", "aufenthalt", "eu_efta"],
    },
    {
        "source_id": "zh-residence",
        "url": "https://www.zh.ch/de/migration-integration/aufenthalt.html",
        "hosts": ["www.zh.ch", "zh.ch"],
        "prefixes": ["/de/migration-integration/aufenthalt.html", "/de/migration-integration/aufenthalt"],
        "authority": "Canton Zurich - Migration Office",
        "authority_level": "cantonal", "jurisdiction": "CH-ZH",
        "title": "Canton Zurich residence procedures", "keywords": ["anmeld", "aufenthalt", "euefta"],
    },
    {
        "source_id": "zurich-city-arrival",
        "url": "https://www.stadt-zuerich.ch/de/lebenslagen/einwohner-services/umziehen-melden/zuzug.html",
        "hosts": ["www.stadt-zuerich.ch", "stadt-zuerich.ch"],
        "prefixes": ["/de/lebenslagen/einwohner-services/umziehen-melden"],
        "authority": "City of Zurich - Population Office",
        "authority_level": "municipal", "jurisdiction": "CH-ZH",
        "title": "City of Zurich arrival registration", "keywords": ["zuzug", "anmeld", "umzug"],
        "municipality": {"name": "Zurich", "bfs_code": "0261"},
    },
]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def say(message: str) -> None:
    timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
    print(f"[{timestamp}] REAL DISCOVERY DEMO: {message}", flush=True)


def require_mock_workspace(workspace: Path) -> Path:
    workspace = workspace.resolve()
    marker = workspace / MARKER
    if not marker.is_file():
        raise ValueError(f"refusing to write outside a marked mock workspace: {workspace}")
    data = json.loads(marker.read_text(encoding="utf-8"))
    if data.get("schema_version") != "swisstip.mock-demo/v1":
        raise ValueError(f"unsupported mock workspace marker in {workspace}")
    return workspace


class IntegratedProxyCurlOpener:
    """Curl transport using the current Windows identity for proxy negotiation."""

    def __init__(self, proxy: str) -> None:
        self.proxy = proxy

    def open(self, request, timeout=None):
        with tempfile.TemporaryDirectory() as directory:
            headers = Path(directory) / "headers"
            body = Path(directory) / "body"
            command = [
                "curl.exe" if os.name == "nt" else "curl", "--disable", "--silent", "--show-error",
                "--proto", "=http,https", "--max-time", str(timeout or 20),
                "--max-filesize", "25000000", "--proxy", self.proxy,
                "--proxy-negotiate", "--proxy-user", ":",
                "--dump-header", str(headers), "--output", str(body),
            ]
            for key, value in request.header_items():
                command.extend(["--header", f"{key}: {value}"])
            command.append(request.full_url)
            completed = subprocess.run(
                command, capture_output=True, timeout=(timeout or 20) + 5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if completed.returncode:
                raise OSError(completed.stderr.decode(errors="replace").strip())
            return CurlResponse(body.read_bytes(), headers.read_bytes())


def prepare_pack(workspace: Path, pack: str, reset: bool) -> None:
    paths = [workspace / ".local" / pack, workspace / "releases" / pack,
             workspace / "docs" / f"{pack}-acceptance-questions.md"]
    existing = [path for path in paths if path.exists()]
    if existing and not reset:
        raise ValueError(f"demo pack already exists; rerun with --reset: {pack}")
    if existing:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive = workspace / ".local" / "real-discovery-attempts" / stamp
        archive.mkdir(parents=True, exist_ok=False)
        for path in existing:
            destination = archive / ("run" if path == paths[0] else
                                     "release" if path == paths[1] else path.name)
            shutil.move(str(path), destination)
        say(f"Archived the previous attempt under {archive}.")


def scope_details() -> dict:
    return {"scope_statement": TOPIC, "out_of_scope": OUT_OF_SCOPE, "questions": QUESTIONS}


def initialize_and_approve_scope(workspace: Path, pack: str) -> tuple[AutopilotService, object]:
    service = AutopilotService(workspace, pack)
    workflow = service.initialize(f"[REAL DISCOVERY DEMO] {TOPIC}", ReviewMode.FULL_REVIEW, COORDINATOR)
    drafts = workspace / ".local" / pack / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    scope = drafts / "scope.md"
    scope.write_text(
        "# Real discovery demo scope\n\n" + TOPIC + ".\n\n## Questions\n"
        + "".join(f"- {question}\n" for question in QUESTIONS)
        + "\n## Out of scope\n" + "".join(f"- {item}\n" for item in OUT_OF_SCOPE),
        encoding="utf-8",
    )
    pending = service.submit(
        ApprovalGate.SCOPE, "Federal, cantonal and City of Zurich residence-registration scope",
        scope_details(), COORDINATOR, workflow.revision,
        artifacts={"scope-document": scope}, promotions=[
            PromotionSpec(artifact="scope-document",
                          destination=f"docs/{pack}-acceptance-questions.md")])
    approved = service.decide(
        ApprovalGate.SCOPE, Decision.APPROVE,
        pending.gates[ApprovalGate.SCOPE].proposal.sha256,
        "SIMULATED APPROVAL for the real-discovery demo; no legal or factual review is asserted.",
        AUTO_APPROVER, pending.revision)
    return service, service.promote(ApprovalGate.SCOPE, COORDINATOR, approved.revision)


def crawl_seed(run: Path, seed: dict, transport: str, proxy: str | None = None) -> dict:
    output = run / "discovery" / seed["source_id"]
    saved = []

    def save(page, body: bytes) -> None:
        identity = hashlib.sha256(page.final_url.encode("utf-8")).hexdigest()
        folder = output / "pages" / identity
        folder.mkdir(parents=True, exist_ok=True)
        response = folder / "response.html"
        response.write_bytes(body)
        item = {**asdict(page), "response": response.relative_to(run).as_posix()}
        write_json(folder / "metadata.json", item)
        saved.append(item)

    source = SourceDefinition(
        source_id=seed["source_id"], start_url=seed["url"],
        allowed_hosts=tuple(seed["hosts"]), allowed_path_prefixes=tuple(seed["prefixes"]),
        canonical_authority=seed["authority"], jurisdiction=seed["jurisdiction"], language="de",
    )
    opener = IntegratedProxyCurlOpener(proxy) if proxy else CurlOpener() if transport == "curl" else None
    crawler = SafeCrawler(source, DISCOVERY_LIMITS, opener=opener,
                          on_page=save)
    report = crawler.crawl().to_dict()
    value = {"seed": seed, "limits": asdict(DISCOVERY_LIMITS), "report": report, "saved": saved}
    write_json(output / "report.json", value)
    say(f"{seed['authority']}: {len(saved)} pages saved; stop={report['stop_reason']}; "
        f"requests={report['requests_sent']}; bytes={report['bytes_downloaded']}")
    return value


def relevance(seed: dict, page: dict) -> tuple[int, int, str]:
    value = (page.get("final_url", "") + " " + (page.get("title") or "")).lower()
    score = sum(3 for keyword in seed["keywords"] if keyword in value)
    score += 4 if page.get("depth") == 0 else 0
    return score, -int(page.get("depth", 0)), page.get("final_url", "")


def select_pages(results: list[dict], per_authority: int = 2) -> list[dict]:
    selected = []
    for result in results:
        seed = result["seed"]
        unique = {item["final_url"]: item for item in result["saved"]
                  if not urlsplit(item["final_url"]).query}
        ranked = sorted(unique.values(), key=lambda item: relevance(seed, item), reverse=True)
        depth_zero = next((item for item in ranked if item.get("depth") == 0), None)
        choices = [depth_zero] if depth_zero else []
        choices.extend(item for item in ranked if item is not depth_zero)
        choices = choices[:per_authority]
        if not choices:
            raise ValueError(f"real discovery saved no usable page for {seed['authority']}")
        for item in choices:
            selected.append({"source_id": seed["source_id"], "url": item["final_url"],
                             "title": item.get("title") or seed["title"], "depth": item["depth"],
                             "response": item["response"]})
    if len(selected) > 6:
        raise ValueError("governed demo policy permits at most six selected URLs")
    return selected


def catalogue_data(selected: list[dict]) -> dict:
    sources = []
    for seed in SEEDS:
        entry = {
            "definition": {
                "source_id": seed["source_id"], "start_url": seed["url"],
                "allowed_hosts": seed["hosts"], "allowed_path_prefixes": seed["prefixes"],
                "canonical_authority": seed["authority"], "jurisdiction": seed["jurisdiction"],
                "language": "de",
            },
            "title": seed["title"], "authority_level": seed["authority_level"],
            "source_kind": "official_guidance", "priority": "P0",
            "topic_hints": ["residence-registration"],
            "discovery": {"method": "official_page_link", "reference_url": seed["url"],
                          "located_on": date.today().isoformat()},
            "scan_status": "ready",
            "notes": "Selected by a bounded real-web crawl for this isolated demonstration.",
        }
        if seed.get("municipality"):
            entry["municipality"] = seed["municipality"]
        sources.append(entry)
    source_ids = [seed["source_id"] for seed in SEEDS]
    return {
        "schema_version": "source-catalog/v1",
        "artifact_id": "demo-real-residence-registration-sources", "version": "real-discovery-1",
        "knowledge_space_id": "demo-real-residence-registration",
        "title": "Official residence-registration sources for Zurich",
        "status": "SOURCES_ONLY",
        "scope": {"country_code": "CH", "canton_codes": ["CH-ZH"],
                  "description": TOPIC, "exclusions": OUT_OF_SCOPE},
        "planning_topics": [{"topic_id": "residence-registration", "label": TOPIC}],
        "language_discovery": {"preferred_seed_language": "de"},
        "crawl_profiles": {"bounded-real-demo": asdict(DISCOVERY_LIMITS)},
        "scan_sets": {"all": source_ids}, "sources": sources,
    }


def write_catalogue_drafts(workspace: Path, pack: str, selected: list[dict], results: list[dict]) -> tuple[Path, Path, Path]:
    drafts = workspace / ".local" / pack / "drafts"
    catalogue = drafts / "sources.json"
    inventory = drafts / "sources.md"
    discovery = drafts / "discovery-report.json"
    write_json(catalogue, catalogue_data(selected))
    inventory.write_text(
        "# Real discovery demo sources\n\n"
        + "\n".join(f"- [{item['source_id']} page {number}]({item['url']})"
                     for number, item in enumerate(selected, 1)) + "\n",
        encoding="utf-8",
    )
    write_json(discovery, {"topic": TOPIC, "selected": selected, "authorities": results,
                           "network_calls_are_real": True, "model_calls": 0})
    return catalogue, inventory, discovery


def approve_gate(service: AutopilotService, gate: ApprovalGate, workflow, note: str):
    proposal = workflow.gates[gate].proposal
    return service.decide(gate, Decision.APPROVE, proposal.sha256, note, AUTO_APPROVER,
                          workflow.revision)


def write_gap_report(run: Path) -> dict:
    report = gap_report.build_report(run)
    write_json(run / "gap-report.json", report)
    (run / "gap-report.md").write_text(gap_report.render_markdown(report), encoding="utf-8")
    return report


def approve_observed_gaps(run: Path, report: dict) -> dict:
    review = {
        "review_status": "human-reviewed", "decision": "approved",
        "reviewed_by": AUTO_APPROVER.actor_id, "reviewed_on": date.today().isoformat(),
        "reason": "SIMULATED APPROVAL for this demo; the original observed outcome remains visible.",
    }
    decisions = []
    for row in report["targets"]:
        if row.get("outstanding"):
            decisions.append({"url": row["url"],
                              "observation_sha256": observation_fingerprint(row), **review})
    write_json(run / "review-decisions.json", {
        "schema_version": REVIEW_SCHEMA, "catalogue_sha256": report["catalogue_sha256"],
        "acquisition": decisions, "text_documents": [], "scope": review,
    })
    return write_gap_report(run)


def run_demo(workspace: Path, pack: str, reset: bool, transport: str,
             proxy: str | None = None) -> dict:
    workspace = require_mock_workspace(workspace)
    prepare_pack(workspace, pack, reset)
    started_at = datetime.now(UTC).isoformat()
    service, workflow = initialize_and_approve_scope(workspace, pack)
    run = workspace / ".local" / pack

    say(f"Starting bounded real discovery for: {TOPIC}")
    results = [crawl_seed(run, seed, transport, proxy) for seed in SEEDS]
    selected = select_pages(results)
    say(f"Selected {len(selected)} exact pages for the governed A2 proposal.")
    catalogue, inventory, discovery = write_catalogue_drafts(workspace, pack, selected, results)
    pending = service.submit(
        ApprovalGate.CATALOGUE,
        f"{len(selected)} real official pages across federal, cantonal and municipal authorities",
        {"sources": len(SEEDS), "selected_pages": len(selected), "real_network": True},
        COORDINATOR, workflow.revision,
        artifacts={"catalogue": catalogue, "inventory": inventory, "discovery-report": discovery},
        promotions=[
            PromotionSpec(artifact="catalogue", destination=f"releases/{pack}/sources.json"),
            PromotionSpec(artifact="inventory", destination=f"releases/{pack}/sources.md"),
        ])
    approved = approve_gate(
        service, ApprovalGate.CATALOGUE, pending,
        "SIMULATED APPROVAL of the real discovered source boundaries for this demo.")
    workflow = service.promote(ApprovalGate.CATALOGUE, COORDINATOR, approved.revision)

    pack_dir = workspace / "releases" / pack
    plan = build_plan(pack_dir / "sources.json", pack_dir / "sources.md",
                      scan_set=None, source_ids=None, workers=1)
    write_json(run / "plan.json", plan)
    write_json(run / "plugin-plan.json", {"enabled": [], "sources": []})
    workflow = service.confirm_download(AUTO_APPROVER, workflow.revision)
    say(f"SIMULATED human confirmation recorded for {len(plan['targets'])} exact acquisition targets.")

    original_curl_opener = acquisition.CurlOpener
    if proxy:
        acquisition.CurlOpener = lambda: IntegratedProxyCurlOpener(proxy)
    try:
        download_code = download_main([
            "--catalogue", str(pack_dir / "sources.json"), "--markdown", str(pack_dir / "sources.md"),
            "--output", str(run), "--download", "--workers", "1", "--transport", transport,
            "--no-source-plugins",
        ])
    finally:
        acquisition.CurlOpener = original_curl_opener
    report = approve_observed_gaps(run, write_gap_report(run))
    workflow = service.complete_acquisition(COORDINATOR, workflow.revision)
    say(f"Governed acquisition checkpoint recorded; downloader exit={download_code}; "
        f"outstanding gaps={report['counts'].get('outstanding', 0)}.")

    extraction_code, extraction = run_extraction(
        run, workers=1, force=True, prune_superseded=True, log=lambda message: say(str(message)))
    if extraction_code:
        raise ValueError(f"real extraction reported failures: {extraction}")
    workflow = service.complete_extraction(COORDINATOR, workflow.revision)
    pending = service.submit(
        ApprovalGate.EXCEPTIONS, "Real acquisition and extraction observations reviewed",
        {"outstanding": 0, "real_network": True, "simulated_approval": True},
        COORDINATOR, workflow.revision)
    workflow = approve_gate(
        service, ApprovalGate.EXCEPTIONS, pending,
        "SIMULATED APPROVAL of all observed source exceptions for this demo.")
    workflow = service.report_progress(
        COORDINATOR,
        "Real source discovery completed; stopped before model-authored knowledge generation",
        {"selected_pages": len(selected), "extracted_records": extraction.get("records", 0),
         "model_calls": 0}, workflow.revision)

    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    validation = json.loads((run / "text" / "validation.json").read_text(encoding="utf-8"))
    final = {
        "schema_version": "swisstip.real-discovery-demo/v1", "pack": pack, "topic": TOPIC,
        "started_at": started_at, "finished_at": datetime.now(UTC).isoformat(),
        "workspace": str(workspace), "discovery": results, "selected": selected,
        "acquisition": {"exit_code": download_code, "summary": summary,
                        "gap_counts": report["counts"]},
        "extraction": {"exit_code": extraction_code, "summary": extraction,
                       "validation": validation},
        "workflow": {"state": workflow.state.value, "revision": workflow.revision,
                     "events": workflow.event_sequence},
        "approvals": {"actor": AUTO_APPROVER.actor_id, "simulated": True},
        "transport": {"name": transport, "integrated_proxy": bool(proxy)},
        "network_calls_are_real": True, "model_calls": 0,
        "stopped_before": "A4 model-authored knowledge design; no facts or release were fabricated",
    }
    write_json(run / "real-discovery-demo-report.json", final)
    return final


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", type=Path, default=Path(".local/swisstip-team-demo"))
    parser.add_argument("--pack", default=DEFAULT_PACK)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--network", action="store_true",
                        help="required acknowledgement that this command makes real HTTP requests")
    parser.add_argument("--transport", choices=("urllib", "curl"), default="curl")
    parser.add_argument("--proxy",
                        help="HTTP proxy; curl negotiates with the current Windows identity, no secret argument")
    args = parser.parse_args(argv)
    if not args.network:
        parser.error("real discovery requires explicit --network acknowledgement")
    try:
        result = run_demo(args.workspace, args.pack, args.reset, args.transport, args.proxy)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"pack": result["pack"], "topic": result["topic"],
                      "workflow": result["workflow"],
                      "selected_pages": len(result["selected"]),
                      "saved": result["acquisition"]["summary"]["counts"],
                      "records": result["extraction"]["validation"]["records"]},
                     indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
