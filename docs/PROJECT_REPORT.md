# Reddit Stock Sentiment Analyzer

**Maintainer:** Devjyoti  
**Project type:** Python application for natural language processing and visualisation

This report describes the implemented project and its demonstration. It is a general
technical report; a module-specific assignment brief and marking rubric were not supplied.

## 1. Problem and objectives

Stock discussions on Reddit contain many informal comments. Manually comparing
which companies receive attention and how people describe them is time-consuming.
This application converts comments into ticker rankings and sentiment summaries.

Its objectives are to identify supported ticker symbols, reduce false matches,
count contributors fairly, summarise language tone, and save inspectable results.
It supports both Reddit collection and analysis of a saved dataset.

## 2. Data and scope

Live collection uses PRAW to read public subreddit discussion threads. Configurable
filters select hot posts by flair, upvote ratio and score, then retain comments and
replies above a comment-score threshold. Named bot accounts can be excluded from
analysis. This is a filtered sample of discussion, not all Reddit activity.

The included [demonstration dataset](../examples/sample_comments.jsonl) contains
12 synthetic comments. It requires no Reddit credentials and is used for the
results below. No successful live Reddit collection is claimed by this report.

Supported ticker symbols come from NASDAQ Trader directories through
[`update_tickers.py`](../update_tickers.py). The updater includes supported common
equities, partnership units and ETFs, while excluding unsupported symbol forms and
certain derivative instruments. Refreshing this list can change historical analyses.

## 3. Methodology

**Ticker detection.** URLs are removed before matching. A cashtag such as `$gme`
can match regardless of case. A bare symbol such as `GME` must be uppercase and
absent from the ambiguous-word blacklist. Single-letter symbols require a cashtag.
Only symbols present in the supported ticker file count.

**Contributor counting.** Each named author contributes once per ticker. Author
names are compared without case differences, and repeated nonempty comment IDs
are ignored. Each comment with an unknown/deleted author is a separate contributor.
Rankings use descending contributor count, then alphabetical ticker order for ties.

**Sentiment.** The application uses NLTK's VADER analyser with a small custom
stock-discussion vocabulary. It is a lexicon-and-rule method; this project does not
train a classifier. Ticker symbols are masked during scoring so names such as
`$LOVE` do not themselves add sentiment.

For a particular ticker, the calculation is:

1. Score each sentence that explicitly mentions that ticker.
2. Average those sentence scores to obtain the comment score.
3. Average an author's relevant comment scores to obtain one contributor score.
4. Average contributor scores to obtain the ticker's mean score.

Contributor scores of at least `0.05` are positive; scores at most `-0.05` are
negative; scores between those boundaries are neutral. The exported shares classify
contributors, not individual comments. Giving contributors equal weight prevents a
prolific named author from receiving extra weight merely by posting more comments.

## 4. Software design and reliability

| Component | Responsibility |
| --- | --- |
| `main.py` | Command-line entry point |
| `app.py` | Options, input validation, Reddit collection, exports and charts |
| `analysis.py` | Detection, grouping, rankings and sentiment calculations |
| `data.py` | Supported symbols, blacklist and custom vocabulary |
| `update_tickers.py` | Validate and refresh the ticker snapshot |

Each run receives a unique output directory. Comments are archived incrementally,
including during replay, so an interrupted collection can leave recoverable data.
CSV tables contain the rankings and scores; PNG charts present them visually.
`run.json` records settings, status, warnings and hashes of analysis inputs.

These records help explain changes between runs. They do not automatically recreate
old software environments. A completed replay of a partial archive also does not
establish that the original collection was complete.

## 5. Demonstration results and testing

The following results were reproduced using `python main.py --demo` on 1 November
2026. They describe the synthetic sample only.

| Ticker | Contributors | Mean score |
| --- | ---: | ---: |
| GME | 3 | -0.001 |
| PLTR | 3 | +0.540 |
| TSLA | 3 | -0.516 |
| AMC | 2 | -0.029 |
| SPY | 2 | -0.024 |

For example, PLTR has three contributors: two are classified positive and one
neutral. Its positive mean describes the wording in this sample, not future price
movement or the wider Reddit community.

The [test suite](../tests/) covers detection boundaries, URLs, author grouping,
stable rankings, sentiment rules, input validation, simulated Reddit failures,
saved outputs and ticker refresh safeguards. Run `python -m pytest -q` to obtain
the current result. Passing these tests establishes selected software behaviours;
it does not measure real-world sentiment accuracy.

## 6. Limitations and evaluation plan

Sarcasm, emoji and financial context can be misinterpreted. Multiple tickers within
one sentence receive the same sentence score. Pronoun-only follow-up sentences can
be missed. Deleted-author identities cannot be reconstructed, and collection
filters create selection bias. No labelled evaluation dataset is included.

The next evaluation step is to define the sentiment target, independently label a
separate set of real comments, and measure a confusion matrix and class-wise
precision, recall and F1. Comparing the custom vocabulary with unmodified VADER
would test whether the additions improve results. Evaluation data should remain
separate from examples used to tune rules.

## 7. Attribution and contribution

This project adapts [asad70/reddit-sentiment-analysis](https://github.com/asad70/reddit-sentiment-analysis)
under its [MIT licence](../LICENSE.md). Devjyoti's version adds the simplified
entry point, demo, stable ranking, URL handling, contributor averaging, input
validation, recoverable archives, provenance information and refresh safeguards.
The original attribution remains intact. The complete development scope is in
the [project overview](../PROJECT_OVERVIEW.md).
