# Swiss TIP knowledge-base builder

A Claude Code plugin that turns a high-level Swiss public-information topic into a
grounded, citable knowledge pack. Claude discovers official sources and coordinates
subagents; the Swiss TIP workflow engine persists proposals and enforces approvals; the
admin console visualizes progress and records human decisions.

## Install

```text
/plugin marketplace add <this repository>
/plugin install swisstip-kb-builder@swisstip
```

Then ask Claude Code:

> Build a knowledge base about starting as a self-employed sole proprietor in the
> Canton of Zurich.

The plugin bootstraps a Python 3.14 workspace with permission, initializes durable
workflow state and guides the A1-A6 process. It supports:

- `full-review`: a person reviews every gate and fact;
- `fast-track`: deterministic policy may send typed descriptive source metadata and
	retrieval-only non-blocking regression variants to a separate frontier-model reviewer;
	source boundaries, navigation dispositions, every served fact, blocking test policy and
	attestation remain human.

## Architecture

| Repository | Ownership |
| --- | --- |
| `swiss-tip-skills` | Claude skill, subagent briefs, portable templates and thin helper scripts |
| `swiss-tip` | Workflow state machine, risk routing, approval integrity, deterministic pipeline and admin-console control room |
| `swiss-tip-mvp` or another pack workspace | Approved catalogues, curation, releases and reports |

Workflow state lives under `.local/<pack>/autopilot/`, not in Claude's conversation and
not in the release directory. A restarted Claude session resumes from verified files.

## Setup

Nothing is installed until the operator agrees. For development against this workspace:

```shell
python skills/build-knowledge-base/scripts/bootstrap.py --workspace . --source ../swiss-tip
.venv/Scripts/python.exe skills/build-knowledge-base/scripts/scaffold.py \
	--workspace . --pack <pack> --title "<title>" --scope "<topic>" \
	--assistant-model "<actual Claude model identity>"
```

The published builder may lag the governed workflow. Bootstrap fails closed when the
installed package has no `swisstip-autopilot`. `--legacy-manual` remains available for
recovery but provides no A1-A6 guarantees.

Hybrid retrieval optionally needs [Ollama](https://ollama.com) with
`qwen3-embedding:0.6b`; lexical serving does not.

## Human control room

```shell
.venv/Scripts/python.exe -m swisstip.admin_console.app --packs-dir . --actor "<name>"
```

Open `http://127.0.0.1:8765/packs/<pack>/workflow`. The screen shows verified state,
gate status, proposal details and the event stream. It records source-budget
confirmation, fact-review completion and final readiness attestation as the console
actor. Claude's CLI intentionally cannot approve or attest.

### Offline team mock

For a predictable walkthrough with no network, Ollama or model calls, seed four real
workflow scenes and run the actual control room:

```powershell
..\.venv\Scripts\python.exe skills\build-knowledge-base\scripts\mock_demo.py `
	--workspace .local\swisstip-team-demo --reset --serve
```

Open `http://127.0.0.1:8765/packs/demo-01-scope/workflow`. The pack picker also
contains A2 catalogue, network-confirmation, and fast-track support-review scenes.
Approvals modify only the isolated mock workspace. Rerun with `--reset --serve` to
restore all scenes.

For a continuous interactive run, leave the control room running and start the
explicitly labelled offline coordinator in a second terminal:

```powershell
..\.venv\Scripts\python.exe -u skills\build-knowledge-base\scripts\mock_claude.py `
	--workspace .local\swisstip-team-demo --pack demo-01-scope
```

In `demo-01-scope`, approve A1, approve the A2 proposal that appears, type the pack
name to confirm the network plan, and approve A3. The control room polls every two
seconds. The companion prints `MOCK CLAUDE` activity and performs the genuine
coordinator-owned promotions, offline acquisition receipts, extraction validation,
and proposal submissions. It stops at every human-owned decision. Its synthetic HTML
fixture is local: the process makes no network, Ollama or model calls. Stop it with
Ctrl+C.

## Claude subscription, no API key

The scaffold creates `config/semantic-models.toml` with `assistant_exchange` and
`frontier-review`. Python writes structured request files and Claude Code subagents
answer them through the subscription. Model identity is explicit and checkpointed; no
Anthropic credential is exported to the workspace.

## Contents

| Path | Purpose |
| --- | --- |
| `skills/build-knowledge-base/SKILL.md` | Governed state-by-state coordinator workflow |
| `skills/build-knowledge-base/references/` | Pipeline, schemas, hard rules and troubleshooting |
| `skills/build-knowledge-base/scripts/` | Bootstrap, governed scaffold, doctor and replay helpers |
| `skills/build-knowledge-base/templates/` | Suite and semantic-model starting points |
| `skills/build-knowledge-base/data/places/` | Swiss place register and aliases |
| `agents/` | Scope planner, scouts, readers, classifier, independent frontier reviewer and test author |
| `tests/` | Offline plugin and upstream-contract checks |

## Boundaries

The plugin builds Swiss packs only. It does no OCR and ships no live-caller harness.
No agent marks its own work human-reviewed or supplies another person's attestation.
The local demo is a cooperative same-user setup: actor and observed-model names are
audited assertions, not cryptographic credentials. Use an isolated coordinator and
hosted authenticated console for an adversarial deployment.

## Licence

Apache-2.0. See [NOTICE](NOTICE) for derived code, place data and quoted-source terms.
