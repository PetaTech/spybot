"""
Backtest Configuration
Settings for historical backtesting
"""

# Import strategy parameters
from .strategy import *

# === Data Configuration ===
SPY_PATH = f"./data/spy_data_2025-05-30_2025-05-30_1min.parquet"
OPT_PATH = f"./data/spy_options_0dte_contracts_2025-05-30_2025-05-30_1min.parquet"

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