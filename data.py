'''Ticker list, blacklist and WSB lexicon used by the analysis.

tickers.txt holds the supported US stock and ETF symbols (refresh with update_tickers.py).
'''

from pathlib import Path

TICKER_FILE = Path(__file__).with_name('tickers.txt')

tickers = frozenset(
    line.strip() for line in TICKER_FILE.read_text(encoding='utf-8').splitlines()
    if line.strip() and not line.startswith('#')
)

# Symbols that are also everyday English or WSB slang. A bare word in capitals from this
# list is NOT counted ("GOOD", "CASH", "YOLO"); written as a cashtag ("$CASH") it is.
# Single-letter symbols are never counted without a "$" either.
blacklist = frozenset('''
    ACT ACTS AD ADAM AGO AI AIM AIR ALL AM AN APP ARE ARM ARMS ARMY AS ASIA AT AWAY BALL BAND BAR
    BAY BBC BE BEAT BEN BILL BIRD BIT BOAT BOND BOX BULL BY CAKE CALM CAMP CAN CAR CARD CARE CARS
    CASH CAST CAT CENT CFO CHAT CLUB COLD COOK COOL COPY COST CPU CRY CTO CUT DAN DC DD DE DEC DEEP
    DOG DON DOW DRUG DUTY EASY EAT ED EDGE EDIT EGGS EL EOD EPS EU EVER EYE EYES FACT FAN FAST FIVE
    FIX FLAG FLOW FLY FOR FORM FOUR FOX FT FUN FUND GAIN GAME GIFT GLAD GO GOLD GOLF GOOD GRAB GROW
    HARD HAS HE HELP HERE HERO HIDE HIGH HIS HIT HODL HOLD HOPE HOST HOUR HQ ICE III IMO INFO IP IPO
    IQ IRON IRS IT ITM JACK JAN JOB JOE JUST KEY KIDS KIM KNOW LAKE LAND LAW LEE LIFE LINE LINK LIVE
    LOAN LOT LOVE LOW LUCK MA MADE MAIN MAN MAR MASS MATE MAX MET MILK MIND MINE MOVE MS MUST NEAR
    NECK NET NEXT NICE NINE NOV NOW OCT ON ONTO OPEN OR OUT OWN PACK PARK PATH PAY PC PDT PICK PINK
    PLAY PLUS PM POOL POST PR PRAY PRE PS PUMP PUSH RACE RAIN RARE REAL RENT RH RING RISE ROAD ROCK
    ROPE RULE RUN RYAN SAFE SAM SAN SEA SEAT SEEM SELF SEMI SEPT SHE SHIP SHOP SHOT SITE SIZE SKIN
    SKY SNOW SO SON SOUL SPOT ST STEP SUB SURE TASK TAX TD TEAM TECH TEN TEND TEST TILL TIME TINY
    TIP TLDR TOP TOS TOUR TOWN TREE TRIP TV UK UN UNIT UP USA USD USE VIA VOTE VS WANT WAR WAVE WAY
    WEEK WELL WEST WING WISE WOOD WTF YEAR YOLO YOU ZONE
'''.split())

# WSB vocabulary added to VADER's lexicon. Scores run from -4.0 (very negative) to 4.0
# (very positive). Words that mean different things in different contexts (put, call,
# short, long, high, low, way, big...) are left out on purpose.
new_words = {
    'citron': -4.0,
    'hindenburg': -4.0,
    'moon': 4.0,
    'mooning': 4.0,
    'rocket': 2.2,
    'calls': 2.0,
    'puts': -2.0,
    'buy': 2.5,
    'sell': -2.5,
    'bullish': 3.7,
    'bearish': -3.7,
    'bull': 2.5,
    'bear': -2.5,
    'tendie': 2.0,
    'tendies': 2.0,
    'stonk': 1.9,
    'squeeze': 3.0,
    'highs': 2.0,
    'green': 1.9,
    'red': -1.9,
    'print': 2.2,
    'undervalued': 3.0,
    'overvalued': -3.0,
    'upgrade': 3.0,
    'downgrade': -3.0,
    'rebound': 1.5,
    'drop': -2.5,
    'offering': -2.3,
    'bagholder': -1.7,
    'bagholding': -1.7,
    'gtfo': -1.7,
    'paper': -1.7,
    'rip': -4.0,
    'scam': -2.0,
    'snake': -2.0,
    'sus': -3.0,
    'cult': -1.0,
}
