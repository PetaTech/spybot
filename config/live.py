"""
Live Trading Configuration
Settings for live trading with real money
"""

# Import strategy parameters
from .strategy import *

# === API Configuration ===
TRADIER_API_URL = 'https://api.tradier.com/v1'
TRADIER_ACCESS_TOKEN = 'gHHlnkRTiQEcyMIW2qGDIGZnKQMM'
ACCOUNT_ID = '6YB57635'

# === Logging ===
LOG_LEVEL = 'INFO'
LOG_DIR = 'logs' 