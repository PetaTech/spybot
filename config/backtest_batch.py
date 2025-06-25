"""
Analytics Configuration
Fine-tune parameters for strategy optimization
"""

# === Optimization Settings ===
SEARCH_TYPE = "grid"  # Only grid search mode
MAX_COMBINATIONS = 10000  # Reduced for focused testing of most impactful parameters
SAVE_RESULTS = True
TOP_N_RESULTS = 10  # Show top 10 results

# === Data Processing Settings ===
DATA_FOLDER = "data"
MAX_WORKERS = None  # Use CPU cores - 1
MEMORY_LIMIT_MB = 1000
SAFETY_ROW_LIMIT = 5000  # Reduced safety limit

# === Fine-Tune Parameters for Grid Search ===
# Focused on the MOST IMPACTFUL parameters for VIX-based strategy optimization
TUNABLE_PARAMETERS = {
    # VIX-Based Strategy Parameters (CORE - MOST IMPACTFUL)
    'VIX_THRESHOLD': [20, 25, 30],  # Test different VIX regime thresholds
    
    # High Volatility Parameters (CORE - MOST IMPACTFUL)
    'HIGH_VOL_MOVE_THRESHOLD': [3.0, 3.5, 4.0],      # SPY move thresholds for high VIX
    'HIGH_VOL_PROFIT_TARGET': [1.25, 1.35, 1.45],    # Profit targets for high VIX
    
    # Low Volatility Parameters (CORE - MOST IMPACTFUL)
    'LOW_VOL_MOVE_THRESHOLD': [2.0, 2.5, 3.0],       # SPY move thresholds for low VIX
    'LOW_VOL_PROFIT_TARGET': [1.25, 1.35, 1.45],     # Profit targets for low VIX
    
    # Core Strategy Parameters (HIGHEST IMPACT)
    'COOLDOWN_PERIOD': [15 * 60, 20 * 60, 25 * 60],  # Trade frequency (15, 20, 25 min)
    'RISK_PER_SIDE': [300, 400, 500],                 # Position sizing
    
    # Risk Management (HIGHEST IMPACT)
    'STOP_LOSS_PERCENTAGE': [30.0, 50.0, 70.0],       # Stop loss thresholds
}

# === Fixed Parameters (These will NOT be changed during optimization) ===
FIXED_PARAMETERS = {
    'symbol', 'interval', 'expiration_days', 'LOG_DIR', 'MODE',
    'BASE_DIR', 'REPLAY_DATE', 'SPY_PATH', 'OPT_PATH',
    'INITIAL_CAPITAL', 'COMMISSION_PER_CONTRACT', 'SLIPPAGE',
    'LOG_LEVEL', 'MARKET_OPEN', 'MARKET_CLOSE', 'TIMEZONE',
    'REFERENCE_PRICE_TYPE', 'MAX_RETRIES', 'RETRY_DELAY', 'MAX_ENTRY_TIME',
    'OPTION_ASK_MIN', 'OPTION_ASK_MAX', 'OPTION_BID_ASK_RATIO',  # Fixed option filtering
    'MAX_DAILY_TRADES', 'MAX_DAILY_LOSS', 'EMERGENCY_STOP_LOSS',  # Fixed risk management
    'MARKET_OPEN_BUFFER_MINUTES', 'MARKET_CLOSE_BUFFER_MINUTES',  # Fixed timing
    'EARLY_SIGNAL_COOLDOWN_MINUTES', 'PRICE_WINDOW_SECONDS',  # Fixed timing
    'MAX_HOLD_SECONDS',  # Fixed hold time
    'HIGH_VOL_PREMIUM_MIN', 'HIGH_VOL_PREMIUM_MAX',  # Fixed VIX premium ranges
    'LOW_VOL_PREMIUM_MIN', 'LOW_VOL_PREMIUM_MAX',  # Fixed VIX premium ranges
}

# === Output Settings ===
LOG_LEVEL = 'INFO' 