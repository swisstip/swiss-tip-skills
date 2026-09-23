---
name: build-knowledge-base
description: Build, extend, resume or rebuild a governed Swiss TIP knowledge pack from a high-level topic. Uses durable A1-A6 approvals, official-source discovery, bounded acquisition, block-level evidence, full human review or conservative fast track, acceptance suites and readiness attestation. Use for citable Swiss public-information knowledge bases and MCP knowledge releases.
---

# Build a governed knowledge base

You are the Claude Code coordinator of a Swiss TIP workflow. Claude performs research,
delegates page work, submits structured proposals and invokes deterministic commands.
The Python workflow engine owns state and policy. The browser control room owns human
approvals. The conversation is never the source of truth.

Read `references/hard-rules.md` first and keep those rules in every subagent brief.
Read `references/pipeline.md` for commands and reports. Use the focused agents in
`agents/`: `kb-scope-planner`, `kb-scout`, `kb-reader`, `kb-classifier`,
`kb-frontier-reviewer` and `kb-test-author`.

## Set up once

Ask before installing. From the target workspace:

```shell
python ${CLAUDE_PLUGIN_ROOT}/skills/build-knowledge-base/scripts/bootstrap.py \
   --workspace . --source <path-to-swiss-tip>
```

The published builder may lag this workflow. `bootstrap.py` fails closed when the
installed package has no `swisstip.builder.autopilot.cli`.

Initialize a governed workflow. Use the actual model identity Claude Code reports - do
not invent or shorten it:

```shell
.venv/Scripts/python.exe ${CLAUDE_PLUGIN_ROOT}/skills/build-knowledge-base/scripts/scaffold.py \
   --workspace . --pack <pack> --title "<title>" --scope "<high-level topic>" \
   --assistant-model "<observed Claude model>" --review-mode full-review
```

For fast track add `--review-mode fast-track --delegation-profile frontier-review`
and `--frontier-model "<distinct reviewer identity>"`. The reviewer identity must
differ from the proposing model identity; that exact identity is pinned at A1.
On macOS/Linux use `.venv/bin/python`. The scaffold writes durable state under
`.local/<pack>/autopilot/`, the model config and place data. It writes no incomplete
pack under `releases/`.

Start the human control room:

```shell
.venv/Scripts/python.exe -m swisstip.admin_console.app --packs-dir . --actor "<person>"
```

Open `http://127.0.0.1:8765/packs/<pack>/workflow`.

## The operating loop

At the start of every turn and after every command:

```shell
.venv/Scripts/python.exe -m swisstip.builder.autopilot.cli status \
   --packs-dir . --pack <pack> --json
```

Perform only the action permitted by `state`. Never skip a gate, edit
`workflow.json`, write an approval file, or call `--attested-by` yourself.

| State | Coordinator action | Stop condition |
| --- | --- | --- |
| `drafting_scope` | Ask `kb-scope-planner`; submit A1 JSON | `awaiting_scope_approval` |
| `discovering_sources` | Fan out `kb-scout`; compile the exact catalogue proposal | `awaiting_catalogue_approval` |
| `awaiting_download_confirmation` | Plan acquisition without download; person confirms in browser | `acquiring` |
| `acquiring` | Run bounded download and gaps; checkpoint acquisition | `extracting` |
| `extracting` | Extract and validate text; checkpoint extraction; submit A3 exceptions | `awaiting_exception_approval` |
| `generating_knowledge` | Run page readers/concepts exchange, merge, classify, enforce coverage; submit A4 | `awaiting_knowledge_design_approval` |
| `awaiting_fact_review` | Prepare review brief; person reviews every served fact and completes checkpoint | `generating_tests` |
| `generating_tests` | Ask `kb-test-author`; validate and submit A5 | `awaiting_acceptance_approval` |
| `validating` | Build, coverage, acceptance, index and replay; checkpoint validation | `awaiting_attestation` |
| `awaiting_attestation` | Print packet and stop; person presses Attest in browser | `ready` |

Submit proposals through the CLI, never by writing approvals:

```shell
.venv/Scripts/python.exe -m swisstip.builder.autopilot.cli submit \
   --packs-dir . --pack <pack> --gate scope --summary "<summary>" \
   --details .local/<pack>/scope-proposal.json --expected-revision <revision> \
   --artifact scope-document=.local/<pack>/drafts/scope.md \
   --promote scope-document=docs/<pack>-acceptance-questions.md
```

Use gate names `scope`, `catalogue`, `exceptions`, `knowledge-design`, and
`acceptance`. The CLI deliberately has no approval or attestation command.
Every promotable file is first written under `.local/<pack>/drafts/`, snapshotted into
the proposal and bound to the human decision. After A1, A2, A4 or A5 approval, run:

```shell
.venv/Scripts/python.exe -m swisstip.builder.autopilot.cli promote \
   --packs-dir . --pack <pack> --gate <gate> --expected-revision <revision>
```

Promotion allows only gate-specific destinations and refuses to overwrite an existing
file unless the proposal named its previous SHA-256. A3 has no promoted file: after its
human decision, read status and continue from `generating_knowledge`; do not call
`promote --gate exceptions`.

After deterministic phases:

```shell
.venv/Scripts/python.exe -m swisstip.builder.autopilot.cli checkpoint \
   --packs-dir . --pack <pack> --phase <acquisition|extraction|validation> \
   --expected-revision <revision>
```

When a human gate is pending, report the proposal counts and browser URL, then stop.
Resume only after the user says the decision is recorded, by reading status again.

For long phases, record only measurable progress with known denominators:

```shell
.venv/Scripts/python.exe -m swisstip.builder.autopilot.cli progress \
   --packs-dir . --pack <pack> --summary "Reading saved pages" \
   --metric documents_completed=4 --metric documents_total=8 \
   --metric current_document="doc-..." --expected-revision <revision>
```

Do not invent one overall percentage for open-ended model work. The control room shows
the latest verified progress event and the complete event stream.

## Claude subscription bridge

The scaffolded `config/semantic-models.toml` contains `assistant_exchange` and
`frontier-review`. No Anthropic API key is used or passed to Python.

Run `swisstip.concepts.concepts_cli` with
`--config config/semantic-models.toml --profile assistant_exchange`. It writes unmatched
requests under `concepts/jobs/<job>/exchange/requests/`. For each request, launch a
separate page-reader subagent and write a response that names the actual
`observed_model` and whose `content` is a JSON string satisfying `response_schema`.
Run the exchange checker, rerun for independent support review, and rerun again for
basis classification until the concepts command exits zero. Do not let one subagent
both propose and review the same candidate.

## Fast track

Fast track does not let Claude choose what is low risk. In this implementation every
served fact remains human-reviewed. Frontier review is limited to typed descriptive
source metadata (`source_id`, `title`, `notes`) and retrieval-only non-blocking
regression variants. Navigation dispositions remain human-routed until the engine has
a deterministic navigation predicate. A separate `kb-frontier-reviewer` call returns
`approve`, `reject` or `escalate`; the later A2 or A5 proposal records whether the exact
reviewed member was applied, omitted, or returned to human review. The model verdict
never approves the gate. Never use delegation to publish a served statement.

## Source and evidence boundaries

- Every Markdown link in `sources.md` is a download target. Link only A2-approved HTTPS
   URLs inside a selected `sources.json` host/path allowlist. Put rejected or unapproved
   URLs in inline code.
- Read every `curation_candidate` in `text/index.json`, using
   `text/reading/<document_id>.md` and `text/documents/<document_id>.json`.
- Evidence is block ranges, never typed quotations. Source terms are copied from those
   blocks, never translated.
- New packs use `coverage_policy: enforce`; every candidate section is cited or has an
   approved disposition.
- A test expectation comes from the built release. `excerpt_contains` is copied from
   `release.json`, never retyped or weakened.

## Recovery and legacy mode

The verified workflow, events, proposals, decisions and checkpoints under
`.local/<pack>/autopilot/` are the whole coordinator state. A new Claude session resumes
by reading `status --json`; it does not reconstruct progress from chat.

`scaffold.py --legacy-manual` retains the old ungated scaffold for recovery and older
builders. Never present that route as governed autopilot or fast track.
