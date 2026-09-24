# When a stage fails

The pipeline is built to refuse rather than to guess, so most failures are informative.
Fix the cause, not the symptom: every entry below names the wrong fix too, because the
wrong fix usually works.

## Acquire

| Symptom | Cause | Fix |
| --- | --- | --- |
| Target not fetched, no error | The URL is outside `allowed_path_prefixes` | Widen that source's prefix deliberately, or add a source. Not: `/` everywhere |
| HTTP 200 with an error body | The publisher serves a soft error page to a non-browser user agent | Record it, and use a browser user agent if the publisher's terms allow it |
| Robots or login block | Publisher reality | Record it in `sources.md`; the fact does not exist for this release |
| Run stops early | The crawl profile's budget | Raise that source's profile, not the pack's total |
| Pages differ from the catalogue | The catalogue changed after planning | New catalogue version, fresh run directory; keep the old one |

## Extract

| Symptom | Cause | Fix |
| --- | --- | --- |
| Record far shorter than the saved HTML | Content in a component the extractor does not read, or a browser-filled table | Report it. Do not paraphrase what you saw in a browser into a fact |
| PDF with no text | The pages are images; there is no OCR | Drop it, or find the HTML version |
| Record has no language | A PDF without a declared language | Add a `page_languages` rule in the curation |
| `the text dataset has no index` | Build ran before extract | Run the extract stage |

## Build

| `build-report.json` says | Cause | Fix |
| --- | --- | --- |
| Citation does not resolve | Wrong block IDs, or the record changed | Re-read the record and correct the IDs. Not: change the excerpt |
| Source term not in the excerpt | The term was translated or invented | Use a term that is in the excerpt, or drop it |
| Statement not supported | The reader over-reached | Narrow the statement to what the block says |
| Concept without a question in a language | `question_languages` requires one | Write one from the facts, not from a test case |
| Fact dropped | Any of the above | Fix or delete the fact, and report it. A release that builds because a fact vanished is not a release that improved |

A fact that cannot be cited is deleted and named in the report. Widening its excerpt to
a block that does not carry it is the one fix that must never be applied.

## Accept and replay

Three diagnoses, and naming which one it is *is* the work:

1. **The release is wrong.** The fact does not say what the case expects. Fix the
   curation, rebuild, re-run.
2. **The case is wrong.** The expectation came from step 1, before anything was read.
   Fix the case and say why the earlier expectation was wrong.
3. **Retrieval is wrong.** Fact and case are both right, but search does not find the
   concept. Fix aliases, source terms or the sample question - then replay the whole
   regression pack, because every added word moves the rarity weights and can push a
   different concept off the top.

Never weaken `excerpt_contains` to make a case pass.

## Index and hybrid search

| Symptom | Cause | Fix |
| --- | --- | --- |
| Replay exits 2, "semantic search unavailable" | Ollama is not running or the model is missing | Start Ollama, `ollama pull qwen3-embedding:0.6b`, or accept a lexical-only run |
| Replay exits 2, queries fell back to lexical | The index does not match the release | Rebuild the index; it is bound to the release ID and content digest |
| Server serves worse results than expected | A stale index degrades silently to lexical search | Rebuild the index after every release change |

## Readiness

| Symptom | Cause | Fix |
| --- | --- | --- |
| A release without an acceptance suite cannot be ready | No `acceptance.yaml` | Write the suite (step 8) |
| Readiness no longer matches | `release.json` changed by a byte, including a reworded limitation | Run the ready stage again, with the person's name |
| The server with `--require-ready` refuses | No matching readiness record | Same |

## The console

| Symptom | Cause | Fix |
| --- | --- | --- |
| Console shows no cards | Wrong `--packs-dir`, or every fact is already reviewed | Check the path; filter by `review_status` |
| A confirm did not stick | The console writes the curation file; a concurrent edit by you overwrote it | Do not edit `curation.yaml` while the reviewer works |

## When you are stuck

Write what you know into `.local/<pack>/worklist.md` - the stage, the exact error, what
you tried, and which files are in which state - and tell the user. A half-finished run
that is described precisely can be resumed; one that was smoothed over cannot.
