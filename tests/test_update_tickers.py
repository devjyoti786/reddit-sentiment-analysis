'''Offline checks for ticker classification and safe snapshot replacement.'''

from io import BytesIO

import pytest

import update_tickers as updater


@pytest.mark.parametrize('symbol,name,etf', [
    ('ET', 'Energy Transfer LP Common Units', 'N'),
    ('AB', 'AllianceBernstein Holding L.P. Units', 'N'),
    ('PFF', 'iShares Preferred and Income Securities ETF', 'Y'),
    ('PFFD', 'Global X U.S. Preferred ETF', 'Y'),
    ('PGX', 'Invesco Preferred ETF', 'Y'),
    ('PFXF', 'VanEck Preferred Securities ex Financials ETF', 'Y'),
    ('PFBC', 'Preferred Bank - Common Stock', 'N'),
])
def test_common_units_and_funds_are_kept(symbol, name, etf):
    assert updater.keep(symbol, {'Security Name': name, 'ETF': etf, 'Test Issue': 'N'})


@pytest.mark.parametrize('symbol,name', [
    ('AACIU', 'Armada Acquisition Corp. III - Units'),
    ('UNITX', 'Example Units, each consisting of one share and one warrant'),
    ('ABCW', 'Example Corp. - Warrants'),
    ('ABCR', 'Example Corp. - Rights'),
    ('ABCP', 'Example Corp. - Series A Preferred Stock'),
    ('CHSCN', 'CHS Inc - Preferred Class B Series 2 Reset Rate'),
    ('BTSGU', 'BrightSpring Health Services, Inc. - Tangible Equity Unit'),
    ('DUKU', 'Duke Energy Corporation Corporate Units'),
    ('NOTES', 'Example Corp. 5% Notes due 2030'),
    ('BRK.B', 'Berkshire Hathaway Class B'),
])
def test_unsupported_instruments_are_excluded(symbol, name):
    assert not updater.keep(symbol, {'Security Name': name, 'ETF': 'N', 'Test Issue': 'N'})


def test_test_issues_are_excluded_even_when_etfs():
    assert not updater.keep('TEST', {'Security Name': 'Test ETF', 'ETF': 'Y', 'Test Issue': 'Y'})


def mock_directory(monkeypatch, content):
    monkeypatch.setattr(updater.urllib.request, 'urlopen', lambda *a, **k: BytesIO(content.encode()))


def test_download_validates_and_parses_complete_directory(monkeypatch):
    mock_directory(monkeypatch, 'Symbol|Security Name|Test Issue|ETF\n'
                               'GME|GameStop Common Stock|N|N\nFile Creation Time: timestamp|||\n')
    assert updater.download('https://example.test/feed') == [
        {'Symbol': 'GME', 'Security Name': 'GameStop Common Stock', 'Test Issue': 'N', 'ETF': 'N'}
    ]


@pytest.mark.parametrize('content', [
    '',
    '<html>Service unavailable</html>',
    'Symbol|Security Name|Test Issue|ETF\nFile Creation Time: timestamp|||\n',
    'Symbol|Security Name|Test Issue|ETF\nGME|GameStop|N|N\n',  # missing completeness footer
    'Symbol|Security Name|Test Issue|ETF\nGME|GameStop|N\nFile Creation Time: timestamp|||\n',
    'Symbol|Security Name|Test Issue|ETF\nGME|GameStop|N|unknown\nFile Creation Time: timestamp|||\n',
])
def test_download_rejects_empty_truncated_or_malformed_content(monkeypatch, content):
    mock_directory(monkeypatch, content)
    with pytest.raises(ValueError):
        updater.download('https://example.test/feed')


def test_failed_second_source_preserves_previous_snapshot(monkeypatch, tmp_path):
    destination = tmp_path / 'tickers.txt'
    destination.write_text('previous snapshot\n')
    monkeypatch.setattr(updater, 'OUT_FILE', destination)

    def download(url):
        if 'otherlisted' in url:
            raise ValueError('Truncated response')
        return [{'Symbol': 'GME', 'Security Name': 'GameStop', 'ETF': 'N', 'Test Issue': 'N'}]

    monkeypatch.setattr(updater, 'download', download)
    with pytest.raises(ValueError, match='Truncated'):
        updater.main()
    assert destination.read_text() == 'previous snapshot\n'


def test_failed_atomic_replace_preserves_snapshot_and_cleans_temp(monkeypatch, tmp_path):
    destination = tmp_path / 'tickers.txt'
    destination.write_text('previous snapshot\n')

    def failed_replace(*args):
        raise OSError('simulated disk error')

    monkeypatch.setattr(updater.os, 'replace', failed_replace)
    with pytest.raises(OSError, match='disk error'):
        updater.write_symbols({'GME'}, destination)
    assert destination.read_text() == 'previous snapshot\n'
    assert list(tmp_path.iterdir()) == [destination]


def test_empty_snapshot_cannot_replace_existing_file(tmp_path):
    destination = tmp_path / 'tickers.txt'
    destination.write_text('previous snapshot\n')
    with pytest.raises(ValueError, match='empty'):
        updater.write_symbols(set(), destination)
    assert destination.read_text() == 'previous snapshot\n'


def test_snapshot_is_written_in_sorted_order(tmp_path):
    destination = tmp_path / 'tickers.txt'
    updater.write_symbols({'TSLA', 'GME'}, destination)
    assert destination.read_text().splitlines()[2:] == ['GME', 'TSLA']
