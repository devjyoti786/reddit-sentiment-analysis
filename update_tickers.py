'''Rebuild the supported stock and ETF symbols from NASDAQ Trader's directory.

Only plain, one-to-five-letter symbols are supported. Common partnership units
and ETFs are included; warrants, rights, preferred shares and bundled units are not.

    python3 update_tickers.py
'''

import os
import re
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCES = {
    'nasdaqlisted': 'https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt',
    'otherlisted': 'https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt',
}
OUT_FILE = Path(__file__).with_name('tickers.txt')

# plain symbols only: drops preferreds, classes and when-issued forms such as BRK.B or ABR$D
SYMBOL = re.compile(r'^[A-Z]{1,5}$')
# Match instrument descriptions, rather than any occurrence of "preferred" or "units".
# ETF metadata takes precedence: a fund holding preferred shares is still an ETF.
SKIP_INSTRUMENTS = re.compile(
    r'\b(?:warrants?|rights?)\b|\b(?:preferred|preference)\s+(?:stocks?|shares?|units?|securities|class|series)\b'
    r'|\bnotes?\s+due\b', re.I
)
BUNDLED_UNITS = re.compile(
    r'\s-\s+units?\b|\bunits?\s*[,()]?\s*(?:each\s+)?consist(?:ing|s)\b'
    r'|\b(?:tangible equity|corporate)\s+units?\b', re.I
)


def download(url):
    '''Download a complete directory, rejecting changed schemas or truncated responses.'''
    with urllib.request.urlopen(url, timeout=30) as resp:
        lines = resp.read().decode('utf-8').splitlines()
    if not lines:
        raise ValueError(f'Empty symbol directory: {url}')
    header = lines[0].split('|')
    required = {'Security Name', 'Test Issue', 'ETF'}
    symbol_key = 'Symbol' if 'Symbol' in header else 'ACT Symbol'
    if (not required.union({symbol_key}).issubset(header)
            or len(header) != len(set(header))):
        raise ValueError(f'Unexpected symbol directory header: {url}')
    rows = []
    complete = False
    for line_number, line in enumerate(lines[1:], start=2):
        if line.startswith('File Creation Time'):
            complete = True
            break
        fields = line.split('|')
        if len(fields) != len(header):
            raise ValueError(f'Malformed directory row at {url}:{line_number}')
        row = dict(zip(header, fields))
        if (not row[symbol_key] or not row['Security Name']
                or row['ETF'] not in {'Y', 'N'} or row['Test Issue'] not in {'Y', 'N'}):
            raise ValueError(f'Invalid directory fields at {url}:{line_number}')
        rows.append(row)
    if not complete or not rows:
        raise ValueError(f'Incomplete or empty symbol directory: {url}')
    return rows


def keep(symbol, row):
    '''Keep ordinary equities/common units and ETFs, excluding unsupported instruments.'''
    if not SYMBOL.fullmatch(symbol) or row.get('Test Issue') == 'Y':
        return False
    if row.get('ETF') == 'Y':
        return True
    name = row.get('Security Name', '')
    return not (SKIP_INSTRUMENTS.search(name) or BUNDLED_UNITS.search(name))


def write_symbols(symbols, destination):
    '''Replace the snapshot only after a complete nonempty file has been written.'''
    if not symbols or any(not SYMBOL.fullmatch(s) for s in symbols):
        raise ValueError('Refusing to replace the ticker snapshot with empty or invalid symbols')
    header = (
        f'# Supported US stock and ETF symbols from NASDAQ Trader, '
        f'{datetime.now(timezone.utc).date().isoformat()}\n'
        '# Regenerate with: python3 update_tickers.py\n'
    )
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=destination.parent,
                                         prefix=f'.{destination.name}.', delete=False) as f:
            temporary = Path(f.name)
            f.write(header + '\n'.join(sorted(symbols)) + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    symbols = set()
    for name, url in SOURCES.items():
        rows = download(url)
        key = 'Symbol' if name == 'nasdaqlisted' else 'ACT Symbol'
        kept = {row[key] for row in rows if keep(row[key], row)}
        if not kept:
            raise ValueError(f'No supported symbols in {name}; existing snapshot was not changed')
        print(f'{name}: {len(rows)} rows, kept {len(kept)}')
        symbols |= kept

    write_symbols(symbols, OUT_FILE)
    print(f'wrote {len(symbols)} symbols to {OUT_FILE.name}')


if __name__ == '__main__':
    main()
