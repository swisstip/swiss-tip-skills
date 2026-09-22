"""Install everything the knowledge-base pipeline needs into a workspace.

    python bootstrap.py --workspace .              create .venv and install the published packages
    python bootstrap.py --workspace . --with-ollama    also pull the embedding model for hybrid search
    python bootstrap.py --workspace . --source ../swiss-tip    editable install from a code checkout
    python bootstrap.py --check-only               report what is present, install nothing

The pipeline needs Python 3.14 or newer. This script never installs a system
tool on its own: it prefers `uv`, which downloads that interpreter itself; if
`uv` is absent but the Python running this script is already 3.14 or newer, it
falls back to the standard venv and pip; otherwise it stops and prints the one
command that installs `uv`.

Runs on any Python 3.9 or newer, because it is the one script that runs before
the workspace exists.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PACKAGES = ["swisstip-builder", "swisstip-mcp"]
SOURCE_COMPONENTS = [
    "packages/core", "packages/runtime", "packages/ingestion", "packages/extraction",
    "packages/build", "packages/concepts", "apps/knowledge-builder", "apps/admin-console",
    "apps/mcp-server",
]
EMBEDDING_MODEL = "qwen3-embedding:0.6b"
UV_INSTALL = {
    "win32": 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
    "other": "curl -LsSf https://astral.sh/uv/install.sh | sh",
}


def venv_python(workspace):
    venv = Path(workspace) / ".venv"
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(command, **kwargs):
    print("+ " + " ".join(str(part) for part in command))
    return subprocess.run([str(part) for part in command], check=True, **kwargs)


def ollama_reachable(base_url):
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def report(workspace, base_url):
    python = venv_python(workspace)
    print("workspace:        %s" % Path(workspace).resolve())
    print("uv:               %s" % (shutil.which("uv") or "NOT FOUND"))
    print("venv interpreter: %s" % (python if python.is_file() else "not created yet"))
    if python.is_file():
        subprocess.run([str(python), "-c", "import sys; print('venv python:      ' + sys.version.split()[0])"])
        for package in PACKAGES + ["swisstip-core"]:
            proc = subprocess.run(
                [str(python), "-c", "import importlib.metadata as m; print(m.version(%r))" % package],
                capture_output=True, text=True)
            version = proc.stdout.strip() if proc.returncode == 0 else "not installed"
            print("  %-18s %s" % (package, version))
    print("ollama:           %s" % (shutil.which("ollama") or "not on PATH"))
    tags = ollama_reachable(base_url)
    if tags is None:
        print("ollama server:    not reachable at %s (lexical search still works)" % base_url)
    else:
        models = sorted(model.get("name", "") for model in tags.get("models", []))
        print("ollama server:    reachable, %d model(s): %s" % (len(models), ", ".join(models) or "none"))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", default=".", help="directory that will hold .venv, releases/ and .local/")
    parser.add_argument("--version", help="pin the swisstip packages to this version (default: the newest published)")
    parser.add_argument("--source", help="install editable from a swiss-tip code checkout instead of PyPI")
    parser.add_argument("--python", default="3.14", help="interpreter version for the venv; 3.14 is the minimum")
    parser.add_argument("--office", action="store_true", help="add the office extra (RTF and legacy Word pages)")
    parser.add_argument("--with-ollama", action="store_true", help="pull the embedding model for hybrid search")
    parser.add_argument("--embedding-model", default=EMBEDDING_MODEL)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--check-only", action="store_true", help="report the environment and exit")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    if args.check_only:
        report(workspace, args.ollama_url)
        return 0

    uv = shutil.which("uv")
    if not uv and sys.version_info < (3, 14):
        print("uv is not installed, and the Python running this script is %d.%d, older than the 3.14 the"
              % (sys.version_info.major, sys.version_info.minor))
        print("packages need. This script does not install system tools on its own; install uv with:")
        print("    %s" % UV_INSTALL.get(sys.platform, UV_INSTALL["other"]))
        print("then run this script again. uv downloads Python %s itself." % args.python)
        return 3
    if not uv:
        print("uv is not installed; falling back to this interpreter (%d.%d) and its venv module."
              % (sys.version_info.major, sys.version_info.minor))

    workspace.mkdir(parents=True, exist_ok=True)
    python = venv_python(workspace)
    if not python.is_file():
        if uv:
            run([uv, "venv", "--python", args.python, str(workspace / ".venv")])
        else:
            run([sys.executable, "-m", "venv", str(workspace / ".venv")])

    if args.source:
        source = Path(args.source).resolve()
        missing = [name for name in SOURCE_COMPONENTS if not (source / name / "pyproject.toml").is_file()]
        if missing:
            print("not a swiss-tip checkout (missing %s): %s" % (missing[0], source))
            return 4
        targets = []
        for name in SOURCE_COMPONENTS:
            targets += ["--editable", str(source / name)]
    else:
        pin = ("==" + args.version) if args.version else ""
        extra = "[office]" if args.office else ""
        targets = ["swisstip-builder%s%s" % (extra, pin), "swisstip-mcp%s" % pin]
    if uv:
        run([uv, "pip", "install", "--python", str(python)] + targets)
    else:
        run([str(python), "-m", "pip", "install"] + targets)

    if args.with_ollama:
        if not shutil.which("ollama"):
            print("\nollama is not on PATH. Install it from https://ollama.com/download and run:")
            print("    ollama pull %s" % args.embedding_model)
            print("Hybrid search needs it; lexical search does not, and the pipeline runs without it.")
        else:
            run(["ollama", "pull", args.embedding_model])

    print("")
    report(workspace, args.ollama_url)
    print("\nNext: scaffold a pack")
    print("    %s scaffold.py --workspace %s --pack <pack> --title \"<title>\"" % (python, workspace))
    return 0


if __name__ == "__main__":
    sys.exit(main())
