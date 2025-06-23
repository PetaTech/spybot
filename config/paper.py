"""
Paper Trading Configuration
Settings for paper trading with sandbox environment
"""

# Import strategy parameters
from .strategy import *

# === API Configuration ===
TRADIER_API_URL = 'https://sandbox.tradier.com/v1'
TRADIER_ACCESS_TOKEN = 'EpBD3Tx9hM9EfBqpTaAVsrJfXjkA'
ACCOUNT_ID = 'VA60323101'

# === Logging ===
LOG_LEVEL = 'INFO'
LOG_DIR = 'logs' 