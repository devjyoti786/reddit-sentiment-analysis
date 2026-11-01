'''Devjyoti's Reddit Stock Sentiment Analyzer: collection, analysis and exports.

Adapted from asad70/reddit-sentiment-analysis under the MIT licence (LICENSE.md).
Run ``python main.py --demo`` for an example without Reddit credentials.
'''

import argparse
import configparser
import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from analysis import count_mentions, make_analyzer, ranked_mentions, summarize

APP_NAME = 'Reddit Stock Sentiment Analyzer'
APP_AUTHOR = 'Devjyoti'
APP_VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parent

PRAW_SITE = 'wsb-sentiment'        # section name in praw.ini


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=f'{APP_NAME} by {APP_AUTHOR}.')
    p.add_argument('--version', action='version', version=f'{APP_NAME} {APP_VERSION} by {APP_AUTHOR}')
    p.add_argument('--subreddits', nargs='+', default=['wallstreetbets'], help='subreddits to read')
    p.add_argument('--flairs', nargs='+', default=['Daily Discussion', 'Weekend Discussion', 'Discussion'],
                   help='post flairs to read; posts without a flair are read too')
    p.add_argument('--posts', type=int, default=100, help='how many "hot" posts to look through per subreddit')
    p.add_argument('--min-upvote-ratio', type=float, default=0.70, help='skip posts below this upvote ratio')
    p.add_argument('--min-post-upvotes', type=int, default=20, help='skip posts with this many upvotes or fewer')
    p.add_argument('--min-comment-score', type=int, default=2, help='skip comments with this score or lower')
    p.add_argument('--sort', default='new', choices=['new', 'top', 'best', 'controversial', 'old', 'q&a'],
                   help='comment order when fetching')
    p.add_argument('--more', type=int, default=5,
                   help='extra batches of comments to load per post (each is one API call)')
    p.add_argument('--ignore-authors', nargs='*', default=['AutoModerator', 'VisualMod'],
                   help='accounts to skip, e.g. bots')
    p.add_argument('--top', type=int, default=10, help='how many most-mentioned tickers to list')
    p.add_argument('--sentiment-top', type=int, default=5, help='how many top tickers to score (capped at --top)')
    source = p.add_mutually_exclusive_group()
    source.add_argument('--input', type=Path, help='analyse saved comments.jsonl instead of fetching from Reddit')
    source.add_argument('--demo', action='store_true', help='analyse the included fictional example comments')
    p.add_argument('--output', type=Path, default=Path('output'), help='folder for results')
    p.add_argument('--show', action='store_true', help='also open the charts in a window')
    args = p.parse_args(argv)
    for name in ('posts', 'top', 'sentiment_top'):
        if getattr(args, name) < 1:
            p.error(f'--{name.replace("_", "-")} must be at least 1')
    if args.more < 0:
        p.error('--more must be at least 0')
    if not math.isfinite(args.min_upvote_ratio) or not 0 <= args.min_upvote_ratio <= 1:
        p.error('--min-upvote-ratio must be between 0 and 1')
    args.sentiment_top = min(args.sentiment_top, args.top)
    if args.demo:
        args.input = ROOT / 'examples' / 'sample_comments.jsonl'
    return args


def connect():
    '''Log in read-only, with credentials from praw.ini or praw_* environment variables.'''
    import praw
    from praw.exceptions import MissingRequiredAttributeException
    try:
        try:
            reddit = praw.Reddit(PRAW_SITE)
        except configparser.NoSectionError:
            reddit = praw.Reddit()                  # no praw.ini section: environment variables only
    except MissingRequiredAttributeException as e:
        sys.exit(f'Reddit credentials missing ({e}).\n'
                 f'Copy praw.ini.example to praw.ini and fill it in. See "Reddit API keys" in README.md.')
    reddit.read_only = True
    return reddit


def author_name(item):
    '''Name of a post's or comment's author, or None if the account was deleted.'''
    return item.author.name if item.author else None


def fetch_comments(reddit, args, warnings=None):
    '''Yield every qualifying comment as a dict, printing progress as posts are read.'''
    from praw.models import MoreComments
    warnings = warnings if warnings is not None else []
    flairs = set(args.flairs)
    for sub in args.subreddits:
        for post in reddit.subreddit(sub).hot(limit=args.posts):
            if not (post.upvote_ratio >= args.min_upvote_ratio and post.ups > args.min_post_upvotes
                    and (post.link_flair_text in flairs or post.link_flair_text is None)):
                continue
            post.comment_sort = args.sort
            try:
                post.comments.replace_more(limit=args.more)
            except Exception as e:                  # e.g. 413 "too large" on huge threads
                warning = f'could not load extra comments for "{post.title}": {e!r}; using what loaded'
                warnings.append({'post_id': post.id, 'subreddit': sub, 'message': warning})
                print(f'  {warning}')
                try:
                    post.comments.replace_more(limit=0)     # drop placeholders, no request
                except Exception:
                    pass
            kept = 0
            for comment in post.comments.list():    # .list() includes replies
                if isinstance(comment, MoreComments) or comment.score <= args.min_comment_score:
                    continue
                kept += 1
                yield {'post_id': post.id, 'post_title': post.title, 'subreddit': sub,
                       'comment_id': comment.id, 'author': author_name(comment),
                       'body': comment.body, 'score': comment.score, 'created_utc': comment.created_utc}
            print(f'  r/{sub}: "{post.title}" - {kept} comments')


def iter_comments(path):
    '''Read JSONL with useful file/line errors, without losing already-read records.'''
    with open(path, encoding='utf-8') as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip():
                continue
            location = f'{path}:{line_number}'
            try:
                comment = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'{location}: invalid JSON: {exc.msg}') from exc
            if not isinstance(comment, dict):
                raise ValueError(f'{location}: each comment must be a JSON object')
            if not isinstance(comment.get('body'), str):
                raise ValueError(f'{location}: body must be a string')
            if comment.get('author') is not None and not isinstance(comment['author'], str):
                raise ValueError(f'{location}: author must be a string or null')
            for key in ('post_id', 'comment_id'):
                if comment.get(key) is not None and not isinstance(comment[key], str):
                    raise ValueError(f'{location}: {key} must be a string or null')
            yield comment


def load_comments(path):
    return list(iter_comments(path))


def print_report(mentions, rows, top, n_comments, n_posts, seconds):
    print(f'\nAnalysed {n_comments} comments from {n_posts} posts in {seconds:.1f} seconds.')
    if not mentions:
        print('No tickers found.')
        return
    print(f'\n{min(top, len(mentions))} most-mentioned tickers (one mention per contributor):')
    print('Named authors count once; each comment with a deleted author counts separately.')
    for symbol, count in ranked_mentions(mentions, top):
        print(f'  {symbol:<6}{count:>6}')
    print(f'\nSentiment of the top {len(rows)} (share of contributors with positive / neutral / negative tone;')
    print('mean score runs from -1 to 1). This measures tone of language, not a price prediction.')
    print(f'  {"ticker":<7}{"contributors":>13}{"mean":>8}{"pos":>7}{"neu":>7}{"neg":>7}')
    for r in rows:
        print(f'  {r["ticker"]:<7}{r["mentions"]:>13}{r["mean_score"]:>+8.3f}'
              f'{r["positive"]:>7.0%}{r["neutral"]:>7.0%}{r["negative"]:>7.0%}')


def save_results(out_dir, mentions, rows, top, meta):
    with open(out_dir / 'mentions.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['ticker', 'mentions'])
        w.writerows(ranked_mentions(mentions, top))
    with open(out_dir / 'sentiment.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['ticker', 'mentions', 'mean_score', 'positive', 'neutral', 'negative'])
        w.writeheader()
        w.writerows(rows)
    write_metadata(out_dir, meta)


def save_charts(out_dir, mentions, rows, top, show):
    import matplotlib
    if not show:
        matplotlib.use('Agg')                       # no window needed; works on servers too
    import matplotlib.pyplot as plt

    names, counts = zip(*ranked_mentions(mentions, top))
    fig, ax = plt.subplots(figsize=(8, 0.45 * len(names) + 1.2))
    ax.barh(names[::-1], counts[::-1], color='#2456a4')
    for y, c in enumerate(counts[::-1]):
        ax.text(c, y, f' {c}', va='center')
    ax.set_title(f'{APP_NAME}\n{len(names)} most-mentioned tickers')
    ax.set_xlabel('contributors (deleted authors counted per comment)')
    fig.text(0.99, 0.01, f'By {APP_AUTHOR}', ha='right', fontsize=8, color='#555555')
    fig.tight_layout()
    fig.savefig(out_dir / 'mentions.png', dpi=150)
    if not show:
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 0.6 * len(rows) + 1.4))
    labels = [f'{r["ticker"]} (n={r["mentions"]})' for r in rows][::-1]
    left = [0.0] * len(rows)
    for key, color in (('negative', '#c0392b'), ('neutral', '#b8bec6'), ('positive', '#2e8b57')):
        values = [r[key] for r in rows][::-1]
        ax.barh(labels, values, left=left, color=color, label=key)
        left = [a + b for a, b in zip(left, values)]
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title('Average tone per contributor about each ticker')
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.35), ncol=3, frameon=False)
    fig.tight_layout()
    fig.text(0.99, 0.01, f'By {APP_AUTHOR}', ha='right', fontsize=8, color='#555555')
    fig.savefig(out_dir / 'sentiment.png', dpi=150)

    if show:
        plt.show()
    plt.close('all')


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def provenance():
    '''Record the exact analysis inputs, without reading Reddit credentials.'''
    packages = {}
    for name in ('praw', 'nltk', 'matplotlib'):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    files = ('app.py', 'analysis.py', 'data.py', 'tickers.txt', 'requirements.txt')
    info = {'python': sys.version.split()[0], 'packages': packages,
            'files_sha256': {name: file_hash(ROOT / name) for name in files}}
    try:
        revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                                  text=True, timeout=3, check=True)
        status = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True,
                                text=True, timeout=3, check=True)
        info.update(git_revision=revision.stdout.strip(), git_dirty=bool(status.stdout.strip()))
    except (OSError, subprocess.SubprocessError):
        pass
    return info


def write_metadata(out_dir, meta):
    temporary = out_dir / 'run.json.tmp'
    temporary.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(out_dir / 'run.json')


def main(argv=None):
    args = parse_args(argv)
    start = time.monotonic()
    print(f'{APP_NAME} v{APP_VERSION} | {APP_AUTHOR}')
    try:
        args.output.mkdir(parents=True, exist_ok=True)
        prefix = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S_UTC_')
        out_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=args.output))
    except OSError as exc:
        print(f'Cannot create output directory: {exc}', file=sys.stderr)
        return 1

    warnings = []
    comments = []
    meta = {'project': APP_NAME, 'author': APP_AUTHOR, 'version': APP_VERSION,
            'started': utc_now(), 'status': 'running', 'warnings': warnings,
            'source': 'demo' if args.demo else ('file' if args.input else 'reddit'),
            'sentiment_policy': 'mean per author, then equal weight per contributor',
            'deleted_author_policy': 'one contributor per comment',
            'ranking_policy': 'descending mentions, then alphabetical ticker',
            'settings': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}}
    archive = out_dir / 'comments.jsonl'
    try:
        write_metadata(out_dir, meta)
        meta['provenance'] = provenance()
        if args.input:
            meta['source_sha256'] = file_hash(args.input)
            source = iter_comments(args.input)
        else:
            reddit = connect()
            print(f'Reading r/{", r/".join(args.subreddits)}...')
            source = fetch_comments(reddit, args, warnings)

        # Persist both new and replayed comments before analysis. A later failure keeps this archive.
        with archive.open('w', encoding='utf-8') as saved:
            for comment in source:
                saved.write(json.dumps(comment, ensure_ascii=False) + '\n')
                saved.flush()
                comments.append(comment)
        meta['input_sha256'] = file_hash(archive)
        if args.input:
            print(f'Loaded {len(comments)} comments from {args.input}')

        mentions, texts = count_mentions(comments, ignore_authors=set(args.ignore_authors))
        rows = []
        if mentions:
            analyzer = make_analyzer()
            lexicon = json.dumps(analyzer.lexicon, sort_keys=True).encode('utf-8')
            meta['provenance']['lexicon_sha256'] = hashlib.sha256(lexicon).hexdigest()
            rows = summarize(mentions, texts, analyzer, top=args.sentiment_top)
        n_posts = len({c['post_id'] for c in comments if c.get('post_id')})
        print_report(mentions, rows, args.top, len(comments), n_posts, time.monotonic() - start)
        meta.update(comments=len(comments), posts=n_posts)
        save_results(out_dir, mentions, rows, args.top, meta)
        if mentions:
            save_charts(out_dir, mentions, rows, args.top, args.show)
        meta.update(status='partial' if warnings else 'complete', finished=utc_now(),
                    elapsed_seconds=round(time.monotonic() - start, 3))
        write_metadata(out_dir, meta)
    except (Exception, KeyboardInterrupt, SystemExit) as exc:
        meta.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                    finished=utc_now(), comments=len(comments),
                    error=f'{type(exc).__name__}: {exc}')
        try:
            if archive.exists():
                meta['input_sha256'] = file_hash(archive)
            write_metadata(out_dir, meta)
        except OSError:
            pass
        print(f'Run stopped: {exc or type(exc).__name__}. Saved progress: {out_dir}', file=sys.stderr)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1
    print(f'\nSaved results to {out_dir}/')
    if warnings:
        print('Some extra comments could not be loaded; see warnings in run.json.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
