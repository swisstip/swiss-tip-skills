"""Check that a workspace can run the pipeline, and say what is missing.

    python doctor.py --workspace .                     the environment
    python doctor.py --workspace . --pack mvp-selfemployed   the environment and one pack

Prints one line per check: OK, MISSING (blocks the pipeline) or NOTE (limits it
but does not block). Exit code 1 when something is MISSING.

Run it with the workspace interpreter, not the system one.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODULES = [
    ("swisstip.core.contracts", "the tool contracts and the release model"),
    ("swisstip.runtime.service", "search and resolve over a release"),
    ("swisstip.runtime.semantic", "hybrid search"),
    ("swisstip.build.build_cli", "the release build"),
    ("swisstip.ingestion.catalog", "the source catalogue and the crawler"),
    ("swisstip.extraction.extract_cli", "text extraction"),
    ("swisstip.concepts.concepts_cli", "model-proposed concepts"),
    ("swisstip.builder.cli", "the pipeline stages"),
    ("swisstip.admin_console.app", "the review console"),
]
DISTRIBUTIONS = ["swisstip-core", "swisstip-builder", "swisstip-mcp"]
results = []


def check(name, state, detail=""):
    results.append((state, name, detail))
    print("%-8s %-44s %s" % (state, name, detail))


def check_python():
    version = sys.version_info
    detail = "%d.%d.%d at %s" % (version.major, version.minor, version.micro, sys.executable)
    check("python 3.14 or newer", "OK" if version >= (3, 14) else "MISSING", detail)


def check_packages():
    import importlib
    import importlib.metadata as metadata
    importable = True
    for module, purpose in MODULES:
        try:
            importlib.import_module(module)
            check("module %s" % module, "OK", purpose)
        except ImportError as exc:
            importable = False
            check("module %s" % module, "MISSING", str(exc))
    for distribution in DISTRIBUTIONS:
        try:
            check("dist %s" % distribution, "OK", metadata.version(distribution))
        except metadata.PackageNotFoundError:
            # An editable install of the component trees provides the modules without the aggregates.
            check("dist %s" % distribution, "NOTE" if importable else "MISSING",
                  "not installed; the modules come from somewhere else" if importable else "not installed")


def check_ollama(base_url, model):
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=5) as response:
            tags = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        check("ollama at %s" % base_url, "NOTE", "not reachable (%s); lexical search still works" % exc)
        return
    names = [entry.get("name", "") for entry in tags.get("models", [])]
    if any(name.startswith(model.split(":")[0]) for name in names):
        check("embedding model %s" % model, "OK", "served by ollama")
    else:
        check("embedding model %s" % model, "NOTE",
              "ollama is up but the model is missing; run: ollama pull %s" % model)


def check_workspace(workspace):
    workspace = Path(workspace).resolve()
    check("workspace", "OK" if workspace.is_dir() else "MISSING", str(workspace))
    for name in ("ch-register.json", "ch-aliases.json"):
        path = workspace / "config" / "places" / name
        check("places/%s" % name, "OK" if path.is_file() else "NOTE",
              str(path) if path.is_file() else "absent; the release then accepts jurisdiction codes only")


def check_pack(workspace, pack):
    pack_dir = Path(workspace).resolve() / "releases" / pack
    run_dir = Path(workspace).resolve() / ".local" / pack
    check("pack directory", "OK" if pack_dir.is_dir() else "MISSING", str(pack_dir))
    if not pack_dir.is_dir():
        return
    for name, state in (("sources.json", "MISSING"), ("curation.yaml", "MISSING"),
                        ("acceptance.yaml", "NOTE"), ("regression.yaml", "NOTE"),
                        ("release.json", "NOTE"), ("semantic-index.json", "NOTE"),
                        ("readiness.json", "NOTE")):
        path = pack_dir / name
        check(name, "OK" if path.is_file() else state,
              "" if path.is_file() else "not written yet")
    check("run directory", "OK" if run_dir.is_dir() else "NOTE",
          str(run_dir) if run_dir.is_dir() else "no pages acquired yet")
    for part, what in (("pages", "saved pages"), ("text", "text records")):
        path = run_dir / part
        count = len(list(path.rglob("*"))) if path.is_dir() else 0
        check("run/%s" % part, "OK" if count else "NOTE", "%d file(s) - %s" % (count, what))

    curation = pack_dir / "curation.yaml"
    if curation.is_file():
        try:
            from swisstip.build.curation import load_curation
            loaded = load_curation(curation)
            facts = [fact for concept in loaded.concepts for fact in concept.facts]
            statuses = {}
            for fact in facts:
                key = getattr(fact.provenance, "review_status", "unknown")
                statuses[key] = statuses.get(key, 0) + 1
            check("curation loads", "OK", "%d concept(s), %d fact(s): %s"
                  % (len(loaded.concepts), len(facts),
                     ", ".join("%s %s" % (count, name) for name, count in sorted(statuses.items())) or "none"))
        except Exception as exc:  # the validator refused it, which is a finding
            check("curation loads", "NOTE", "%s: %s" % (type(exc).__name__, " ".join(str(exc).split())[:150]))

    release, readiness = pack_dir / "release.json", pack_dir / "readiness.json"
    if release.is_file() and readiness.is_file():
        try:
            release_id = json.loads(release.read_text(encoding="utf-8"))["release_id"]
            attested = json.loads(readiness.read_text(encoding="utf-8")).get("release_id")
            check("readiness matches release", "OK" if attested == release_id else "NOTE",
                  "%s vs %s" % (attested, release_id) if attested != release_id else release_id)
        except (ValueError, KeyError) as exc:
            check("readiness matches release", "NOTE", str(exc))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--pack")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--embedding-model", default="qwen3-embedding:0.6b")
    args = parser.parse_args()

    check_python()
    check_packages()
    check_workspace(args.workspace)
    check_ollama(args.ollama_url, args.embedding_model)
    if args.pack:
        check_pack(args.workspace, args.pack)

    missing = [name for state, name, _ in results if state == "MISSING"]
    notes = [name for state, name, _ in results if state == "NOTE"]
    print("\n%d check(s): %d missing, %d note(s)" % (len(results), len(missing), len(notes)))
    if missing:
        print("blocking: %s" % ", ".join(missing))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
