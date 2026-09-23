# The hard rules

Read this before writing anything into a curation file, and put it in front of every
subagent you launch. These rules are what make a release checkable by someone who was
not in the room. Each one exists because the opposite behaviour produces output that
looks correct and is not.

## 1. Evidence is selected, never written

A citation names a document and a range of block IDs in a saved text record. The build
reads those blocks and pins them with hashes. A quotation typed from memory, from a
browser, or from a page you read but did not save, cannot be cited and will not build.

When the text you need is not in a record, the answer is to add the page to the
catalogue and acquire it, or to drop the fact. It is never to write the sentence anyway.

## 2. Source terms are copied, never translated

`source_terms` are the terms that make a query in the page's language match the concept.
They appear character for character in the excerpt they cite - same spelling, same
compound, same capitalisation. The build verifies this and refuses the release otherwise.

A translated term is worse than no term: it looks like coverage of a language the pack
cannot actually match.

## 3. No fact without an excerpt

If the page does not say it, it is not a fact for this release, however certain you are.
Model knowledge entering a release is exactly the failure the release exists to prevent:
a caller cannot tell a grounded sentence from a fluent one, and the citation makes the
invention look verified.

Two common temptations, both refusals:

- the page states a rule "in der Regel" and the statement drops the hedge;
- a second page supplies the condition that the cited section leaves out, and the
  statement merges them. One section per concept; conditions from a sibling section are
  never borrowed.

## 4. Review status belongs to the person

An agent writes `assistant-authored-unreviewed` for a hand-authored statement, or
`model-candidate-automated-review` for one packaged by the extraction pipeline.
`human-reviewed` and `reviewed_by` are written by the admin console's confirm action,
operated by a person looking at the excerpt.

Setting it in the file directly forges a review. The release's limitations then state a
review that did not happen, and every caller repeats that claim.

## 5. Attestation belongs to the person

`--attested-by` takes the name of whoever is accountable for the release. Never pass a
name to make a gate green - not the user's, not a placeholder, not yours.

## 6. The crawler follows the catalogue

The bounded downloader exists so that what was read is exactly what was declared. To
read a page, add it to `sources.json` and bump the catalogue version. Never fetch a page
by other means and drop it into the run directory, and never edit a saved page.

## 7. Numbers come from reports

When you say how many facts, concepts or cases exist, read it out of `release.json`,
`build-report.json` or `regression-report.json`. Do not carry a number forward from an
earlier draft, and do not state a count you have not read this session.

## 8. Say what failed

A stage that fails, a case that is quarantined, a question no source covers, a
contradiction you could not resolve: these go in the report to the user and on the
worklist. A pipeline whose problems are smoothed over in the summary is worse than one
that stops, because the release still ships.

## 9. Workflow state is not chat state

Read `.local/<pack>/autopilot/workflow.json` through `swisstip-autopilot status` before
every action. Submit proposals through the CLI and record human decisions in the
control room. Never write workflow, approval, delegated-decision or readiness files by
hand. A new Claude session resumes from verified files, not from a summary in chat.

## 10. Fast track is routed by code

Claude never decides that its own output is low risk. In this implementation every
served fact remains human-reviewed. A separate frontier-reviewer may approve, reject or
escalate only typed descriptive source metadata and retrieval-only non-blocking
regression variants. Navigation dispositions remain human-routed.
