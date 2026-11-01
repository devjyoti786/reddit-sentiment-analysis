'''Tests for the Reddit-facing part of the script, using fake PRAW objects (no network).'''

import json
from types import SimpleNamespace as NS

import pytest
from praw.models import MoreComments


class FakeForest(list):
    def __init__(self, items, fail=False):
        super().__init__(items)
        self.fail = fail

    def replace_more(self, limit=32):
        if self.fail and limit:
            raise RuntimeError('413 Request Entity Too Large')
        self[:] = [c for c in self if not isinstance(c, MoreComments)]
        return []

    def list(self):
        out = []
        for c in self:
            out.append(c)
            out.extend(getattr(c, 'replies', []))
        return out


def comment(author, body, score=10, replies=()):
    return NS(id=body[:8], author=NS(name=author) if author else None, body=body, score=score,
              created_utc=0, replies=list(replies))


def post(items, author='op', flair='Daily Discussion', fail=False, title='Daily thread'):
    return NS(id='p1', title=title, author=NS(name=author) if author else None, link_flair_text=flair,
              upvote_ratio=0.9, ups=100, comment_sort=None, comments=FakeForest(items, fail))


def fetch(app, posts, *extra):
    reddit = NS(subreddit=lambda name: NS(hot=lambda limit: iter(posts)))
    return list(app.fetch_comments(reddit, app.parse_args(list(extra))))


def test_post_by_deleted_account_does_not_crash(app):
    got = fetch(app, [post([comment('a', 'GME')], author=None)])
    assert [c['body'] for c in got] == ['GME']


def test_replies_are_included(app):
    got = fetch(app, [post([comment('a', 'GME', replies=[comment('b', 'TSLA reply')])])])
    assert [c['body'] for c in got] == ['GME', 'TSLA reply']


def test_deleted_comment_author_becomes_none(app):
    got = fetch(app, [post([comment('a', 'GME'), comment(None, 'TSLA')])])
    assert [c['author'] for c in got] == ['a', None]


def test_failed_load_more_keeps_the_comments_already_loaded(app, capsys):
    got = fetch(app, [post([comment('a', 'GME'), MoreComments(None, {'count': 5, 'children': []})], fail=True)])
    assert [c['body'] for c in got] == ['GME']
    assert 'could not load extra comments' in capsys.readouterr().out


def test_post_and_comment_filters(app):
    posts = [post([comment('a', 'GME')], flair='Meme'),
             post([comment('a', 'low score', score=2), comment('b', 'kept', score=3)])]
    assert [c['body'] for c in fetch(app, posts)] == ['kept']


def test_run_from_saved_comments_writes_results_and_charts(app, tmp_path):
    saved = tmp_path / 'comments.jsonl'
    rows = [{'post_id': 'p', 'author': f'u{i}', 'body': b}
            for i, b in enumerate(['GME to the moon!', 'TSLA is a scam', 'GME calls', 'not bullish on TSLA'])]
    saved.write_text('\n'.join(json.dumps(r) for r in rows))
    assert app.main(['--input', str(saved), '--output', str(tmp_path / 'out')]) == 0
    (run,) = (tmp_path / 'out').iterdir()
    assert {p.name for p in run.iterdir()} == {
        'comments.jsonl', 'mentions.csv', 'sentiment.csv', 'run.json', 'mentions.png', 'sentiment.png'}
    assert 'GME,2' in (run / 'mentions.csv').read_text()
    assert app.load_comments(run / 'comments.jsonl') == rows
    meta = json.loads((run / 'run.json').read_text())
    assert meta['status'] == 'complete'
    assert meta['author'] == 'Devjyoti'
    assert meta['source_sha256'] == app.file_hash(saved)
    assert meta['input_sha256'] == app.file_hash(run / 'comments.jsonl')
    assert 'lexicon_sha256' in meta['provenance']


def test_run_with_no_tickers_does_not_crash(app, tmp_path, capsys):
    saved = tmp_path / 'comments.jsonl'
    saved.write_text(json.dumps({'post_id': 'p', 'author': 'u', 'body': 'nothing here'}))
    app.main(['--input', str(saved), '--output', str(tmp_path / 'out')])
    assert 'No tickers found.' in capsys.readouterr().out


def test_missing_credentials_give_a_clear_message(app, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)                       # no praw.ini here
    for key in ('praw_client_id', 'praw_client_secret', 'praw_user_agent'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))         # and none in the user config folder
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    with pytest.raises(SystemExit, match='praw.ini'):
        app.connect()


@pytest.mark.parametrize('flags', [
    ['--top', '0'], ['--top', '-1'], ['--sentiment-top', '0'], ['--posts', '0'],
    ['--more', '-1'], ['--min-upvote-ratio', '-0.1'], ['--min-upvote-ratio', '1.1'],
    ['--min-upvote-ratio', 'nan'], ['--min-upvote-ratio', 'inf'],
])
def test_invalid_numeric_options_are_rejected(app, flags):
    with pytest.raises(SystemExit) as exc:
        app.parse_args(flags)
    assert exc.value.code == 2


def test_sentiment_selection_is_limited_to_mention_selection(app):
    args = app.parse_args(['--top', '1', '--sentiment-top', '5', '--more', '0'])
    assert args.sentiment_top == 1
    assert args.more == 0


@pytest.mark.parametrize('record, message', [
    ('not json', 'invalid JSON'),
    ('[]', 'JSON object'),
    ('{"author":"a"}', 'body must be a string'),
    ('{"body":null}', 'body must be a string'),
    ('{"body":"GME","author":[]}', 'author must be a string or null'),
    ('{"body":"GME","post_id":[]}', 'post_id must be a string or null'),
    ('{"body":"GME","comment_id":4}', 'comment_id must be a string or null'),
])
def test_input_validation_includes_filename_and_line(app, tmp_path, record, message):
    path = tmp_path / 'bad.jsonl'
    path.write_text('\n' + record)
    with pytest.raises(ValueError) as exc:
        app.load_comments(path)
    assert f'{path}:2:' in str(exc.value)
    assert message in str(exc.value)


def test_runs_with_same_clock_do_not_overwrite_each_other(app, monkeypatch, tmp_path):
    from datetime import datetime, timezone

    class FrozenClock:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 11, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(app, 'datetime', FrozenClock)
    source = tmp_path / 'comments.jsonl'
    source.write_text('{"author":"a","body":"no tickers here"}')
    output = tmp_path / 'out'
    for _ in range(2):
        assert app.main(['--input', str(source), '--output', str(output)]) == 0
    runs = list(output.iterdir())
    assert len(runs) == 2
    assert all((run / 'comments.jsonl').exists() for run in runs)


def test_api_failure_preserves_already_fetched_comments(app, monkeypatch, tmp_path):
    saved_comment = {'post_id': 'p', 'author': 'a', 'body': 'GME'}

    def broken_fetch(reddit, args, warnings=None):
        yield saved_comment
        raise RuntimeError('connection lost')

    monkeypatch.setattr(app, 'connect', lambda: object())
    monkeypatch.setattr(app, 'fetch_comments', broken_fetch)
    assert app.main(['--output', str(tmp_path / 'out')]) == 1
    (run,) = (tmp_path / 'out').iterdir()
    assert app.load_comments(run / 'comments.jsonl') == [saved_comment]
    meta = json.loads((run / 'run.json').read_text())
    assert meta['status'] == 'failed'
    assert meta['comments'] == 1
    assert 'connection lost' in meta['error']


def test_partial_comment_fetch_is_recorded(app, monkeypatch, tmp_path):
    reddit = NS(subreddit=lambda name: NS(hot=lambda limit: iter([
        post([comment('a', 'nothing here')], fail=True)
    ])))
    monkeypatch.setattr(app, 'connect', lambda: reddit)
    assert app.main(['--output', str(tmp_path / 'out')]) == 0
    (run,) = (tmp_path / 'out').iterdir()
    meta = json.loads((run / 'run.json').read_text())
    assert meta['status'] == 'partial'
    assert meta['warnings'][0]['post_id'] == 'p1'


def test_invalid_later_input_line_preserves_valid_records(app, tmp_path):
    source = tmp_path / 'comments.jsonl'
    source.write_text('{"body":"GME"}\nnot-json\n')
    assert app.main(['--input', str(source), '--output', str(tmp_path / 'out')]) == 1
    (run,) = (tmp_path / 'out').iterdir()
    assert app.load_comments(run / 'comments.jsonl') == [{'body': 'GME'}]
    assert json.loads((run / 'run.json').read_text())['status'] == 'failed'


def test_demo_and_version_do_not_need_credentials(app, capsys):
    args = app.parse_args(['--demo'])
    assert args.input.is_file()
    with pytest.raises(SystemExit) as exc:
        app.parse_args(['--version'])
    assert exc.value.code == 0
    assert 'Devjyoti' in capsys.readouterr().out


def test_demo_cannot_be_combined_with_input(app):
    with pytest.raises(SystemExit):
        app.parse_args(['--demo', '--input', 'comments.jsonl'])
