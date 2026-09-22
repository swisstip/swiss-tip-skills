"""Create the pack layout the knowledge builder expects, in a workspace without the repositories.

    python scaffold.py --workspace . --pack mvp-selfemployed \
        --title "Self-employment and founding a business" \
        --canton CH-ZH --topic legal-form:"Legal form and registration" \
        --topic social-insurance:"Social insurance of the self-employed"

Writes, under the workspace:

    releases/<pack>/sources.json   a valid, empty source catalogue (draft-1)
    releases/<pack>/curation.yaml  the manifest and the topics, with no concepts yet
    config/places/                 the Swiss place register and aliases, so a caller
                                   can name a canton or a city instead of its code
    .local/<pack>/worklist.md      the resumable plan
    .gitignore                     keeps .local/ out of Git

The catalogue is validated with the builder's own validator before it is
written, so a scaffolded pack can never start life in a shape the planner
refuses. `curation.yaml` is deliberately left without concepts: the build
refuses it until the first one is written from a saved page, which is the
correct state for a pack that has read nothing yet.

Run with the workspace interpreter created by bootstrap.py.
"""

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLACE_DATA = HERE.parent / "data" / "places"

CRAWL_PROFILES = {
    "smoke": {"max_depth": 0, "max_pages": 1, "max_requests": 5, "max_total_bytes": 3000000,
              "max_response_bytes": 2000000, "max_duration_seconds": 60, "request_timeout_seconds": 15,
              "delay_seconds": 2, "max_redirects": 2, "max_links_per_page": 200, "max_queued_urls": 50,
              "max_failures": 2},
    "page": {"max_depth": 0, "max_pages": 12, "max_requests": 24, "max_total_bytes": 30000000,
             "max_response_bytes": 4000000, "max_duration_seconds": 300, "request_timeout_seconds": 20,
             "delay_seconds": 2, "max_redirects": 3, "max_links_per_page": 400, "max_queued_urls": 100,
             "max_failures": 3},
    "section": {"max_depth": 1, "max_pages": 40, "max_requests": 80, "max_total_bytes": 80000000,
                "max_response_bytes": 4000000, "max_duration_seconds": 900, "request_timeout_seconds": 20,
                "delay_seconds": 2, "max_redirects": 3, "max_links_per_page": 500, "max_queued_urls": 300,
                "max_failures": 5},
}

LANGUAGE_DISCOVERY = {
    "seed_languages_are_hints": True,
    "method": "Inspect the saved page language and any visible language navigation.",
    "scope": "New language URLs or hosts outside the explicit allowlist require a catalogue update before acquisition.",
    "parallel_content": "Every language version receives its own snapshot, hashes and document identity.",
}

EVIDENCE_POLICY = {
    "status": "PLANNED_NOT_IMPLEMENTED",
    "eligibility": "Apply scope, jurisdiction, applicability, effective date and source language filters before ranking evidence.",
    "ranking": "Prefer the narrow official service page over a general landing page when both support the same statement.",
    "duplicate_support": "Related navigation pages do not count as independent corroboration.",
}

BUILD_NOTES = [
    "URLs and planning metadata only; this file carries no page content.",
    "Ready means eligible for a bounded request, not an assertion that the live page is complete or unchanged.",
    "The downloader snapshots only what this catalogue allows and does not submit forms, sign in or follow links beyond it.",
    "Bump the version (draft-N) with every change; a run directory is bound to the catalogue it was planned from.",
]

CURATION_HEADER = """\
# Curation of the {pack} pack: topics, concepts, facts and their citations.
#
# The build refuses this file until it holds at least one concept with one fact
# that cites a block range of a saved page. That is intentional: a pack that has
# read nothing yet has nothing to serve.
#
# Every fact carries provenance.review_status. An agent may write
# assistant-authored-unreviewed or model-candidate; only the admin console's
# confirm action, driven by a person, writes human-reviewed.
"""


def parse_topic(value):
    topic_id, _, label = value.partition(":")
    if not topic_id or not label:
        raise argparse.ArgumentTypeError("a topic is <topic_id>:<label>, for example legal-form:\"Legal form\"")
    return topic_id.strip(), label.strip()


def catalogue(pack, title, scope, cantons, topics):
    return {
        "schema_version": "source-catalog/v1",
        "artifact_id": "%s-sources" % pack,
        "version": "draft-1",
        "knowledge_space_id": "swisstip",
        "title": "%s - sources" % title,
        "status": "SOURCES_ONLY",
        "scope": {
            "country_code": "CH",
            "canton_codes": list(cantons),
            "description": scope,
            "exclusions": [
                "News, events, vacancies and other short-lived announcements.",
                "Pages whose authoritative publisher is outside this scope.",
                "Commercial advisers, chambers of commerce and law-firm explainers.",
            ],
        },
        "planning_topics": [{"topic_id": topic_id, "label": label} for topic_id, label in topics],
        "language_discovery": LANGUAGE_DISCOVERY,
        "crawl_profiles": CRAWL_PROFILES,
        "scan_sets": {},
        "build_notes": BUILD_NOTES,
        "parallel_page_groups": [],
        "evidence_selection_policy": EVIDENCE_POLICY,
        "sources": [],
    }


def known_fields_only(body):
    """Keep only the manifest fields the installed swisstip-builder knows.

    The curation model gains fields between versions (question_languages arrived after
    0.2.5) and refuses one it does not know, so a scaffold written for the newest model
    would not load on an older install. Dropping the unknown keys here keeps the pack
    valid on whatever is installed; a later upgrade can add them back."""
    try:
        from swisstip.build.curation import Curation
    except ImportError:
        return body
    known = set(getattr(Curation, "model_fields", {}) or {})
    if not known:
        return body
    dropped = [key for key in body if key not in known]
    for key in dropped:
        del body[key]
    if dropped:
        print("note: the installed swisstip-builder does not know %s; left out of the curation"
              % ", ".join(sorted(dropped)))
    return body


def curation(pack, title, scope, topics, places):
    lines = [CURATION_HEADER.format(pack=pack)]
    body = {
        "schema_version": "swiss-tip-curation/v1",
        "pack": pack,
        "title": title,
        "scope_statement": scope,
        "out_of_scope": [
            "Individual eligibility decisions, case outcomes and legal advice.",
            "Live availability, appointment slots and the changing contents of directories.",
            "Procedures whose authoritative publisher is outside the scope statement.",
        ],
        "out_of_scope_response": (
            "Tell the user that this release does not cover the request, quote the scope statement, and point at the "
            "responsible authority instead of answering from general knowledge as if it were grounded."),
        "limitations": [
            "TODO before the first release: state who wrote the statements, who reviewed them and on which date, in "
            "absolute numbers. Every caller reads this list.",
        ],
        "freshness_max_age_days": 60,
        "question_languages": ["en", "de"],
        "publishers": {},
        "institutions": [],
        "page_basis": {},
        "page_languages": {},
        "context_fields": {},
        "topics": [{"topic_id": topic_id, "title": label, "description": "TODO: one line on what this topic covers."}
                   for topic_id, label in topics],
        "concepts": [],
    }
    if places:
        body["place_register"] = "../../config/places/ch-register.json"
        body["place_aliases"] = "../../config/places/ch-aliases.json"
    body = known_fields_only(body)
    try:
        import yaml
        lines.append(yaml.safe_dump(body, allow_unicode=True, sort_keys=False, width=110))
    except ImportError:
        lines.append(json.dumps(body, ensure_ascii=False, indent=2))  # valid YAML
    return "".join(lines)


WORKLIST = """\
# Worklist - {pack}

Created {today}. One line per unit of work, with its state. Any step can be
resumed from this file plus the files it names.

| Step | Unit | State | Note |
| ---: | --- | --- | --- |
| 1 | scope and acceptance questions | todo | |
| 2 | source discovery | todo | |
| 3 | acquire | todo | |
| 4 | extract text | todo | |
| 5 | concepts and facts | todo | |
| 6 | build | todo | |
| 7 | human review | todo | the reviewer's step |
| 8 | acceptance and regression suites | todo | |
| 9 | replay and index | todo | |
| 10 | readiness | todo | the attestor's step |

## Open questions for the reviewer

(none yet)
"""


def write(path, text, force):
    if path.exists() and not force:
        print("kept existing %s" % path)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote %s" % path)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--pack", required=True, help="pack name, for example mvp-selfemployed")
    parser.add_argument("--title", required=True)
    parser.add_argument("--scope", default="TODO: the scope statement every caller reads.",
                        help="the scope statement; it goes into the catalogue and the manifest")
    parser.add_argument("--canton", action="append", default=[], metavar="CH-ZH",
                        help="cantonal scope, repeatable; omit for a federal-only pack")
    parser.add_argument("--topic", action="append", type=parse_topic, default=[], metavar="id:Label",
                        help="planning topic, repeatable; at least one is needed")
    parser.add_argument("--no-places", action="store_true", help="do not copy the Swiss place register")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    topics = args.topic or [("general", "General")]
    workspace = Path(args.workspace).resolve()
    pack_dir = workspace / "releases" / args.pack

    data = catalogue(args.pack, args.title, args.scope, args.canton, topics)
    try:
        from swisstip.ingestion.catalog import dump_source_catalog
        rendered = dump_source_catalog(data)
    except ImportError:
        print("warning: swisstip-builder is not installed here, so the catalogue was not validated")
        rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    except Exception as exc:  # the validator refused it
        print("the scaffolded catalogue does not validate: %s" % exc)
        return 1

    write(pack_dir / "sources.json", rendered, args.force)
    write(pack_dir / "sources.md",
          "# %s - source inventory\n\n**Last update:** %s\n\nOne link list per planning topic; "
          "every page the catalogue intends to save.\n" % (args.title, date.today().isoformat()), args.force)

    places = not args.no_places
    if places:
        for name in ("ch-register.json", "ch-aliases.json"):
            target = workspace / "config" / "places" / name
            if target.exists() and not args.force:
                print("kept existing %s" % target)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PLACE_DATA / name, target)
            print("wrote %s" % target)

    write(pack_dir / "curation.yaml", curation(args.pack, args.title, args.scope, topics, places), args.force)
    write(workspace / ".local" / args.pack / "worklist.md",
          WORKLIST.format(pack=args.pack, today=date.today().isoformat()), args.force)
    gitignore = workspace / ".gitignore"
    if not gitignore.exists():
        write(gitignore, ".venv/\n.local/\n", args.force)

    print("\nThe acceptance and regression suites are written in step 8; templates are next to this script")
    print("in ../templates/. Next: discover the sources and fill releases/%s/sources.json." % args.pack)
    return 0


if __name__ == "__main__":
    sys.exit(main())
