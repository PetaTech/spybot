"""
Telegram Bot Configuration
Settings for Telegram notifications
"""

# === Telegram Bot Configuration ===
TELEGRAM_BOT_TOKEN = "8352695755:AAFblmWmOYRUnWC36yjPxGVu9vKU7fljg7k"  # Get from @BotFather on Telegram
TELEGRAM_CHAT_ID = "6529748739"     # Your chat ID or group chat ID
TELEGRAM_ENABLED = True                     # Set to False to disable notifications

# === Notification Settings ===
SEND_SIGNAL_ALERTS = True      # Signal detection alerts
SEND_ENTRY_ALERTS = True       # Trade entry alerts  
SEND_EXIT_ALERTS = True        # Trade exit alerts
SEND_LIMIT_HIT_ALERTS = True   # Limit order fill alerts
SEND_STOP_LOSS_ALERTS = True   # Stop loss alerts
SEND_DAILY_LIMIT_ALERTS = True # Daily limit warnings
SEND_SYSTEM_ALERTS = True      # Bot start/stop alerts

# === Message Format Settings ===
TIMEZONE_DISPLAY = "US/Eastern"  # Timezone for alert timestamps
INCLUDE_ACCOUNT_NAME = True       # Include account holder name in alerts
DETAILED_POSITION_INFO = True     # Include detailed position information