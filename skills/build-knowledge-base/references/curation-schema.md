# The curation file

`releases/<pack>/curation.yaml` is the only file a person or an agent writes by hand.
The build turns it into `release.json`, resolving every citation against the saved text
records and pinning it with hashes. Schema version: `swiss-tip-curation/v1`.

## The manifest

Read by every caller, so its words are the product's words.

| Field | What it is |
| --- | --- |
| `pack`, `title` | The pack name and its human title |
| `scope_statement` | What the release covers, served verbatim by `get_coverage` |
| `out_of_scope` | What it deliberately does not cover |
| `out_of_scope_response` | What a caller should say when a question falls outside |
| `limitations` | Who wrote the statements, who reviewed them, when, and what kind of review it was. Absolute numbers, no adjectives |
| `freshness_max_age_days` | How old a snapshot may be before results are stale |
| `question_languages` | The query languages; the build refuses a concept without a sample question in each |
| `publishers` | Publisher name by host, the fallback when no institution rule matches |
| `institutions` | Who publishes the cited pages: id, name, native name, level, body, jurisdiction, URLs |
| `page_basis` | Default basis of a page's excerpts, by host or host plus path prefix |
| `page_languages` | Language of records that declare none (a PDF without `/Lang`) |
| `place_register`, `place_aliases` | Paths to the place files the build embeds, so callers name places instead of codes |
| `topics` | `topic_id`, `title`, `description` |

### Fields that depend on the installed version

The curation model gains fields between package versions and refuses one it does not
know. `question_languages` arrived after 0.2.5, the version currently on PyPI; the
scaffolder checks the installed model and leaves out what it cannot accept, printing a
note when it does. If a field described here is refused, that is the reason - check the
installed version with `doctor.py` before working around it.

## A concept

A concept is one thing a user wants to know, at the granularity of one question.

```yaml
- concept_id: sole-proprietorship-register     # stable kebab-case key, unique in the pack
  topic_id: legal-form
  label: Commercial register entry for a sole proprietorship
  description: When a sole proprietorship must be entered and when the entry is voluntary.
  aliases:                      # the words USERS use, in every query language,
  - Einzelfirma anmelden        # including colloquial forms and likely misspellings.
  - do I have to register my business
  - Handelsregister Pflicht
  source_terms:                 # copied character for character out of the excerpts below
  - Handelsregister
  - Einzelunternehmen
  questions:                    # one per question_language, written from these facts,
  - Do I have to enter my one-person business in the commercial register?   # never copied
  - Muss ich mein Einzelunternehmen im Handelsregister eintragen?           # from a test case
  required_context: [country, canton]      # which parts of the place the answer depends on
  required_user_facts:
  - name: annual_turnover
    status: required
    instruction: Ask for the expected annual turnover of the business in CHF.
  not_served:                   # what a reader could wrongly expect this to cover
  - the individual decision of the register office
  facts: [...]
```

`aliases` and `source_terms` do different jobs. Aliases are how a user might phrase the
subject; source terms are the page's own vocabulary that a query in that language will
hit. An alias may be invented; a source term may not.

An alias that matches three concepts helps none of them - it makes all three rank for a
query that means one. Prefer the specific phrase.

## A fact

```yaml
  facts:
  - fact_id: sole-proprietorship-register-1
    statement: One self-contained English sentence, fully supported by ONE excerpt.
    language: en
    jurisdiction: CH                # CH | CH-<canton> | CH-<canton>-<bfs>
    valid_through: '2026-12-31'      # only when the statement is dated
    provenance:
      kind: curated-statement
      review_status: assistant-authored-unreviewed
      author: <who wrote it, and from what>
      notes:
      - anything the reviewer should check
    evidence:
    - document_id: doc-<id>
      first_block: 84
      basis:
        level: federal            # federal | cantonal | municipal
        kind: act                 # act | ordinance | treaty | directive | guidance | directory | summary
        norm: <the norm and article as the excerpt states it>
```

Supply `document_id`, `first_block` and optional `last_block`; omit `anchor`. The build
fills in the complete anchor, offsets, hashes and excerpt from the record when run with
`--update-curation`. An act, ordinance, treaty or directive basis requires `norm`.
`basis` weighs in search while the publisher's level alone never does.

New governed packs set `coverage_policy: enforce` and
`boilerplate_min_pages: 5` at the top level. Every curation-candidate content section
must then be cited or have a reviewed disposition.

## What the build checks

- every citation resolves to blocks that exist in the text dataset, with matching hashes;
- every source term occurs in an excerpt the concept cites;
- every concept has a sample question in each language of `question_languages`;
- jurisdiction codes are known, and a municipal fact names a real municipality;
- nothing is dropped silently: `build-report.json` lists every fact it could not build.

## Statuses a fact can carry

| `review_status` | Written by | Meaning |
| --- | --- | --- |
| `assistant-authored-unreviewed` | An agent, reading a saved page | Proposed, nobody has checked it |
| `model-candidate-automated-review` | The concept-extraction pipeline | Proposed and model-reviewed, nobody has checked it |
| `human-reviewed` | The admin console's confirm action, only | A named person compared it with its excerpt on a named date |

`human-reviewed` is not a claim that the rule is in force, that the page is still live,
or that a lawyer looked at it. The limitations must say which of those the release does
not assert.
