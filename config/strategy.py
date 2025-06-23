"""
Strategy Configuration
Core strategy parameters shared across all trading modes
"""

# === Core Strategy Parameters ===
MOVE_THRESHOLD_PERCENT = 0.4  # 0.4% minimum price move to trigger entry (replaces fixed 2.50)
MOVE_THRESHOLD_MIN_POINTS = 3.0  # Minimum absolute move in points (safety floor)
MOVE_THRESHOLD_MAX_POINTS = 20.0  # Maximum absolute move in points (safety ceiling)
REFERENCE_PRICE_TYPE = 'window_high_low'  # 'open', 'prev_close', 'vwap', 'window_high_low'
COOLDOWN_PERIOD = 20 * 60  # 20 minutes between trades
RISK_PER_SIDE = 400  # $ risk per side
OPTION_TARGET_MULTIPLIER = 2.35  # Exit at 2.35x entry price
MAX_RETRIES = 6  # Maximum retries for option chain fetching
RETRY_DELAY = 5  # Seconds between retries
PRICE_WINDOW_SECONDS = 30 * 60  # 30 minutes rolling window
MAX_ENTRY_TIME = '15:00'  # Stop entering after 3 PM
MIN_PROFIT_PERCENTAGE = 30.0  # Minimum 30% profit to exit (instead of fixed 50%)

# === Option Filtering Parameters ===
OPTION_ASK_MIN = 0.5  # Minimum ask price for valid options
OPTION_ASK_MAX = 347.33  # Maximum ask price for valid options
OPTION_BID_ASK_RATIO = 0.5  # ask must be > bid * 0.5

# === Risk Management Parameters ===
MAX_DAILY_TRADES = 5  # Maximum trades per day
MAX_DAILY_LOSS = 1000  # $1000 max daily loss
EMERGENCY_STOP_LOSS = 2000  # $2000 emergency stop loss
STOP_LOSS_PERCENTAGE = 12.0  # Exit if loss exceeds 12% of entry cost
MAX_HOLD_SECONDS = 3600  # 1 hour max hold time for any trade

# === Market Hours ===
MARKET_OPEN = '09:30'
MARKET_CLOSE = '16:00'
TIMEZONE = 'America/New_York'

# === Market Timing Parameters (Theta Decay Management) ===
MARKET_OPEN_BUFFER_MINUTES = 15  # Wait 15 minutes after market open before trading
MARKET_CLOSE_BUFFER_MINUTES = 15  # Force exit 15 minutes before market close
EARLY_SIGNAL_COOLDOWN_MINUTES = 30  # Cooldown period if signal occurs before open buffer 