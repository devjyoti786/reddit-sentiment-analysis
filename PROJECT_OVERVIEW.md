# Project overview

**Title:** Reddit Stock Sentiment Analyzer  
**Maintainer:** Devjyoti  
**Type:** Python command-line application for text analysis and visualisation

## Problem and objectives

Reddit discussions contain large volumes of informal comments about stocks. Reading
them manually makes it difficult to compare which tickers attract attention and how
contributors describe them. This project makes that exploration repeatable by
turning comments into ticker counts, sentiment summaries and charts.

The objectives are to:

- Collect relevant public comments or analyse an existing JSONL dataset.
- Recognise supported stock symbols while reducing common-word and URL false positives.
- Give each named contributor equal weight in ticker counts and sentiment summaries.
- Preserve inputs and run details so results can be inspected and compared.
- Test important behaviours and make the demonstration easy to run.

## Architecture

```text
Reddit API or saved comments
            |
            v
Validated comments + incremental JSONL archive
            |
            v
Ticker extraction -> contributor groups -> stable rankings
            |
            v
VADER sentence scores -> per-contributor averages -> ticker summaries
            |
            v
CSV tables + charts + run metadata
```

`main.py` starts the application. `app.py` handles configuration, collection
and file output. `analysis.py` contains the analysis independently of Reddit access.
`data.py` provides the symbol universe and custom vocabulary. `update_tickers.py`
refreshes symbols from NASDAQ Trader's directory.

PRAW provides Reddit access, NLTK provides VADER, Matplotlib draws charts, and pytest
runs the automated checks. Sentiment comes from a lexicon and rules; this project
does not train a classifier.

## Development scope and attribution

This is an adaptation of [asad70/reddit-sentiment-analysis](https://github.com/asad70/reddit-sentiment-analysis).
The original MIT attribution remains in the repository. The inherited application
already supplied the Reddit stock-discussion concept and a working analysis baseline.

Devjyoti's project version extends that baseline with:

- A named project identity, a simple `main.py` entry point and a built-in demo command.
- Deterministic ranking when tickers have equal counts.
- Consistent URL exclusion and improved ticker masking during scoring.
- Sentiment averaged across an author's comments rather than taking only the first one.
- Validated CLI options and input records with actionable errors.
- Unique output directories, incremental archives and recorded run status.
- Provenance information to help detect changed datasets and analysis components.
- More precise ticker-directory filtering and safer refresh behaviour.
- Regression tests for the added behaviours.

These extensions are the development scope of this version. The project retains
its upstream origin rather than presenting the entire codebase as written from scratch.

## Demonstration and deliverables

After following the README setup, run:

```bash
python main.py --demo
python -m pytest
```

The demo uses synthetic comments and produces an archived dataset, two CSV tables,
two charts and metadata. Explain a result by following one ticker from its source
comments to its contributor count and sentiment summary.

A complete demonstration should show:

1. A successful demo run and its output directory.
2. How named authors are counted once and their comment scores are averaged.
3. How positive, neutral and negative shares are calculated.
4. A test result and examples of the errors caught by validation.
5. The limitations and the distinction between language tone and price expectations.

## Evaluation and future work

The current tests check software behaviour. They are not evidence of sentiment
accuracy. The next evaluation step is to label a separate set of real comments,
define the intended sentiment target, and measure classification performance.
Useful measures include a confusion matrix and precision, recall and F1 for each
sentiment class, alongside manual review of disagreement cases.

Potential improvements include ticker-specific scoring within shared sentences,
better treatment of pronouns and sarcasm, and evaluation of the custom vocabulary
against unmodified VADER. These are future work, not features already delivered.

Known limits include sampling bias from hot posts and score filters, incomplete
comment expansion, unknown identities for deleted accounts, and changes in the
supported ticker universe. Reproducible comparisons require the same inputs and
analysis configuration; matching inputs alone is not sufficient.
