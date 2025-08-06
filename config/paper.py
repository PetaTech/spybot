"""
Paper Trading Configuration
Settings for paper trading with sandbox environment
"""

# Import strategy parameters
from .strategy import *

# === API Configuration ===
TRADIER_API_URL = 'https://sandbox.tradier.com/v1'
TRADIER_ACCESS_TOKEN = 'vZkJpiR828SUs7nO02B0MQ4VmXhd'
ACCOUNT_ID = 'VA32928735'

# === Logging ===
LOG_LEVEL = 'INFO'
LOG_DIR = 'logs'