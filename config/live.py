"""
Live Trading Configuration
Settings for live trading with real money
"""

# Import strategy parameters
from .strategy import *

# === API Configuration ===
TRADIER_API_URL = 'https://api.tradier.com/v1'
TRADIER_ACCESS_TOKEN = 'bcuTwm0ocPZja7J2L159sBNnGHBT'
ACCOUNT_ID = '6YB57979'

# === Logging ===
LOG_LEVEL = 'INFO'
LOG_DIR = 'logs' 