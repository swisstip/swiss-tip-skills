---
name: build-knowledge-base
description: Build a grounded, citable knowledge base of Swiss public information from official web pages, end to end - discover the sources, crawl them, write concepts and facts with block-level citations, take a human through review, build and validate a release, and author its acceptance and regression suites. Use when the user wants to create, extend or rebuild a Swiss TIP knowledge pack, a citable corpus of official pages, or an MCP knowledge release; also when they ask to add a topic, canton or municipality to an existing pack. Installs the swisstip packages into a workspace itself.
---

# Build a knowledge base from official pages

You are building a **release**: a set of statements about public information, each one
carrying the excerpt of the official page it comes from, the hashes that pin that
excerpt, and the date the page was read. The MCP server serves it, an assistant
answers from it, and a person can check every sentence against its source. Anything
that cannot be traced to a saved page does not belong in it.

The pipeline has eleven steps and two human gates. Read `references/pipeline.md` for
the step order and the exact commands; read `references/hard-rules.md` before writing
any curation. Both are next to this file.

## Set the workspace up first

A workspace is any directory. It needs Python 3.14 or newer, which `uv` downloads:

```shell
python ${CLAUDE_PLUGIN_ROOT}/skills/build-knowledge-base/scripts/bootstrap.py --workspace . --with-ollama
python ${CLAUDE_PLUGIN_ROOT}/skills/build-knowledge-base/scripts/doctor.py --workspace .
```

Ask before installing anything. `bootstrap.py` stops and prints the one command that
installs `uv` rather than installing a system tool on its own; `--with-ollama` pulls a
600 MB embedding model that only hybrid search needs. Everything else is Python
packages in the workspace's own `.venv`. Then scaffold the pack:

```shell
.venv/Scripts/python.exe ${CLAUDE_PLUGIN_ROOT}/skills/build-knowledge-base/scripts/scaffold.py \
  --workspace . --pack <pack> --title "<title>" --canton CH-ZH \
  --topic <topic-id>:"<Topic label>"
```

On macOS and Linux the interpreter is `.venv/bin/python`. Every later command uses the
workspace interpreter, never the system one.

## The five invariants

These are not style preferences. Each one is enforced somewhere downstream, and
breaking one produces a release that looks fine and is not trustworthy.

1. **Evidence is selected, never written.** A citation is a block range of a saved text
   record. Never type a quotation into a curation file - the build resolves citations
   against the records and refuses what it cannot find.
2. **Search terms are copied, never translated.** `source_terms` appear character for
   character in the excerpt they cite. The build verifies this.
3. **No fact without an excerpt.** If the page does not say it, it is not a fact, even
   when you know it is true.
4. **Review status is the person's to set.** Write `assistant-authored-unreviewed`.
   Only the admin console's confirm action, driven by a human, writes `human-reviewed`.
5. **Attestation is the person's to give.** Never pass `--attested-by` with someone's
   name to make a gate pass.

## The eleven steps

Work through them in order, reporting numbers from the reports rather than
impressions. Steps 6 to 10 repeat after every change to the curation, and step 10 is
last because one changed byte of `release.json` invalidates it.

| # | Step | Done when |
| ---: | --- | --- |
| 1 | Scope and the user questions | 10-15 questions exist with their traps, written before any source is chosen |
| 2 | Source discovery and the catalogue | `sources.json` validates and every question has a source behind it |
| 3 | Acquire | Pages are saved and every gap in `gap-report.md` is classified |
| 4 | Extract text | Every question's answer is visibly present in some reading view |
| 5 | Concepts and facts | `curation.yaml` holds concepts with aliases, source terms, questions and cited facts |
| 6 | Build | `build-report.json` drops nothing |
| 7 | **Human review** | A person has confirmed, corrected or rejected every fact |
| 8 | Acceptance and regression suites | Both files exist, written from the reviewed release |
| 9 | Replay and index | Both suites replay; failures are diagnosed, not silenced |
| 10 | **Readiness** | A person has attested the release |
| 11 | Documents | Coverage and limitations state the review numbers in absolute terms |

Delegate the bulk work. This plugin ships four subagents: `kb-scout` (one per authority
branch in step 2), `kb-reader` (one per saved page in step 5), `kb-classifier` (one per
page packet, for institutions and basis), `kb-test-author` (step 8). Give each one the
five invariants and the specific file it works on; merge their output yourself.

For a subagent on a smaller model, use the fully specified prompts in
`references/prescriptive-prompts.md` instead of a short brief - they leave less room
for a helpful invention.

## The two human gates

**Review (step 7).** Start the console and write the reviewer a brief; do not review on
their behalf.

```shell
.venv/Scripts/python.exe -m swisstip.admin_console.app --packs-dir . --actor "<reviewer name>"
```

A good brief orders the queue hardest-first (facts carrying numbers, then the ones
whose concept rests on a single page), lists the contradictions you could not resolve
with both excerpts side by side, names the statements where you generalised a hedged
phrasing, and says plainly what the reviewer is *not* confirming: not that the rule is
in force today, not that the page is still live, not legal advice.

**Attestation (step 10).** Print what the attestor is taking responsibility for -
release ID, digest, counts, review numbers, the gates, the quarantined cases and the
open gaps - and stop. They run the command with their own name.

## What to tell the user up front

A pack of 60-80 pages is a long run: many subagent passes and a review session that a
person has to sit through. Say so before starting, keep `.local/<pack>/worklist.md`
current after every step, and make each step resumable from the files it wrote. If the
session ends, the worklist plus the pack directory is the whole state.

## References

| File | Read it when |
| --- | --- |
| `references/pipeline.md` | Always - the step order, the exact commands, what each stage writes |
| `references/hard-rules.md` | Before writing any curation content |
| `references/curation-schema.md` | Writing or merging concepts and facts |
| `references/test-suites.md` | Writing `acceptance.yaml` or `regression.yaml` (step 8) |
| `references/troubleshooting.md` | A stage fails, the build drops facts, a case fails |
| `references/limits.md` | The user asks what this cannot do, or wants a non-Swiss pack |
| `references/prescriptive-prompts.md` | Briefing a subagent on a smaller model |
| `templates/` | Copy `acceptance.yaml` and `regression.yaml` into the pack in step 8 |
