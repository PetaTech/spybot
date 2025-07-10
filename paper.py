"""
Paper Trading Data Provider
Streams live data rows to the trading engine
"""

import time
import datetime
import os
import pandas as pd
from dateutil import tz
from typing import Optional, Iterator, Dict
from core.trading_engine import TradingEngine, DataProvider
from utils.tradier_api import set_api_credentials, get_spy_ohlc, get_option_chain, test_connection
from config.paper import *

# Set API credentials before importing other modules
set_api_credentials(TRADIER_API_URL, TRADIER_ACCESS_TOKEN, ACCOUNT_ID)


class PaperDataProvider(DataProvider):
    """Paper trading data provider using Tradier sandbox API"""
    
    def __init__(self, api_url: str, access_token: str):
        self.api_url = api_url
        self.access_token = access_token
        self.last_price = None
        self.last_time = None
    
    def stream(self) -> Iterator[Dict]:
        """Stream live market data rows"""
        while True:
            try:
                now = datetime.datetime.now(tz=tz.gettz(TIMEZONE))
                ohlc = get_spy_ohlc()
                
                # Skip if ohlc is None
                if ohlc is None:
                    time.sleep(60)
                    continue
                
                # Create market row with real OHLC data
                row = {
                    'current_time': now,
                    'open': ohlc['open'],
                    'high': ohlc['high'],
                    'low': ohlc['low'],
                    'close': ohlc['close'],
                    'volume': ohlc['volume'],
                    'symbol': 'SPY'
                }
                
                # Debug logging
                print(f"[PAPER DATA] {now.strftime('%H:%M:%S')} SPY: O={ohlc['open']:.2f} H={ohlc['high']:.2f} L={ohlc['low']:.2f} C={ohlc['close']:.2f} V={ohlc['volume']}")
                
                yield row
                
                # Wait before next data point
                time.sleep(60)
                
            except Exception as e:
                print(f"Error getting data: {e}")
                time.sleep(60)
    
    def get_option_chain(self, symbol: str, expiration_date: str, current_time=None) -> pd.DataFrame:
        """Get option chain from sandbox API"""
        return get_option_chain(symbol, expiration_date)


def create_config() -> dict:
    """Create configuration for paper mode"""
    return {
        'REFERENCE_PRICE_TYPE': REFERENCE_PRICE_TYPE,
        'COOLDOWN_PERIOD': COOLDOWN_PERIOD,
        'RISK_PER_SIDE': RISK_PER_SIDE,
        'MAX_RETRIES': MAX_RETRIES,
        'RETRY_DELAY': RETRY_DELAY,
        'PRICE_WINDOW_SECONDS': PRICE_WINDOW_SECONDS,
        'MAX_ENTRY_TIME': datetime.datetime.strptime(MAX_ENTRY_TIME, '%H:%M').time(),
        'OPTION_ASK_MIN': OPTION_ASK_MIN,
        'OPTION_ASK_MAX': OPTION_ASK_MAX,
        'OPTION_BID_ASK_RATIO': OPTION_BID_ASK_RATIO,
        'MAX_HOLD_SECONDS': MAX_HOLD_SECONDS,
        'MAX_DAILY_TRADES': MAX_DAILY_TRADES,
        'MAX_DAILY_LOSS': MAX_DAILY_LOSS,
        'MARKET_OPEN': MARKET_OPEN,
        'MARKET_CLOSE': MARKET_CLOSE,
        'TIMEZONE': TIMEZONE,
        'LOG_DIR': 'logs',
        'MODE': 'paper',
        'STOP_LOSS_PERCENTAGE': STOP_LOSS_PERCENTAGE,
        'EMERGENCY_STOP_LOSS': EMERGENCY_STOP_LOSS,
        'MARKET_OPEN_BUFFER_MINUTES': MARKET_OPEN_BUFFER_MINUTES,
        'MARKET_CLOSE_BUFFER_MINUTES': MARKET_CLOSE_BUFFER_MINUTES,
        'EARLY_SIGNAL_COOLDOWN_MINUTES': EARLY_SIGNAL_COOLDOWN_MINUTES,
        'COMMISSION_PER_CONTRACT': COMMISSION_PER_CONTRACT if 'COMMISSION_PER_CONTRACT' in globals() else 0.65,
        'SLIPPAGE': SLIPPAGE if 'SLIPPAGE' in globals() else 0.01,
        # VIX-based parameters
        'VIX_THRESHOLD': VIX_THRESHOLD,
        'HIGH_VOL_MOVE_THRESHOLD': HIGH_VOL_MOVE_THRESHOLD,
        'HIGH_VOL_PREMIUM_MIN': HIGH_VOL_PREMIUM_MIN,
        'HIGH_VOL_PREMIUM_MAX': HIGH_VOL_PREMIUM_MAX,
        'HIGH_VOL_PROFIT_TARGET': HIGH_VOL_PROFIT_TARGET,
        'LOW_VOL_MOVE_THRESHOLD': LOW_VOL_MOVE_THRESHOLD,
        'LOW_VOL_PREMIUM_MIN': LOW_VOL_PREMIUM_MIN,
        'LOW_VOL_PREMIUM_MAX': LOW_VOL_PREMIUM_MAX,
        'LOW_VOL_PROFIT_TARGET': LOW_VOL_PROFIT_TARGET,
    }


def main():
    """Main paper trading function - just provides data and config to engine"""
    # Test connection
    if not test_connection():
        print("❌ Failed to connect to API. Exiting...")
        return
    
    # Check market hours
    now = datetime.datetime.now(tz=tz.gettz(TIMEZONE))
    market_open = datetime.datetime.strptime(MARKET_OPEN, '%H:%M').time()
    market_close = datetime.datetime.strptime(MARKET_CLOSE, '%H:%M').time()
    
    print(f"\n🕐 Current Time (NY): {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"📈 Market Hours: {MARKET_OPEN} - {MARKET_CLOSE} EDT")
    
    if not (market_open <= now.time() <= market_close):
        print("❌ Market is currently CLOSED. Paper trading will not detect signals.")
        print("💡 Try running during market hours (9:30 AM - 4:00 PM EDT)")
        return
    
    print("✅ Market is OPEN. Starting paper trading...")
    
    # Create data provider and config
    data_provider = PaperDataProvider(TRADIER_API_URL, TRADIER_ACCESS_TOKEN)
    config = create_config()
    
    # Create trading engine (engine manages orders internally)
    trading_engine = TradingEngine(config, data_provider, mode="paper")
    
    try:
        # Process data rows
        for row in data_provider.stream():
            # Process row through engine with explicit parameters
            trading_engine.process_row(
                current_time=row['current_time'],
                symbol=row['symbol'],
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume']
            )
    except KeyboardInterrupt:
        print("\n🛑 Paper trading interrupted by user")
    finally:
        # Ensure proper cleanup and final logging
        trading_engine.finish()


if __name__ == "__main__":
    main() 