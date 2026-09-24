# The acceptance and regression suites

Two files, two jobs. `acceptance.yaml` is the gate: the questions from step 1, replayed
with no model, plus what a live caller's answer must contain. `regression.yaml` is
breadth: many more queries, retrieval only. Both use `swiss-tip-acceptance/v1`; the
replay runs them as one pack under the acceptance suite's policy, and a case ID may
appear in only one of them. Templates to copy: `../templates/`.

## An acceptance case

```yaml
- case_id: UAT-4
  label: third-country national starting a side business
  question: >-
    I have a B permit through my job in Zurich and want to freelance on the side.
    My friend says I just need to register with the AHV. Is that right?
  expected_answer: >-
    What a correct answer must establish, written from the BUILT release after review:
    every "[to verify]" of step 1 replaced by what a reviewed fact says, or deleted.
  trap: Treating self-employment as a formality and missing the permit question.
  steps:
  - search:
      query: Selbststaendigkeit Bewilligung Drittstaat
      expect_concept: self-employment-permit
      expect_strength: strong        # optional
  - resolve:
      concept_ids: [self-employment-permit]
      jurisdiction: {canton_code: CH-ZH}
      expect_status: {self-employment-permit: SUPPORTED}
  claims:
  - claim: A third-country national needs an authorisation to be self-employed
    concept: self-employment-permit
    statement_contains: [authorisation]        # words of our English statement
    excerpt_contains: [Bewilligung]            # a phrase of the page, copied VERBATIM
  answer:                                      # checked on a live caller's answer
    criteria: [C1, C2, C3]
    must_mention:
      permit: 'permit|Bewilligung'
    must_not:
      just_ahv: 'only|just.{0,20}(AHV|social insurance)'
    cites:
      sem: sem.admin.ch
    resolved: [self-employment-permit]
```

`excerpt_contains` is the tie between your English statement and the official page.
Copy the phrase out of `release.json`, never retype it, and never weaken it to make a
case pass - that is the one edit that turns the gate into decoration.

## Decline cases

A decline case asserts the **server's** behaviour and nothing else: status
`OUT_OF_COVERAGE` and the expected gap. It never asserts what the calling model said,
because that is not the release's to fix.

```yaml
- case_id: DECLINE-2
  label: individual tax advice
  question: How much tax will I actually pay if I go freelance?
  steps:
  - resolve:
      concept_ids: [tax-at-source-tariff]
      jurisdiction: {canton_code: CH-BE}
      expect_status: {tax-at-source-tariff: OUT_OF_COVERAGE}
```

## Place cases

If the pack publishes cantonal or municipal procedure for one place only, prove the
boundary: the same question for another municipality of the canton must not serve the
municipal concepts, and the caveat gap must name the level that applies.

## The regression families

One prefix per family, so a report can be read at a glance:

| Prefix | What it holds |
| --- | --- |
| `Q-EN-`, `Q-DE-` | Plain questions per concept, in each query language |
| `N-` | Noise: typos, no punctuation, keyword-only, situation before the question |
| `CTX-` | The same question with the place given as a code, a canton name, a city name |
| `DATE-` | Questions whose answer depends on a date |
| `OOS-` | Out-of-scope questions that must not match strongly |
| `DECLINE-` | Server-only: expected status and gap |

Rules that keep the breadth honest:

- a regression case never repeats a question already in `acceptance.yaml`;
- a query never contains the words of the expected answer - a query that quotes the fact
  tests nothing;
- a German case must be answerable from the German page, so it may not contain a word
  that exists only in the English statement;
- follow the pack's own ratio of cases per fact rather than writing many cases for the
  concepts that were easy.

## Quarantine

A case that fails in the hybrid run for a genuine retrieval limit is kept with
`blocking: false` and a `quarantine_reason` that states what was measured, and on which
release ID. That is a record, not an excuse: it stays until retrieval changes.

A case that fails because the knowledge is missing is not quarantined. It is a gap, and
it belongs on the worklist.

## Running them

```shell
PY SCRIPTS/replay.py --workspace . --pack <pack>                # lexical and hybrid
PY SCRIPTS/replay.py --workspace . --pack <pack> --lexical-only # no Ollama needed
```

Exit code 1 means a blocking case failed; 2 means the hybrid run was not possible or
fell back to lexical search, so it was not a hybrid replay. The report is written to
`releases/<pack>/regression-report.json`.

The accept stage of the builder replays `acceptance.yaml` alone and fails on a blocking
case, which is what makes it a gate.
