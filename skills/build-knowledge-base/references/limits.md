# What this cannot do

Tell the user these before they start, not when they hit one.

## Switzerland only

The source catalogue's validator requires `country_code: "CH"`, and the release
validator knows Swiss jurisdiction codes (`CH`, `CH-ZH`, `CH-ZH-261`). A pack for
another country needs that country's place file in the `swiss-tip-places/v1` format
from its official register, an alias file, and a widened jurisdiction validator in the
`swisstip-core` package. That is a code change in the upstream project, not a setting.

The place register that ships with this plugin is the Swiss one: the country, the 26
cantons and the municipalities of the Federal Statistical Office's register, with
hand-written other-language names. It is a snapshot; municipalities merge every
1 January. `swisstip-places --output config/places/ch-register.json` fetches it again.

## The published packages trail the upstream tree

`bootstrap.py` installs what is on PyPI, which is not always the newest code in the
Swiss TIP repositories. A feature described in the upstream documentation may therefore
be missing from your install; `doctor.py` prints the versions, and the scaffolder leaves
out manifest fields the installed model does not know. `--version` pins a version, and
`--source <checkout>` installs editable from a clone when the newest code is needed.

## No live-caller harness

The pipeline proves the *server*: that a query retrieves the right concept and that the
served facts carry the claims the suite demands, with no model in the loop. It does not
prove that an assistant holding these tools answers well, which is the actual product
claim.

Measuring that needs a harness that runs a real assistant against the server, several
times per question, with a control run where the server is unavailable, and a grader per
session. The Swiss TIP repository has one built on OpenCode; this plugin does not ship
it, because it needs a model budget and a separate CLI. If the user wants that
evidence, say what it would take rather than implying the replay covers it.

## Hybrid search needs a local model

Lexical search works with nothing installed. Hybrid search needs Ollama serving
`qwen3-embedding:0.6b` (about 600 MB) at the digest the release's index was built with.
Without it the replay runs lexically and says so, and the served release silently falls
back to lexical search if its index is stale - which is why the index is rebuilt after
every release change.

## No OCR

A PDF whose pages are images has no text, so nothing in it can be cited. The same is
true of information that exists only in a picture - a collection-area map, a floor plan,
a scanned form.

## What the extractor can miss

Content that a publisher renders in the browser (some data tables, some contact
components) may be absent or partial in the text record. The pipeline's answer is to
extend the extractor upstream, with tests, and raise its version. The answer is never to
paraphrase what a browser shows into a fact - that statement would cite an excerpt that
does not contain it.

## Review does not disappear in fast track

Every served fact needs a person to compare it with its excerpt in both modes. Fast
track currently delegates only typed descriptive source metadata and retrieval-only
non-blocking regression variants. Navigation dispositions and every served fact remain
human-routed. Fast track does not reduce the fact-review queue.

## What a release never asserts

That the rule is in force today, that the page still says this, that the answer applies
to the user's case, or that a lawyer has seen it. Both workflow modes require a person
to confirm every served statement against its excerpt. Limitations state bulk and
card-by-card review counts in absolute numbers.
