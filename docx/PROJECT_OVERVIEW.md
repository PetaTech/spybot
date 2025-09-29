### SPY Multi-Account Trading Bot - Project Overview for Cursor

### Project Purpose

This is a sophisticated Python-based algorithmic trading bot designed to trade SPY (S&P 500 ETF) options using momentum breakout strategies. The bot supports backtesting, paper trading, and live trading modes with comprehensive risk management and multi-account orchestration.

### Project Architecture

#### Core Components

1. Multi-Account Trading Manager (`core/multi_account_trading.py`)
   - Orchestrates multiple trading accounts simultaneously
   - Each account processes the same market data independently for signal generation
   - Handles account health monitoring, restarts, and telegram notifications
   - Main entry point: `python start.py [live|paper]`
2. Trading Engine (`core/trading_engine.py`)
   - Pure data-driven engine that processes market data row-by-row
   - Implements VIX-based momentum breakout strategy
   - Handles signal detection, trade execution, position management
   - Supports backtest, paper, and live trading modes
3. Account Manager (`core/account_manager.py`)
   - Manages individual trading accounts
   - Wraps `TradingEngine` with account-specific configuration
   - Handles health checks, restarts, and account status
4. Shared Data Provider (`core/shared_data_provider.py`)
   - Fetches real-time SPY price data from Tradier API
   - Broadcasts data to all account managers
   - Handles data collection, error handling, and health monitoring
5. Telegram Notification System
   - `utils/multi_account_telegram.py`: Multi-account telegram manager
   - `utils/telegram_bot.py`: Individual telegram notifier
   - Each account has its own telegram bot for isolated notifications

### Trading Strategy

VIX-Based Momentum Breakout Strategy:
- Signal Detection: 30-minute rolling window price breakouts
- VIX Adaptive Thresholds:
  - High volatility (VIX > 25): 3.5 point threshold, 2.35x profit target
  - Low volatility (VIX ≤ 25): 2.5 point threshold, 2.25x profit target
- Entry Conditions: Price moves above rolling high/low, market timing checks
- Exit Conditions: 2.25-2.35x profit targets or 50% stop loss
- Risk Management: $400 per trade, max 5 trades/day, max $1000 daily loss

### Configuration System

1. Core Strategy (`config/strategy.py`)
   - Base strategy parameters shared across all modes
   - VIX thresholds, risk management, market timing
2. Account Configuration (`config/accounts.py`)
   - Multi-account setup with live/paper credentials
   - Strategy overrides per account
   - Telegram configuration per account
   - Account enabling/disabling
3. Mode-Specific Configs
   - `config/backtest_single.py`: Single backtest parameters
   - `config/backtest_batch.py`: Batch optimization settings

### Key Files and Functions

Main Entry Points:
- `start.py`: Multi-account live/paper trading
- `backtest_single.py`: Single backtest execution
- `backtest_batch.py`: Batch optimization and analytics

Critical Methods:
- `TradingEngine.process_row()`: Main data processing logic
- `TradingEngine.should_detect_signal()`: Signal detection algorithm
- `AccountManager.process_market_data()`: Account-level data handling
- `MultiAccountManager.stop()`: Graceful shutdown with telegram alerts

### Data Flow

1. `SharedDataProvider` fetches SPY price data from Tradier API
2. Data broadcasts to all registered `AccountManager` subscribers
3. Each `AccountManager` processes data through its `TradingEngine`
4. `TradingEngine` analyzes price movements for breakout signals
5. Signal detection triggers option selection and trade execution
6. Position management handles profit targets, stop losses, and exits
7. Telegram notifications sent for all significant events

### Recent Changes and Current State

**Telegram System Migration:**
- Migrated from individual engine telegram to multi-account telegram system
- `TradingEngine` telegram disabled for live/paper (only backtest uses it)
- `MultiAccountTelegramManager` handles all notifications for live/paper trading

**Health Check Improvements:**
- Enhanced health checks to not fail during market closure
- Prevents unnecessary restarts outside trading hours (9:30 AM - 4:00 PM ET)

**Shutdown Process:**
- Fixed telegram alerts during bot shutdown
- Proper signal handling for Ctrl+C with graceful shutdown
- Data provider stops first to prevent race conditions during shutdown

**Key Issues Resolved:**
- Health check restart loops outside market hours
- Missing telegram notifications during shutdown
- Confusing signal handler messages (now shows "Ctrl+C pressed" instead of "signal 2")
- Final trading results spam during account restarts

### Dependencies

**Core Libraries:**
- pandas: Data manipulation and analysis
- requests: HTTP API calls to Tradier
- python-dateutil, pytz: Timezone and datetime handling
- duckdb, pyarrow: High-performance data storage for backtesting
- yfinance: VIX data fetching

**API Integration:**
- Tradier API: Live/paper trading, market data, option chains
- Telegram Bot API: Real-time notifications

### Running the Bot

Live/Paper Trading:
```
python start.py paper  # Safe testing with sandbox
python start.py live   # Real money trading (requires confirmation)
```

Backtesting:
```
python backtest_single.py  # Single backtest
python backtest_batch.py   # Parameter optimization
```

### Important Notes for Development

1. Multi-Account Architecture: The bot is designed to run multiple accounts simultaneously with shared data feed but independent signal generation.
2. Telegram Integration: Each account has its own telegram bot configuration. The `MultiAccountTelegramManager` handles all notifications for live/paper mode.
3. Health Monitoring: Accounts are monitored for health and automatically restarted if they fail (with limits to prevent infinite restart loops).
4. Risk Management: Multiple layers of protection including per-trade limits, daily limits, emergency stops, and market timing restrictions.
5. Data Efficiency: Uses DuckDB and Parquet for high-performance backtesting with large datasets.
6. Error Handling: Comprehensive error handling with retry logic for API calls and graceful degradation.

This bot is production-ready with extensive logging, monitoring, and safety features. The codebase follows clean architecture principles with separation of concerns between data providers, trading logic, account management, and notification systems.


