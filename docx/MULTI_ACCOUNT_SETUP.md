# Multi-Account Trading Setup Guide

## 🚀 **Multi-Account Architecture Complete!**

The SPYBot now supports **10+ Tradier accounts** with:
- ✅ **Single shared data feed** (1-second polling from one account)
- ✅ **Independent signal processing** per account (each account has different strategy configs)
- ✅ **Both live/paper credentials** per account (switch modes easily)
- ✅ **Strategy overrides** per account (inherit from `config/strategy.py`, override as needed)
- ✅ **Separate telegram bots** per account (isolated notifications)
- ✅ **Separate logging** per account (`logs/accounts/account_name.log`)
- ✅ **Health monitoring** and auto-restart
- ✅ **Global risk management** (optional)
- ✅ **Single entry point** (`python start.py live` or `python start.py paper`)

---

## 📋 **Setup Steps**

### 1. **Configure Accounts**
Edit `config/accounts.py`:

**NEW FORMAT: Each account has BOTH live and paper credentials**

```python
ACCOUNTS = [
    {
        'name': 'Account_1',
        'enabled': True,

        # Live Trading Credentials
        'live': {
            'account_id': 'YOUR_LIVE_ACCOUNT_ID_1',
            'access_token': 'YOUR_LIVE_ACCESS_TOKEN_1'
        },

        # Paper Trading Credentials
        'paper': {
            'account_id': 'YOUR_PAPER_ACCOUNT_ID_1',
            'access_token': 'YOUR_PAPER_ACCESS_TOKEN_1'
        },

        # Strategy Overrides (optional)
        'strategy_overrides': {
            'RISK_PER_SIDE': 500,        # Override default 400
            'MAX_DAILY_TRADES': 3,       # Override default 5
            'STOP_LOSS_PERCENTAGE': 15.0 # Override default 12.0
        },

        # Telegram Bot (each account gets own bot)
        'telegram': {
            'bot_token': 'YOUR_BOT_TOKEN_1',
            'chat_id': 'YOUR_CHAT_ID_1',
            'enabled': True
        },

        # Logging
        'logging': {
            'log_prefix': 'account1',
            'log_level': 'INFO'
        }
    },

    {
        'name': 'Account_2',
        'enabled': True,

        # Live Trading Credentials
        'live': {
            'account_id': 'YOUR_LIVE_ACCOUNT_ID_2',
            'access_token': 'YOUR_LIVE_ACCESS_TOKEN_2'
        },

        # Paper Trading Credentials
        'paper': {
            'account_id': 'YOUR_PAPER_ACCOUNT_ID_2',
            'access_token': 'YOUR_PAPER_ACCESS_TOKEN_2'
        },

        'strategy_overrides': {
            'RISK_PER_SIDE': 300,         # Conservative settings
            'MAX_DAILY_TRADES': 2,
            'STOP_LOSS_PERCENTAGE': 10.0
        },

        'telegram': {
            'bot_token': 'YOUR_BOT_TOKEN_2',
            'chat_id': 'YOUR_CHAT_ID_2',
            'enabled': True
        },

        'logging': {
            'log_prefix': 'account2_conservative',
            'log_level': 'INFO'
        }
    },

    # Add up to 10+ more accounts...
]
```

**Key Changes:**
- Each account now has **both** `live` and `paper` credential sections
- When you run `python start.py live`, it uses the `live` credentials
- When you run `python start.py paper`, it uses the `paper` credentials
- Same account, same strategy overrides, just different credentials!
- **API URLs are constants** - no need to repeat them for each account:
  - Live: `https://api.tradier.com/v1` (automatically used)
  - Paper: `https://sandbox.tradier.com/v1` (automatically used)

### 2. **Setup Telegram Bots**
Each account needs its own telegram bot:

1. **Create Bot**: Message `@BotFather` on Telegram → `/newbot` → get token
2. **Get Chat ID**: Message your bot, then visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. **Add to Config**: Put `bot_token` and `chat_id` in account config

### 3. **Configure Strategy Defaults**
Edit `config/strategy.py` for default settings:
```python
RISK_PER_SIDE = 400          # Default risk per account
MAX_DAILY_TRADES = 5         # Default daily trade limit
STOP_LOSS_PERCENTAGE = 12.0  # Default stop loss
# ... etc
```

### 4. **Run Multi-Account Trading**

**NEW SINGLE ENTRY POINT:**

```bash
# Start paper trading (safe testing)
python start.py paper

# Start live trading (real money)
python start.py live
```

**No more separate live.py and paper.py files!**

---

## 🏗️ **Architecture Flow**

```
[Tradier Account A] ──┐
                      ├─→ SharedDataProvider (1-sec polling)
[Tradier Account B] ──┘                │
                                       │
                      ┌────────────────┴────────────────┐
                      │                                 │
                      ▼                                 ▼
            AccountManager[A]                 AccountManager[B]
            ├─ TradingEngine[A]               ├─ TradingEngine[B]
            ├─ Strategy Config A              ├─ Strategy Config B
            ├─ Independent Signals            ├─ Independent Signals
            ├─ TelegramBot[A]                 ├─ TelegramBot[B]
            └─ Logs[A]                        └─ Logs[B]
```

**Key Points:**
- **One data feed** shared across all accounts (efficient API usage)
- **Independent signal processing** per account (different configs = different signals)
- **Isolated notifications** per account (separate telegram groups)
- **Separate logging** per account (easy debugging)

---

## ⚙️ **Strategy Override Examples**

### Conservative Account:
```python
'strategy_overrides': {
    'RISK_PER_SIDE': 300,           # Lower risk
    'MAX_DAILY_TRADES': 2,          # Fewer trades
    'STOP_LOSS_PERCENTAGE': 8.0,    # Tighter stop loss
    'VIX_THRESHOLD': 25             # Only trade in low VIX
}
```

### Aggressive Account:
```python
'strategy_overrides': {
    'RISK_PER_SIDE': 800,           # Higher risk
    'MAX_DAILY_TRADES': 15,         # More trades
    'STOP_LOSS_PERCENTAGE': 20.0,   # Looser stop loss
    'COOLDOWN_PERIOD': 10 * 60      # Shorter cooldown
}
```

### Testing Account:
```python
'strategy_overrides': {
    'RISK_PER_SIDE': 100,           # Small risk for testing
    'MAX_DAILY_TRADES': 50,         # Lots of trades
    'COOLDOWN_PERIOD': 5 * 60,      # 5 min cooldown
    'STOP_LOSS_PERCENTAGE': 30.0    # Very loose for learning
}
```

---

## 📊 **Monitoring & Logs**

### Account-Specific Logs:
```
logs/accounts/
├── live_acc1.log         # Live Account 1
├── paper_acc1.log        # Paper Account 1
├── live_acc2_conservative.log
└── paper_acc2_aggressive.log
```

### Central Orchestration Log:
```
logs/multi_account_manager.log   # Startup, errors, coordination
```

### Real-Time Monitoring:
- **Console Output**: Live status updates every 10 minutes
- **Telegram Notifications**: Per-account trade alerts
- **Health Checks**: Auto-restart failed accounts
- **Global Risk**: Emergency shutdown if total loss exceeds limits

---

## 🔧 **Advanced Features**

### Global Risk Management:
```python
# In config/accounts.py
GLOBAL_RISK = {
    'enabled': True,
    'max_total_daily_loss': 5000,      # Combined loss across all accounts
    'max_total_open_positions': 50,    # Combined open positions
    'emergency_shutdown_loss': 10000   # Emergency stop
}
```

### Health Monitoring:
```python
ORCHESTRATION = {
    'startup_delay_between_accounts': 2,   # Stagger account startups
    'health_check_interval': 30,           # Check every 30 seconds
    'auto_restart_failed_accounts': True,  # Auto-restart on failure
    'max_account_restart_attempts': 3      # Max restart tries
}
```

---

## 🎯 **Usage Examples**

### Test with Paper Mode:
```bash
python start.py paper
```

### Go Live:
```bash
python start.py live
```

### Switch Between Modes:
```bash
# Same accounts, same configs, different credentials
python start.py paper   # Uses paper credentials
python start.py live    # Uses live credentials
```

### Test Setup:
```bash
# 1. Configure both live and paper credentials for each account
# 2. Test with: python start.py paper
# 3. When confident, switch to: python start.py live
```

---

## 🚨 **Important Notes**

1. **API Limits**: Only ONE account polls for data (shared feed) - efficient!
2. **Strategy Independence**: Each account processes same data with different configs
3. **Telegram Isolation**: Each account gets own bot/chat - no message mixing
4. **Log Separation**: Each account logs separately - easy debugging
5. **Fail-Safe**: If one account fails, others continue running
6. **Global Shutdown**: Emergency stop if combined losses exceed limits

---

## ✅ **Ready to Trade!**

The multi-account system is production-ready with:
- **Robust error handling** and auto-recovery
- **Comprehensive logging** and monitoring
- **Flexible configuration** with strategy overrides
- **Isolated notifications** per account
- **Global risk management** for safety

**Start with paper accounts first, then gradually enable live accounts!** 🚀