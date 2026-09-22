# Swiss TIP knowledge-base builder

A Claude Code plugin that builds a grounded, citable knowledge base out of official web
pages, end to end: discover the sources, crawl them, write concepts and facts that cite
saved pages block by block, take a person through review, build and validate a release,
and author the suites that judge it.

The release it produces is served by the [Swiss TIP MCP server](https://github.com/swisstip/swiss-tip),
so an assistant can answer from cited official pages instead of from memory.

## Install

```
/plugin marketplace add <this repository>
/plugin install swisstip-kb-builder@swisstip
```

Then say what you want built:

> Build a knowledge base about self-employment and founding a business in Switzerland,
> for the Canton and City of Zurich.

The skill takes it from there: it sets the workspace up, scaffolds the pack, and works
through the eleven steps, stopping at the two steps that belong to a person.

## What gets installed, and when

Nothing until you agree. On the first run the skill offers to create a workspace `.venv`
and install the published `swisstip-builder` and `swisstip-mcp` packages into it, using
[uv](https://docs.astral.sh/uv/), which also downloads the Python 3.14 the packages
need. `uv` itself is never installed silently - the bootstrap script prints the one
command and stops.

Hybrid search additionally needs [Ollama](https://ollama.com) serving
`qwen3-embedding:0.6b`, about 600 MB. It is optional: everything else works with lexical
search, and the tooling says when it is running without it.

```shell
python skills/build-knowledge-base/scripts/bootstrap.py --workspace . --with-ollama
python skills/build-knowledge-base/scripts/doctor.py --workspace . --pack <pack>
```

## What is in here

| Path | What it is |
| --- | --- |
| `skills/build-knowledge-base/SKILL.md` | The pipeline: eleven steps, five invariants, two human gates |
| `skills/build-knowledge-base/references/` | The step commands, the curation and suite schemas, troubleshooting, the limits, and fully specified prompts for smaller models |
| `skills/build-knowledge-base/scripts/` | `bootstrap.py`, `scaffold.py`, `doctor.py`, `replay.py` |
| `skills/build-knowledge-base/templates/` | Starting points for `acceptance.yaml` and `regression.yaml` |
| `skills/build-knowledge-base/data/places/` | The Swiss place register and its aliases, so a caller can name a canton or a city instead of a code |
| `agents/` | Four subagents: scout, reader, classifier, test author |

Everything the pipeline needs that is not inside a published package ships here, so a
workspace with no clone of the Swiss TIP repositories can run the whole thing. That
includes the replay runner (`replay.py`) and the place files, which otherwise live only
in the packs repository.

## What it does not do

It builds Swiss packs: the catalogue validator requires a Swiss country code and the
release validator knows Swiss jurisdiction codes. It ships no live-caller harness, so it
proves the server, not the assistant answering over it. It does no OCR. And it does not
review or attest on your behalf - `references/limits.md` is the full list, and it is
worth reading before starting rather than after.

## Two steps stay human

A person confirms every fact against its excerpt in the review console, and a person
attests the release. The skill prepares both - a review brief that orders the queue
hardest-first, an attestation packet that says plainly what is being taken
responsibility for - and then stops. An agent that marks its own work reviewed produces
a release whose limitations lie to every caller that reads them.

## Licence

Apache-2.0. `skills/build-knowledge-base/scripts/replay.py` is derived from the Swiss TIP
packs repository, and the place files are built from the Federal Statistical Office's
register of municipalities; see [NOTICE](NOTICE).
