'''Ticker extraction, mention counting and sentiment scoring.

Nothing in this module talks to Reddit, so it can be tested with plain strings.
A comment is a dict with at least 'author' (str, or None for deleted accounts) and 'body'.
'''

import re
from collections import Counter, defaultdict
from math import fsum

from data import blacklist, new_words, tickers

# optional "$", then 1-5 letters that are not glued to other letters, digits or "$"
TICKER_RE = re.compile(r'(?<![\w$])(\$?)([A-Za-z]{1,5})(?![\w$])')
URL_RE = re.compile(r'https?://\S+|www\.\S+', re.IGNORECASE)
SENTENCE_RE = re.compile(r'(?<=[.!?])\s+|\n+')

POSITIVE, NEGATIVE = 0.05, -0.05     # VADER's usual cut-offs for a positive / negative text


def _as_ticker(cashtag, word):
    '''Return the ticker a regex match stands for, or None if it isn't one.'''
    if cashtag:                                 # "$gme", "$CASH", "$F": explicit, always counts
        symbol = word.upper()
        return symbol if symbol in tickers else None
    if (word.isupper() and len(word) > 1        # bare words must be in capitals: "GME", not "gme"
            and word in tickers and word not in blacklist):
        return word
    return None


def find_tickers(text):
    '''Return tickers mentioned outside URLs; link destinations are not mentions.'''
    found = set()
    for cashtag, word in TICKER_RE.findall(URL_RE.sub('', text)):
        symbol = _as_ticker(cashtag, word)
        if symbol:
            found.add(symbol)
    return found


def ranked_mentions(mentions, top=None):
    '''Rank by count descending, breaking ties alphabetically for reproducible runs.'''
    ranked = sorted(mentions.items(), key=lambda item: (-item[1], item[0]))
    return ranked if top is None else ranked[:max(0, top)]


def count_mentions(comments, ignore_authors=frozenset()):
    '''Count contributors and retain all their comments for equal-author scoring.

    Known authors contribute once per ticker, regardless of how often they post.
    Each deleted-author comment is a separate contributor because its author cannot
    be identified. Repeated nonempty string comment IDs are included only once.

    Return: mentions: Counter ticker -> number of contributors
            texts: dict ticker -> list of contributor groups, each a list of bodies
    '''
    mentions = Counter()
    texts = defaultdict(list)
    groups = {}                                 # (author, ticker) -> that author's bodies
    seen_ids = set()
    ignored = {author.casefold() for author in ignore_authors if isinstance(author, str)}
    for comment in comments:
        author = comment.get('author')
        author_key = author.casefold() if author is not None else None
        if author_key in ignored or (author is None and None in ignore_authors):
            continue
        comment_id = comment.get('comment_id')
        if isinstance(comment_id, str) and comment_id:
            if comment_id in seen_ids:
                continue
            seen_ids.add(comment_id)
        for symbol in sorted(find_tickers(comment['body'])):
            key = (author_key, symbol)
            if author is not None and key in groups:
                groups[key].append(comment['body'])
                continue
            group = [comment['body']]
            if author is not None:
                groups[key] = group
            mentions[symbol] += 1
            texts[symbol].append(group)
    return mentions, texts


def make_analyzer():
    '''Return a VADER analyzer with the WSB words added, downloading VADER's lexicon if needed.'''
    import nltk
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    try:
        nltk.data.find('sentiment/vader_lexicon.zip')
    except LookupError:
        nltk.download('vader_lexicon', quiet=True)
    analyzer = SentimentIntensityAnalyzer()
    analyzer.lexicon.update(new_words)
    return analyzer


def _mask_tickers(text):
    '''Replace counted tickers with a neutral word so "$RIOT" or "$LOVE" aren't read as sentiment.'''
    def repl(match):
        if not _as_ticker(*match.groups()):
            return match.group(0)
        word = match.group(2)
        # Preserve VADER's all-caps/mixed-case distinction when removing symbols.
        return 'TICKER' if word.isupper() else 'ticker' if word.islower() else 'Ticker'
    return TICKER_RE.sub(repl, text)


def score_comment(analyzer, body, symbol):
    '''VADER compound score (-1 to 1) of the sentences in body that mention symbol.

    Whole sentences are scored, so negation ("not bullish"), capitals and "!" still count.
    Sentences that do not explicitly mention the symbol do not contribute, even
    when they use pronouns referring to it. With no matching sentence, return 0.
    '''
    text = URL_RE.sub('', body)
    sentences = [s for s in SENTENCE_RE.split(text) if symbol in find_tickers(s)]
    if not sentences:
        return 0.0
    scores = [analyzer.polarity_scores(_mask_tickers(s))['compound'] for s in sentences]
    return fsum(scores) / len(scores)


def summarize(mentions, texts, analyzer, top=5):
    '''Summarize contributor sentiment, averaging each author's comments first.

    Positive/neutral/negative shares classify contributor averages, not individual
    comments. Each contributor has equal weight; deleted accounts count per comment.
    '''
    rows = []
    for symbol, count in ranked_mentions(mentions, top):
        scores = [fsum(score_comment(analyzer, body, symbol) for body in group) / len(group)
                  for group in texts[symbol]]
        n = len(scores)
        rows.append({
            'ticker': symbol,
            'mentions': count,
            'mean_score': round(fsum(scores) / n, 3),
            'positive': round(sum(s >= POSITIVE for s in scores) / n, 3),
            'neutral': round(sum(NEGATIVE < s < POSITIVE for s in scores) / n, 3),
            'negative': round(sum(s <= NEGATIVE for s in scores) / n, 3),
        })
    return rows
