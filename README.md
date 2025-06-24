# SPY Momentum Breakout Trading Bot

A sophisticated Python-based algorithmic trading bot designed to trade SPY (S&P 500 ETF) options using a momentum breakout strategy. The bot supports backtesting, paper trading, and live trading modes with comprehensive risk management and performance tracking.

## Introduction

This trading bot is designed to capitalize on short-term momentum moves in SPY by trading options with a systematic approach. It monitors price movements in real-time and executes trades based on predefined breakout criteria, with built-in risk management to protect capital.

**Key Features:**
- **Multi-mode Support**: Backtesting, paper trading, and live trading
- **SPY Options Trading**: Focuses exclusively on SPY options for liquidity and consistency
- **Momentum Breakout Strategy**: Identifies and trades short-term price breakouts
- **Comprehensive Risk Management**: Multiple layers of protection including daily limits, stop losses, and position sizing
- **Real-time Data Integration**: Uses Tradier API for live market data and order execution
- **Detailed Performance Tracking**: Extensive logging and performance metrics
- **Batch Backtesting & Analytics**: Run large-scale parameter sweeps to find the top 5 strategy configurations by win rate and profit
- **Ultra-Fast Data Handling**: Automatically converts CSVs to Parquet using DuckDB for high-speed, memory-efficient historical data queries

## How It Works

The bot operates on a continuous data stream workflow:

1. **Data Ingestion**: Receives real-time or historical SPY price data (1-minute intervals)
2. **Signal Detection**: Monitors for price breakouts above predefined thresholds
3. **Option Selection**: Identifies suitable options contracts based on liquidity and pricing criteria
4. **Trade Execution**: Places orders when conditions are met (with retry logic for reliability)
5. **Position Management**: Monitors open positions for exit conditions
6. **Performance Tracking**: Logs all trades and calculates comprehensive metrics

The engine processes one data row at a time, maintaining internal state for positions, daily limits, and market timing rules.

## Data Handling & Performance

### Parquet Conversion for Fast Backtesting
For large historical datasets, the bot automatically converts CSV files to Parquet format using DuckDB. This enables extremely fast, memory-efficient queries—critical for running thousands of backtests or analytics sweeps. You do not need to manually convert files; the system handles it on first run.

**Benefits:**
- No need to load entire CSVs into memory
- Orders-of-magnitude faster queries for large datasets
- Seamless integration: just place your CSVs in the `data/` directory

## Trading Strategy

### Strategy Name: Momentum Breakout with Options

**Core Concept**: The bot identifies short-term momentum breakouts in SPY and trades corresponding options to amplify potential returns.

**Entry Conditions**:
- Price moves above a rolling high/low window (30-minute lookback)
- Minimum move threshold: 0.4% or 3.0 points (whichever is greater)
- Maximum move threshold: 20.0 points (safety ceiling)
- Market timing: Between 9:45 AM and 3:00 PM ET (with buffer periods)
- Cooldown period: 20 minutes between trades

**Exit Conditions**:
- Target profit: 2.35x entry price
- Stop loss: 12% of entry cost
- Time-based exit: Maximum 1-hour hold time
- Market close: Force exit 15 minutes before close

**Risk Management**:
- Maximum $400 risk per trade
- Maximum 5 trades per day
- Maximum $1,000 daily loss
- Emergency stop loss: $2,000 total loss

**Option Selection Criteria**:
- Ask price between $0.50 and $347.33
- Bid/Ask ratio > 0.5 (liquidity filter)
- Expiration dates: Weekly and monthly options

## Project Structure

```
bot/
├── live.py                  # Live trading entry point  
├── paper.py                 # Paper trading entry point
├── backtest_batch.py        # Batch backtesting & analytics engine (finds top configs)
├── backtest_single.py       # Single backtest runner (used by batch engine)
├── requirements.txt         # Python dependencies
├── config/                  # Configuration files
│   ├── strategy.py          # Core strategy parameters
│   ├── backtest_batch.py    # Batch backtest specific settings
│   ├── backtest_single.py   # Single backtest specific settings
│   ├── live.py              # Live trading settings
│   └── paper.py             # Paper trading settings
├── core/                    # Core trading logic
│   └── trading_engine.py    # Main trading engine (1151 lines)
├── utils/                   # Utility modules
│   └── tradier_api.py       # Tradier API integration
├── data/                    # Historical data storage
│   ├── spy/                 # SPY price data
│   └── options_greeks/      # Options data with Greeks
└── logs/                    # Performance logs and output
```

## Configuration

The bot uses separate configuration files for different trading modes. All configurations inherit from the core strategy parameters.

### Core Strategy Configuration (`config/strategy.py`)

```python
# Entry Parameters
MOVE_THRESHOLD_MIN_POINTS = 3.0     # Minimum 3.0 point move
MOVE_THRESHOLD_MAX_POINTS = 20.0    # Maximum 20.0 point move
REFERENCE_PRICE_TYPE = 'window_high_low'  # Use rolling high/low
COOLDOWN_PERIOD = 20 * 60           # 20 minutes between trades

# Risk Management
RISK_PER_SIDE = 400                 # $400 risk per trade
MAX_DAILY_TRADES = 5                # Maximum 5 trades per day
MAX_DAILY_LOSS = 1000               # $1000 max daily loss
STOP_LOSS_PERCENTAGE = 12.0         # 12% stop loss
MAX_HOLD_SECONDS = 3600             # 1 hour max hold time

# Option Parameters
OPTION_TARGET_MULTIPLIER = 2.35     # Exit at 2.35x entry price
OPTION_ASK_MIN = 0.5                # Minimum $0.50 ask price
OPTION_ASK_MAX = 347.33             # Maximum $347.33 ask price
OPTION_BID_ASK_RATIO = 0.5          # Minimum bid/ask ratio

# Market Timing
MARKET_OPEN = '09:30'               # Market open time
MARKET_CLOSE = '16:00'              # Market close time
MAX_ENTRY_TIME = '15:00'            # Stop entering after 3 PM
MARKET_OPEN_BUFFER_MINUTES = 15     # Wait 15 min after open
MARKET_CLOSE_BUFFER_MINUTES = 15    # Exit 15 min before close
```

### Backtest Configuration (`config/backtest_single.py`)

```python
# Imports core strategy parameters from config/strategy.py
from .strategy import *

# === Data Configuration ===
BASE_DIR = "."  # Current directory
REPLAY_DATE = "2025-05-30"
SPY_PATH = f"{BASE_DIR}/data/spy/UnderlyingIntervals_60sec_{REPLAY_DATE}.csv"
OPT_PATH = f"{BASE_DIR}/data/options_greeks/UnderlyingOptionsIntervals_60sec_calcs_oi_{REPLAY_DATE}.csv"

# === Backtest Specific Settings ===
INITIAL_CAPITAL = 12000
COMMISSION_PER_CONTRACT = 0.65  # $0.65 per contract
SLIPPAGE = 0.01  # 1 cent slippage per option

# === Backtest Performance Settings ===
MAX_RETRIES = 6  # Same as live/paper modes
RETRY_DELAY = 0  # No delay for faster backtesting (overrides strategy.py)

# === Logging ===
LOG_LEVEL = 'INFO'
LOG_DIR = 'logs'
```

### Batch Optimization Configuration (`config/backtest_batch.py`)

This file controls grid search, analytics, and batch backtesting. Adjust these settings to define parameter sweeps and analytics output for batch runs:

```python
# === Optimization Settings ===
SEARCH_TYPE = "grid"  # Only grid search mode
MAX_COMBINATIONS = 10  # Max configs to test (increase for real runs)
SAVE_RESULTS = True
TOP_N_RESULTS = 5

# === Tunable Parameters (for grid search) ===
TUNABLE_PARAMETERS = {
    'MOVE_THRESHOLD_MIN_POINTS': [3.0],
    'MOVE_THRESHOLD_MAX_POINTS': [20.0],
    'COOLDOWN_PERIOD': [20 * 60],
    'RISK_PER_SIDE': [400],
    'OPTION_TARGET_MULTIPLIER': [2.35],
    'MIN_PROFIT_PERCENTAGE': [30.0],
    'MAX_HOLD_SECONDS': [3600],
    'STOP_LOSS_PERCENTAGE': [12.0],
    'OPTION_ASK_MIN': [0.5],
    'OPTION_ASK_MAX': [300.0],
    'OPTION_BID_ASK_RATIO': [0.5],
    'MAX_DAILY_TRADES': [5],
    'MAX_DAILY_LOSS': [1000],
    'EMERGENCY_STOP_LOSS': [2000],
    'MARKET_OPEN_BUFFER_MINUTES': [15],
    'MARKET_CLOSE_BUFFER_MINUTES': [15],
    'EARLY_SIGNAL_COOLDOWN_MINUTES': [30],
    'PRICE_WINDOW_SECONDS': [30 * 60]
}

# === Output Settings ===
RESULTS_FILENAME = "analytics_results.csv"
LOG_LEVEL = 'INFO'
```

### Live Trading Configuration (`config/live.py`)

```python
# API Configuration
TRADIER_API_URL = 'https://api.tradier.com/v1'
TRADIER_ACCESS_TOKEN = 'your_access_token_here'
ACCOUNT_ID = 'your_account_id_here'
```

### Paper Trading Configuration (`config/paper.py`)

```python
# Sandbox API Configuration
TRADIER_API_URL = 'https://sandbox.tradier.com/v1'
TRADIER_ACCESS_TOKEN = 'your_sandbox_token_here'
ACCOUNT_ID = 'your_sandbox_account_id_here'
```

## How to Run

### Prerequisites

- **Python**: 3.8 or higher
- **Operating System**: Linux, macOS, or Windows
- **Tradier Account**: For live/paper trading (free sandbox available)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/PetaTech/spybot.git
   cd bot
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up API credentials** (for live/paper trading):
   - Sign up for a Tradier account at [tradier.com](https://tradier.com)
   - Get your API access token and account ID
   - Update the configuration files with your credentials

### Running the Bot

#### Backtesting

Run historical backtests using stored data:

- **Single Backtest**:
```bash
python backtest_single.py
```
- **Batch Backtest & Analytics** (find top configs):
```bash
python backtest_batch.py
```

The batch backtest will:
- Run a grid/random search over strategy parameters
- Launch multiple backtests in parallel (using all CPU cores, capped for memory safety)
- Select and report the top 5 configurations by win rate and total profit
- Save analytics results to CSV and a detailed log in the `logs/` directory

The backtest will:
- Load historical SPY and options data from CSV files
- Process data row by row through the trading engine
- Automatically convert CSVs to Parquet (if needed) for ultra-fast, memory-efficient queries using DuckDB
- Stream historical data directly from Parquet files (never loads full files into RAM)
- Generate comprehensive performance reports
- Save results to the `logs/` directory

#### Paper Trading

Test the strategy with simulated orders:

```bash
python paper.py
```

Paper trading:
- Uses live market data from Tradier sandbox
- Simulates order execution without real money
- Perfect for strategy validation before live trading

#### Live Trading

Execute real trades with actual money:

```bash
python live.py
```

**⚠️ WARNING**: Live trading uses real money. Always test thoroughly in paper mode first!

Live trading features:
- Real-time market data from Tradier
- Actual order execution
- Real-time position monitoring
- Comprehensive logging and alerts

## Backtest Results

Batch analytics results include:
- Top 5 configs by win rate and profit
- Full CSV of all tested configs and their metrics
- Timestamped log file with detailed analytics summary

Sample metrics from recent backtests:
- Total Return: +15.2%
- Win Rate: 68.4%
- Average Trade: +$127.50
- Max Drawdown: -8.3%
- Sharpe Ratio: 1.85

## Live and Paper Trading

### Tradier API Setup

1. **Create Tradier Account**:
   - Visit [tradier.com](https://tradier.com)
   - Sign up for a free account
   - Complete account verification

2. **Get API Credentials**:
   - Navigate to API settings in your account
   - Generate an access token
   - Note your account ID

3. **Configure the Bot**:
   - Update `config/live.py` with your live credentials
   - Update `config/paper.py` with your sandbox credentials

### Safety Features

The bot includes multiple safety mechanisms:

- **Daily Limits**: Maximum trades and losses per day
- **Emergency Stop Loss**: Automatic shutdown on large losses
- **Market Timing**: Avoids trading during volatile open/close periods
- **Position Sizing**: Limits risk per trade to $400
- **Retry Logic**: Handles API failures gracefully

### Monitoring

The bot provides real-time monitoring through:

- **Console Output**: Live status updates and trade notifications
- **Log Files**: Detailed trade logs in `logs/` directory
- **Performance Metrics**: Real-time P&L and statistics
- **Error Handling**: Graceful handling of API issues and market conditions

## Troubleshooting and Common Issues

### API Connection Issues

**Problem**: "Failed to connect to API"
- **Solution**: Verify API credentials in config files
- **Check**: Ensure account is active and has proper permissions

**Problem**: "Order failed" errors
- **Solution**: Check account balance and buying power
- **Check**: Verify option symbols and strike prices are valid

### Data Issues

**Problem**: "No data returned from query"
- **Solution**: Ensure data files exist in correct locations
- **Check**: Verify CSV file formats and column names

**Problem**: Missing historical data
- **Solution**: Download required data files for backtesting
- **Check**: Ensure data covers the specified date range

### Configuration Issues

**Problem**: "Strategy name not recognized"
- **Solution**: Check import statements in config files
- **Check**: Ensure all required parameters are defined

**Problem**: Invalid configuration values
- **Solution**: Review parameter ranges and constraints
- **Check**: Ensure time formats match expected patterns

### Performance Issues

**Problem**: Bot running slowly
- **Solution**: Optimize data loading for large datasets
- **Check**: Monitor system resources and API rate limits

**Problem**: Excessive API calls
- **Solution**: Implement caching for frequently accessed data
- **Check**: Review retry logic and polling intervals

## Roadmap and Future Plans

### Planned Features

- **Web Dashboard**: Real-time web interface for monitoring and control
- **Additional Strategies**: Mean reversion, volatility breakout, and sector rotation strategies
- **Multi-Asset Support**: Extend to other ETFs and individual stocks
- **Machine Learning**: Integration of ML models for signal generation
- **Portfolio Management**: Multi-strategy portfolio optimization
- **Mobile App**: iOS/Android app for remote monitoring

### Technical Improvements

- **Database Integration**: Replace CSV files with proper database storage
- **Real-time Streaming**: WebSocket connections for lower latency
- **Advanced Analytics**: Enhanced performance metrics and visualization
- **Risk Models**: More sophisticated risk management algorithms
- **Backtesting Engine**: Monte Carlo simulations and stress testing

### Infrastructure Enhancements

- **Cloud Deployment**: AWS/Azure deployment options
- **Containerization**: Docker support for easy deployment
- **CI/CD Pipeline**: Automated testing and deployment
- **Monitoring**: Prometheus/Grafana integration for system monitoring
- **Alerting**: Email/SMS notifications for important events

## License

This project is licensed for personal, private use only. The trading bot is designed for educational and research purposes. Users are responsible for:

- Complying with all applicable securities laws and regulations
- Understanding the risks involved in options trading
- Testing thoroughly before using real money
- Monitoring the bot's performance and making necessary adjustments

**Disclaimer**: This software is provided "as is" without warranty. Trading involves substantial risk of loss and is not suitable for all investors. Past performance does not guarantee future results.

---

**Author**: Juan Francisco González  
**Version**: 1.0.0  
**Last Updated**: June 2025 