"""
Analytics Configuration
Fine-tune parameters for strategy optimization
"""

# === Optimization Settings ===
SEARCH_TYPE = "grid"  # Only grid search mode
MAX_COMBINATIONS = 10  # Small number for testing
SAVE_RESULTS = True
TOP_N_RESULTS = 5

# === Data Processing Settings ===
DATA_FOLDER = "data"
MAX_WORKERS = None  # Use CPU cores - 1
MEMORY_LIMIT_MB = 1000
SAFETY_ROW_LIMIT = 5000  # Reduced safety limit

# === Fine-Tune Parameters for Grid Search ===
# These are the parameters that will be varied in the optimization
# Small parameter sets for testing

TUNABLE_PARAMETERS = {
    # Core strategy parameters (small sets for testing)
    'COOLDOWN_PERIOD': [20 * 60],  # minutes in seconds
    'RISK_PER_SIDE': [400],
    'OPTION_TARGET_MULTIPLIER': [2.35],
    'MIN_PROFIT_PERCENTAGE': [30.0],
    'MAX_HOLD_SECONDS': [3600],  # 1hr
    'STOP_LOSS_PERCENTAGE': [12.0],
    
    # Option filtering parameters (small sets)
    'OPTION_ASK_MIN': [0.5],
    'OPTION_ASK_MAX': [300.0],
    'OPTION_BID_ASK_RATIO': [0.5],
    
    # Risk management (small sets)
    'MAX_DAILY_TRADES': [5],
    'MAX_DAILY_LOSS': [1000],
    'EMERGENCY_STOP_LOSS': [2000],
    
    # Market timing (small sets)
    'MARKET_OPEN_BUFFER_MINUTES': [15],
    'MARKET_CLOSE_BUFFER_MINUTES': [15],
    'EARLY_SIGNAL_COOLDOWN_MINUTES': [30],
    
    # Price window (small sets)
    'PRICE_WINDOW_SECONDS': [30 * 60]  # 30min
}

# === Fixed Parameters (These will NOT be changed during optimization) ===
FIXED_PARAMETERS = {
    'symbol', 'interval', 'expiration_days', 'LOG_DIR', 'MODE',
    'BASE_DIR', 'REPLAY_DATE', 'SPY_PATH', 'OPT_PATH',
    'INITIAL_CAPITAL', 'COMMISSION_PER_CONTRACT', 'SLIPPAGE',
    'LOG_LEVEL', 'MARKET_OPEN', 'MARKET_CLOSE', 'TIMEZONE',
    'REFERENCE_PRICE_TYPE', 'MAX_RETRIES', 'RETRY_DELAY', 'MAX_ENTRY_TIME'
}

# === Output Settings ===
RESULTS_FILENAME = "analytics_results.csv"
LOG_LEVEL = 'INFO' 