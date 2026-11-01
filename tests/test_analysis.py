from analysis import count_mentions, find_tickers, ranked_mentions, score_comment, summarize
from data import blacklist, new_words, tickers


def comments(*pairs):
    return [{'author': a, 'body': b} for a, b in pairs]


# --- finding tickers -------------------------------------------------------------------

def test_tickers_next_to_punctuation_and_line_breaks_are_found():
    assert find_tickers("GME, TSLA. AMC! (PLTR) NIO\nBB $NOK's") == {'GME', 'TSLA', 'AMC', 'PLTR', 'NIO', 'BB', 'NOK'}


def test_cashtags_work_in_any_case():
    assert find_tickers('loading up on $gme and $Tsla') == {'GME', 'TSLA'}


def test_bare_words_must_be_capitals():
    assert find_tickers('gme tsla') == set()


def test_common_words_count_only_as_cashtags():
    assert find_tickers('GOOD CASH YOLO AI') == set()
    assert find_tickers('$CASH $AI') == {'CASH', 'AI'}


def test_single_letters_count_only_as_cashtags():
    assert find_tickers('press F to pay respects') == set()
    assert find_tickers('$F looks cheap') == {'F'}


def test_letters_inside_longer_words_are_ignored():
    assert find_tickers('GMEs and McDonald and TSLA2 and $GME$') == set()


def test_tickers_inside_urls_do_not_count():
    assert find_tickers('https://example.com/GME www.example.com/TSLA HTTPS://example.com/$AMC') == set()
    assert find_tickers('Buy GME https://example.com/TSLA') == {'GME'}
    assert find_tickers('[GME](https://example.com/TSLA)') == {'GME'}


def test_etfs_and_recent_listings_are_known():
    assert {'AMC', 'SPY', 'QQQ', 'RIVN', 'HOOD'} <= tickers


def test_blacklist_entries_are_all_real_tickers():
    assert blacklist <= tickers


# --- counting --------------------------------------------------------------------------

def test_repeated_ticker_does_not_drop_the_rest_of_the_comment():
    mentions, _ = count_mentions(comments(('alice', 'GME'), ('alice', 'GME TSLA')))
    assert mentions == {'GME': 1, 'TSLA': 1}


def test_ticker_repeated_inside_one_comment_counts_once():
    mentions, texts = count_mentions(comments(('bob', 'GME GME TSLA')))
    assert mentions == {'GME': 1, 'TSLA': 1}
    assert len(texts['GME']) == 1


def test_each_author_counts_once_per_ticker():
    mentions, texts = count_mentions(comments(('alice', 'GME'), ('alice', 'GME!'), ('bob', 'GME')))
    assert mentions['GME'] == 2
    assert texts['GME'] == [['GME', 'GME!'], ['GME']]


def test_author_names_and_ignored_authors_are_case_insensitive():
    mentions, _ = count_mentions(
        comments(('Alice', 'GME'), ('alice', 'GME'), ('automoderator', 'TSLA')),
        ignore_authors={'AutoModerator'},
    )
    assert mentions == {'GME': 1}


def test_repeated_comment_ids_do_not_duplicate_contributors_or_sentiment():
    rows = [
        {'comment_id': 'one', 'author': None, 'body': 'GME'},
        {'comment_id': 'one', 'author': None, 'body': 'GME'},
        {'comment_id': 'two', 'author': 'alice', 'body': 'GME'},
        {'comment_id': 'two', 'author': 'alice', 'body': 'GME'},
        {'comment_id': 'three', 'author': 'alice', 'body': 'GME!'},
    ]
    mentions, texts = count_mentions(rows)
    assert mentions == {'GME': 2}
    assert texts['GME'] == [['GME'], ['GME', 'GME!']]


def test_missing_or_empty_comment_ids_do_not_merge_distinct_comments():
    rows = comments((None, 'GME'), (None, 'GME'))
    rows.extend({'comment_id': '', 'author': None, 'body': 'GME'} for _ in range(2))
    assert count_mentions(rows)[0]['GME'] == 4


def test_tied_rankings_use_alphabetical_order_regardless_of_input_order():
    rows = comments(('a', 'TSLA GME AMC'), ('b', 'PLTR'))
    assert ranked_mentions(count_mentions(rows)[0], 3) == [('AMC', 1), ('GME', 1), ('PLTR', 1)]
    assert ranked_mentions(count_mentions(reversed(rows))[0], 3) == [('AMC', 1), ('GME', 1), ('PLTR', 1)]
    assert ranked_mentions({'TSLA': 3, 'AMC': 1, 'GME': 3}) == [('GME', 3), ('TSLA', 3), ('AMC', 1)]


def test_deleted_authors_are_not_mixed_up_with_the_previous_author():
    mentions, _ = count_mentions(comments(('alice', 'GME'), (None, 'GME is great'), (None, 'GME again')))
    assert mentions['GME'] == 3


def test_deleted_author_first_does_not_skip_later_comments():
    mentions, _ = count_mentions(comments((None, 'GME'), ('carol', 'TSLA'), ('dan', 'AMC')))
    assert mentions == {'GME': 1, 'TSLA': 1, 'AMC': 1}


def test_ignored_authors_are_skipped():
    mentions, _ = count_mentions(comments(('AutoModerator', 'GME'), ('bob', 'TSLA')), ignore_authors={'AutoModerator'})
    assert mentions == {'TSLA': 1}


# --- sentiment -------------------------------------------------------------------------

def test_scores_stay_in_range_and_ticker_is_not_a_bonus(analyzer):
    assert score_comment(analyzer, '$GME 🚀🚀🚀', 'GME') == 0.0
    assert score_comment(analyzer, 'GME to the moon', 'GME') == score_comment(analyzer, 'moon GME', 'GME')
    for text in ['GME to the moon', 'GME is a scam', 'GME']:
        assert -1.0 <= score_comment(analyzer, text, 'GME') <= 1.0


def test_negation_is_kept(analyzer):
    assert score_comment(analyzer, 'Not bullish on GME at all', 'GME') < 0
    assert score_comment(analyzer, 'I would never buy GME, total scam', 'GME') < 0
    assert score_comment(analyzer, 'GME is not good', 'GME') < 0


def test_each_ticker_is_scored_on_its_own_sentence(analyzer):
    body = 'Sell TSLA, it is a scam. Buy GME, going to the moon!'
    assert score_comment(analyzer, body, 'TSLA') < 0 < score_comment(analyzer, body, 'GME')


def test_ticker_symbols_are_not_read_as_words(analyzer):
    # RIOT and LOVE are tickers that VADER would otherwise score as sentiment words
    assert score_comment(analyzer, '$RIOT', 'RIOT') == 0.0
    assert score_comment(analyzer, '$LOVE', 'LOVE') == 0.0


def test_links_are_removed_before_scoring(analyzer):
    assert score_comment(analyzer, 'GME https://example.com/terrible-awful-scam', 'GME') == 0.0


def test_url_only_mentions_do_not_receive_unrelated_sentiment(analyzer):
    assert score_comment(analyzer, 'What a terrible scam https://example.com/GME', 'GME') == 0.0
    assert score_comment(analyzer, 'TSLA is amazing', 'GME') == 0.0


def test_masking_keeps_original_capitalization_emphasis(analyzer):
    assert score_comment(analyzer, 'GME IS AMAZING', 'GME') == analyzer.polarity_scores('GME IS AMAZING')['compound']
    assert score_comment(analyzer, '$gme IS AMAZING', 'GME') > score_comment(analyzer, 'GME IS AMAZING', 'GME')


def test_author_sentiment_includes_all_comments_and_is_order_independent(analyzer):
    rows = comments(('alice', 'GME is great'), ('alice', 'GME is a scam'))
    mentions, texts = count_mentions(rows)
    result = summarize(mentions, texts, analyzer)
    assert result == summarize(*count_mentions(reversed(rows)), analyzer)
    expected = (score_comment(analyzer, rows[0]['body'], 'GME')
                + score_comment(analyzer, rows[1]['body'], 'GME')) / 2
    assert result[0]['mentions'] == 1
    assert result[0]['mean_score'] == round(expected, 3)


def test_frequent_authors_have_equal_weight_in_sentiment(analyzer):
    rows = comments(('alice', 'GME is great'), ('alice', 'GME is great'), ('bob', 'GME is a scam'))
    (row,) = summarize(*count_mentions(rows), analyzer)
    expected = (score_comment(analyzer, 'GME is great', 'GME')
                + score_comment(analyzer, 'GME is a scam', 'GME')) / 2
    assert row['mentions'] == 2
    assert row['mean_score'] == round(expected, 3)
    assert (row['positive'], row['neutral'], row['negative']) == (0.5, 0, 0.5)


def test_sentiment_selection_uses_the_same_tie_breaker_as_mentions(analyzer):
    rows = comments(('a', 'TSLA GME AMC'), ('b', 'PLTR'))
    assert [row['ticker'] for row in summarize(*count_mentions(rows), analyzer, top=2)] == ['AMC', 'GME']


def test_summary_shares_add_up(analyzer):
    mentions, texts = count_mentions(comments(('a', 'GME to the moon'), ('b', 'GME is a scam'), ('c', 'GME')))
    (row,) = summarize(mentions, texts, analyzer, top=5)
    assert row['mentions'] == 3
    assert abs(row['positive'] + row['neutral'] + row['negative'] - 1) < 0.01
    assert (row['positive'], row['neutral'], row['negative']) == (0.333, 0.333, 0.333)


def test_lexicon_typos_fixed():
    assert 'squeeze' in new_words and 'hindenburg' in new_words
    assert 'squezze' not in new_words and 'hidenburg' not in new_words
