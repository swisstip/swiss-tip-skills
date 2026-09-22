"""Replay a pack's acceptance and regression suites against its release, with no model.

    python replay.py --workspace . --pack mvp-selfemployed
    python replay.py --pack-dir releases/mvp-selfemployed --lexical-only --no-write

Every case is answered in process by the same ReleaseService the MCP server
uses: once with lexical search only, and once with the release's semantic index
and the local Ollama embedding model it names, which is the retrieval the
container serves. The outcome goes to releases/<pack>/regression-report.json.

Exit code 1 when a blocking case fails in a mode, 2 when the hybrid run is not
possible or a query fell back to lexical search, unless --lexical-only is given.

This is the packaged equivalent of scripts/test/regression/run_regression.py of
the swiss-tip-mvp repository, so that a workspace without that repository can
run the same replay. It is a derived work of that file (Apache-2.0, Swiss TIP);
see the NOTICE at the root of this plugin.
"""

import argparse
import json
import sys
from pathlib import Path

from swisstip.build.acceptance import load_regression
from swisstip.runtime.acceptance import check_acceptance, issues_of, regression_report
from swisstip.runtime.semantic import OllamaEmbedder, SemanticError, SemanticSearch, load_index
from swisstip.runtime.service import ReleaseService

try:  # the case catalogue is not in every published version
    from swisstip.build.case_catalogue import CATALOGUE_FILE, load_case_catalogue
except ImportError:  # pragma: no cover - depends on the installed version
    CATALOGUE_FILE = None
    load_case_catalogue = None


def hybrid_service(pack_dir, ollama_url, timeout):
    service = ReleaseService.from_file(pack_dir / "release.json")
    index = load_index(pack_dir / "semantic-index.json", service.release)
    service.semantic_search = SemanticSearch(index, OllamaEmbedder(model=index.model, base_url=ollama_url,
                                                                   timeout_seconds=timeout))
    return service


def write_catalogue(pack_dir):
    if CATALOGUE_FILE is None:
        print("note: this version of swisstip-builder writes no case catalogue")
        return
    path = pack_dir / CATALOGUE_FILE
    path.write_text(load_case_catalogue(pack_dir), encoding="utf-8", newline="\n")
    print("wrote %s" % path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", default=".", help="workspace holding releases/<pack>")
    parser.add_argument("--pack", help="pack name under <workspace>/releases/")
    parser.add_argument("--pack-dir", help="the pack directory itself, instead of --workspace and --pack")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=60, help="seconds per embedding request")
    parser.add_argument("--lexical-only", action="store_true", help="skip the hybrid run and record why")
    parser.add_argument("--no-write", action="store_true", help="print the outcome without writing the report")
    parser.add_argument("--render-only", action="store_true",
                        help="rewrite the case catalogue from the committed suites and reports, without a replay")
    args = parser.parse_args()

    if args.pack_dir:
        pack_dir = Path(args.pack_dir).resolve()
    elif args.pack:
        pack_dir = (Path(args.workspace) / "releases" / args.pack).resolve()
    else:
        parser.error("give --pack or --pack-dir")
    if not (pack_dir / "release.json").is_file():
        print("no release at %s; build the pack first" % (pack_dir / "release.json"))
        return 1
    for name in ("acceptance.yaml", "regression.yaml"):
        if not (pack_dir / name).is_file():
            print("no %s in %s; write the suites first (templates are in ../templates/)" % (name, pack_dir))
            return 1

    if args.render_only:
        write_catalogue(pack_dir)
        return 0

    acceptance, regression, combined = load_regression(pack_dir)
    reports = {"lexical": check_acceptance(ReleaseService.from_file(pack_dir / "release.json"), combined)}
    exit_code = 0
    if args.lexical_only:
        reports["hybrid"] = "not run (--lexical-only)"
    else:
        try:
            reports["hybrid"] = check_acceptance(hybrid_service(pack_dir, args.ollama_url, args.timeout), combined)
        except (OSError, ValueError, SemanticError) as exc:
            reports["hybrid"] = "semantic search unavailable: %s" % exc
            exit_code = 2
    report = regression_report(reports, acceptance.digest(), regression.digest())

    for mode, run in report["runs"].items():
        if "skipped" in run:
            print("%s: skipped, %s" % (mode, run["skipped"]))
            continue
        print("%s (%s): %s of %s cases pass; blocking failed %s; quarantined %d, still failing %d, now passing %s; "
              "%s hybrid-only step(s) not judged"
              % (mode, run["retrieval_mode"], run["passed"], run["cases"], run["failed"] or "none",
                 len(run["quarantined"]), len(run["quarantined_failed"]), run["quarantined_passing"] or "none",
                 run["unjudged_steps"]))
        for issue in issues_of(reports[mode]):
            print("   ", issue)
        if run["failed"]:
            exit_code = max(exit_code, 1)
        if mode == "hybrid" and run["retrieval_mode"] != "hybrid":
            print("hybrid: some queries fell back to lexical search; the run is not a hybrid replay")
            exit_code = 2

    if not args.no_write:
        path = pack_dir / "regression-report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote %s" % path)
        write_catalogue(pack_dir)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
