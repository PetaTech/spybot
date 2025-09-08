"""
Backtest Configuration
Settings for historical backtesting
"""

# Import strategy parameters
from .strategy import *

# === Backtest Specific Settings ===
INITIAL_CAPITAL = 12000
COMMISSION_PER_CONTRACT = 0.65  # $0.65 per contract
SLIPPAGE = 0.01  # 1 cent slippage per option

# === Backtest Performance Settings ===
# Override retry settings for faster backtesting
MAX_RETRIES = 6  # Same as live/paper modes
RETRY_DELAY = 0  # No delay for faster backtesting (overrides strategy.py)

# === VIX Static Mode for Backtest ===
STATIC_VIX_MODE = True  # If True, use STATIC_VIX_VALUE for VIX in backtest
STATIC_VIX_VALUE = 20.0  # Static VIX value to use when STATIC_VIX_MODE is enabled

# === Logging ===
LOG_LEVEL = 'INFO'
LOG_DIR = 'logs' 