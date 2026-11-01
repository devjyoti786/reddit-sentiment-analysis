# Reddit Stock Sentiment Analyzer

**A Python NLP project maintained and extended by Devjyoti.**

Explore which stock tickers people discuss on Reddit and how they talk about them.
The application collects comments, identifies tickers, counts contributors, and
uses VADER with a small stock-market vocabulary to produce sentiment tables and charts.

This project adapts [asad70/reddit-sentiment-analysis](https://github.com/asad70/reddit-sentiment-analysis),
originally released under the MIT licence. The original attribution is retained.
See [Project overview](PROJECT_OVERVIEW.md) for the objectives, architecture, extensions and limitations.

## Project documentation

- [Project report](docs/PROJECT_REPORT.md): problem, implementation, demonstration results and evaluation limits.
- [Demo and presentation guide](docs/DEMO_GUIDE.md): commands, a short walkthrough and explanations of the main design choices.
- [Project overview](PROJECT_OVERVIEW.md): objectives, architecture and the work added to the original project.

## Quick start

Use **Python 3.11 or newer**. On macOS, the system `python3` may be older; check
`python3.11 --version` before creating the environment.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python main.py --demo
```

On Windows, activate the environment with `.venv\Scripts\activate`.
For running without the test tools, install `requirements.txt` instead.

The demo uses **12 synthetic comments** and requires no Reddit credentials.
The first sentiment run needs internet access to download VADER's lexicon if it is
not already installed. The sample demonstrates the workflow; it is not an accuracy benchmark.

## Run the project

```bash
# Included sample
python main.py --demo

# Re-analyse a saved dataset
python main.py --input path/to/comments.jsonl

# Collect public Reddit comments using your API credentials
python main.py --subreddits wallstreetbets stocks --posts 25

# See all options and the project version
python main.py --help
python main.py --version
```

The original `reddit-sentiment-analysis.py` command remains available for compatibility.

### Reddit configuration

Live collection requires Reddit API access and valid application credentials.
Configure them through your [Reddit application settings](https://www.reddit.com/prefs/apps).

```bash
cp praw.ini.example praw.ini
```

Edit `praw.ini` with your client ID, client secret and a user agent identifying your
Reddit username. Keep the `[wsb-sentiment]` section name. Alternatively, set
`praw_client_id`, `praw_client_secret` and `praw_user_agent` in your environment.
The application uses read-only access and does not need your Reddit password.
The local credentials file is excluded by `.gitignore`.

### Main options

| Option | Default | Purpose |
| --- | --- | --- |
| `--demo` | off | Analyse the included synthetic sample |
| `--input FILE` | none | Analyse saved JSONL comments |
| `--subreddits` | `wallstreetbets` | Subreddits to read |
| `--posts` | `100` | Hot posts to inspect per subreddit |
| `--flairs` | Daily Discussion, Weekend Discussion, Discussion | Accepted post flairs; posts without a flair are included |
| `--min-upvote-ratio` | `0.70` | Minimum post upvote ratio |
| `--min-post-upvotes` | `20` | Include posts with more than this many upvotes |
| `--min-comment-score` | `2` | Include comments with a score above this value |
| `--more` | `5` | Maximum additional comment expansion calls per post |
| `--top` / `--sentiment-top` | `10` / `5` | Tickers to report / top reported tickers to score |
| `--output` | `output` | Parent folder for saved runs |
| `--show` | off | Also display charts in a window |

## Analysis method

1. **Collect or load comments.** Live collection filters hot posts and comments by
   score and flair, includes replies, and excludes configured bot accounts from analysis.
2. **Identify tickers.** URLs are removed before detection. A valid symbol can appear
   as a cashtag (`$gme`) or an uppercase word (`GME`). Ambiguous words such as `CASH`
   and single-letter symbols such as `F` require a cashtag. The supported universe
   is stored in `tickers.txt`.
3. **Count contributors.** Each named author counts once per ticker. A comment from
   a deleted account counts as its own contributor because its author cannot be identified.
   Ties in mention counts are ordered alphabetically.
4. **Score sentiment.** VADER scores the sentences that mention each ticker. Comments
   from the same named author are averaged first, giving each contributor equal weight.
   A contributor score of at least `0.05` is positive, at most `-0.05` is negative,
   and anything in between is neutral.
5. **Export results.** Save the source comments, tables, charts and run metadata.

The `mentions` column means **contributors**, not total comment occurrences.
Positive, neutral and negative shares describe contributor-level sentiment.
The mean score ranges from `-1` to `1`.

## Saved results

Each run receives a unique directory under `output/`, using a UTC timestamp and random suffix.

| File | Contents |
| --- | --- |
| `comments.jsonl` | Archived input comments, including saved-input runs |
| `mentions.csv` | Top tickers and contributor counts |
| `sentiment.csv` | Mean score and positive, neutral and negative shares |
| `mentions.png` | Ticker mention chart |
| `sentiment.png` | Sentiment distribution chart |
| `run.json` | Settings, status, warnings and provenance hashes |

Charts are created when tickers are found. Comments are saved incrementally, so an
interrupted collection can leave a recoverable partial archive. Check `run.json`
before comparing runs; failed or partial runs may not contain all result files.
The recorded status is `running`, `complete`, `partial`, `failed` or `interrupted`.
`complete` means that this run finished successfully. Replaying a partial archive
does not restore missing Reddit comments or inherit the original collection warnings;
keep the original `run.json` alongside it when assessing coverage.
Metadata includes the source and archived-input hashes, code and data hashes,
library versions and the VADER lexicon hash. These help identify changes, but replaying
an old run still requires the corresponding code, dependencies and vocabulary.

## Maintenance and tests

```bash
# Refresh the supported ticker universe from NASDAQ Trader
python update_tickers.py

# Run automated tests
python -m pytest
```

The ticker updater validates downloaded directories and replaces the local list
only after constructing a valid result. The vocabulary and ambiguous-word blacklist
are in `data.py`.

Tests cover ticker extraction, contributor counting, sentiment rules, simulated
Reddit collection and saved-output behaviour. They do not establish real-world
sentiment accuracy or verify your Reddit credentials.
The included GitHub Actions workflow runs tests on Python 3.11 and 3.12 for pushes
and pull requests. Check the repository's Actions tab for the result of each run.

## Limitations

- VADER measures language tone. Sarcasm, irony, emoji and financial context can be misread.
- Several tickers in the same sentence share that sentence's score.
- Follow-up sentences using pronouns rather than repeating a ticker can be missed.
- Hot-post selection, score filters and limited comment expansion create a sample
  of discussion, not a complete view of Reddit.
- Only supported US-listed symbols are recognised; share classes such as `BRK.B`
  are excluded. Updating the ticker universe can change analysis of historical comments.
- No labelled evaluation dataset or measured classification accuracy is included.

## Project files

| File | Responsibility |
| --- | --- |
| `main.py` | Main entry point |
| `app.py` | CLI, Reddit collection, persistence and visualisation |
| `reddit-sentiment-analysis.py` | Compatibility entry point for the original command |
| `analysis.py` | Ticker detection, contributor counts and sentiment |
| `data.py`, `tickers.txt` | Vocabulary, blacklist and supported symbols |
| `update_tickers.py` | Ticker directory refresh |
| `tests/` | Automated regression tests |
| `examples/sample_comments.jsonl` | Synthetic demonstration data |
| `PROJECT_OVERVIEW.md` | Project explanation and development scope |
| `docs/PROJECT_REPORT.md` | Technical report with demonstration results and limitations |
| `docs/DEMO_GUIDE.md` | Demo walkthrough and presentation preparation |
| `list of subreddits.csv` | Legacy 2021 reference data; unused by the application |

## Attribution and licence

Adapted and extended by **Devjyoti**, 2026. Original project by
[asad70](https://github.com/asad70/reddit-sentiment-analysis).
Distributed under the [MIT licence](LICENSE.md), with the original copyright notice preserved.
