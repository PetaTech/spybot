"""
Strategy Configuration
Core strategy parameters shared across all trading modes
"""

# === Core Strategy Parameters ===
REFERENCE_PRICE_TYPE = 'window_high_low'  # 'open', 'prev_close', 'vwap', 'window_high_low'
COOLDOWN_PERIOD = 20 * 60  # 20 minutes between trades
RISK_PER_SIDE = 400  # $ risk per side
MAX_RETRIES = 6  # Maximum retries for option chain fetching
RETRY_DELAY = 5  # Seconds between retries
PRICE_WINDOW_SECONDS = 30 * 60  # 30 minutes rolling window
MAX_ENTRY_TIME = '15:00'  # Stop entering after 3 PM

# === Option Filtering Parameters ===
OPTION_ASK_MIN = 0.5  # Minimum ask price for valid options
OPTION_ASK_MAX = 300.0  # Maximum ask price for valid options
OPTION_BID_ASK_RATIO = 0.5  # ask must be > bid * 0.5

# === Risk Management Parameters ===
MAX_DAILY_TRADES = 500000  # Maximum trades per day
MAX_DAILY_LOSS = 1000  # $1000 max daily loss
EMERGENCY_STOP_LOSS = 2000  # $2000 emergency stop loss
STOP_LOSS_PERCENTAGE = 50.0  # Exit if loss exceeds 50% of entry cost

# === Market Hours ===
MARKET_OPEN = '09:30'
MARKET_CLOSE = '16:00'
TIMEZONE = 'America/New_York'

# === Market Timing Parameters (Theta Decay Management) ===
MARKET_OPEN_BUFFER_MINUTES = 15  # Wait 15 minutes after market open before trading
MARKET_CLOSE_BUFFER_MINUTES = 60  # Force exit 15 minutes before market close
EARLY_SIGNAL_COOLDOWN_MINUTES = 30  # Cooldown period if signal occurs before open buffer

# === VIX-Based Volatility Strategy Parameters ===
VIX_THRESHOLD = 25  # VIX value to distinguish high vs low volatility

# High Volatility Parameters
HIGH_VOL_MOVE_THRESHOLD = 3.5  # SPY price move threshold for high volatility
HIGH_VOL_PREMIUM_MIN = 1.05    # Min option premium for high volatility
HIGH_VOL_PREMIUM_MAX = 2.20    # Max option premium for high volatility
HIGH_VOL_PROFIT_TARGET = 1.35  # 135% profit target for high volatility

# Low Volatility Parameters
LOW_VOL_MOVE_THRESHOLD = 2.5   # SPY price move threshold for low volatility
LOW_VOL_PREMIUM_MIN = 0.40    # Min option premium for low volatility
LOW_VOL_PREMIUM_MAX = 1.05    # Max option premium for low volatility
LOW_VOL_PROFIT_TARGET = 1.35  # 135% profit target for low volatility 