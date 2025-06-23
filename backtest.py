"""
Backtest Data Provider
Streams historical data rows to the trading engine
"""

import pandas as pd
import datetime
import os
from pathlib import Path
from dateutil import tz
from typing import Optional, Iterator, Dict
from core.trading_engine import TradingEngine, DataProvider
from config.backtest import *
import duckdb


class BacktestDataProvider(DataProvider):
    """Backtest data provider that streams historical CSV data rows"""
    
    def __init__(self, spy_file: str, options_file: str):
        self.spy_file = spy_file
        self.options_file = options_file
        self.spy_data = None
        self.current_index = 0
        
        # Load SPY data (this is small enough to keep in memory)
        self._load_spy_data()
    
    def _load_spy_data(self):
        """Load SPY data into memory"""
        print(f"[DEBUG] Loading SPY data from: {self.spy_file}")
        self.spy_data = pd.read_csv(self.spy_file, parse_dates=["quote_datetime"])
        print(f"[DEBUG] SPY data loaded, total rows: {len(self.spy_data)}")
    
    def stream(self) -> Iterator[Dict]:
        """Stream market data rows one at a time"""
        print(f"[DEBUG] Starting data stream, total SPY rows: {len(self.spy_data)}")
        for idx, row in self.spy_data.iterrows():
            if idx % 100 == 0:  # Log every 100th row
                print(f"[DEBUG] Processing SPY row {idx}/{len(self.spy_data)}: {row['quote_datetime']}")
            yield {
                'current_time': row['quote_datetime'],
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['trade_volume'],
                'symbol': 'SPY'
            }
    
    def set_current_time(self, current_time: datetime.datetime):
        """Set the current time for options data loading"""
        print(f"[DEBUG] Setting current time: {current_time}")
        # No need to store this anymore since we query on demand
    
    def get_option_chain(self, symbol: str, expiration_date: str, current_time: datetime.datetime = None) -> pd.DataFrame:
        """Get option chain for a given symbol and expiration date using DuckDB"""
        print(f"[DEBUG] get_option_chain called - symbol: {symbol}, expiration: {expiration_date}, current_time: {current_time}")
        
        if current_time is None:
            print(f"[DEBUG] No current_time provided, cannot query options data")
            return pd.DataFrame()
        
        # Format the current time for the query
        time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Query by quote_datetime first (like the working example)
        query = f"""
            SELECT * FROM read_csv_auto('{self.options_file}', header=True)
            WHERE underlying_symbol = '{symbol}'
            AND quote_datetime = '{time_str}'
        """
        
        print(f"[DEBUG] Executing DuckDB query: {query}")
        
        try:
            result_df = duckdb.query(query).to_df()
            print(f"[DEBUG] DuckDB query returned {len(result_df)} rows")
            
            if result_df.empty:
                print(f"[DEBUG] No data returned from DuckDB query for time {time_str}")
                return result_df
            
            # Filter by expiration date in Python
            # Convert expiration date to the format used in the CSV file
            try:
                exp_date = datetime.datetime.strptime(expiration_date, '%Y-%m-%d')
                # Try both formats
                exp_formats = [exp_date.strftime('%m/%d/%Y'), expiration_date]
            except:
                exp_formats = [expiration_date]
            
            print(f"[DEBUG] Filtering for expiration formats: {exp_formats}")
            
            # Filter by expiration
            mask = result_df['expiration'].isin(exp_formats)
            filtered_df = result_df[mask]
            
            print(f"[DEBUG] After expiration filtering: {len(filtered_df)} rows")
            
            if not filtered_df.empty:
                print(f"[DEBUG] Option chain columns: {list(filtered_df.columns)}")
                print(f"[DEBUG] Sample option data: {filtered_df.head(1).to_dict('records')}")
            
            return filtered_df
            
        except Exception as e:
            print(f"[DEBUG] DuckDB query failed: {e}")
            return pd.DataFrame()
    

def create_config() -> dict:
    """Create configuration for backtest mode"""
    return {
        'MOVE_THRESHOLD_PERCENT': MOVE_THRESHOLD_PERCENT,
        'MOVE_THRESHOLD_MIN_POINTS': MOVE_THRESHOLD_MIN_POINTS,
        'MOVE_THRESHOLD_MAX_POINTS': MOVE_THRESHOLD_MAX_POINTS,
        'REFERENCE_PRICE_TYPE': REFERENCE_PRICE_TYPE,
        'COOLDOWN_PERIOD': COOLDOWN_PERIOD,
        'RISK_PER_SIDE': RISK_PER_SIDE,
        'OPTION_TARGET_MULTIPLIER': OPTION_TARGET_MULTIPLIER,
        'MAX_RETRIES': MAX_RETRIES,
        'RETRY_DELAY': RETRY_DELAY,
        'PRICE_WINDOW_SECONDS': PRICE_WINDOW_SECONDS,
        'MAX_ENTRY_TIME': datetime.time(15, 0),
        'MIN_PROFIT_PERCENTAGE': MIN_PROFIT_PERCENTAGE,
        'MAX_HOLD_SECONDS': MAX_HOLD_SECONDS,
        'STOP_LOSS_PERCENTAGE': STOP_LOSS_PERCENTAGE,
        'OPTION_ASK_MIN': OPTION_ASK_MIN,
        'OPTION_ASK_MAX': OPTION_ASK_MAX,
        'OPTION_BID_ASK_RATIO': OPTION_BID_ASK_RATIO,
        'MAX_DAILY_TRADES': MAX_DAILY_TRADES,
        'MAX_DAILY_LOSS': MAX_DAILY_LOSS,
        'EMERGENCY_STOP_LOSS': EMERGENCY_STOP_LOSS,
        'MARKET_OPEN': MARKET_OPEN,
        'MARKET_CLOSE': MARKET_CLOSE,
        'TIMEZONE': TIMEZONE,
        'MARKET_OPEN_BUFFER_MINUTES': MARKET_OPEN_BUFFER_MINUTES,
        'MARKET_CLOSE_BUFFER_MINUTES': MARKET_CLOSE_BUFFER_MINUTES,
        'EARLY_SIGNAL_COOLDOWN_MINUTES': EARLY_SIGNAL_COOLDOWN_MINUTES,
        'LOG_DIR': 'logs',
        'MODE': 'backtest'
    }


def main():
    """Main backtest function - just provides data and config to engine"""
    print("[DEBUG] Starting backtest main function")
    
    # Get data files from config
    spy_file = SPY_PATH
    options_file = OPT_PATH
    
    print(f"[DEBUG] SPY file path: {spy_file}")
    print(f"[DEBUG] Options file path: {options_file}")
    
    # Create data provider and config
    data_provider = BacktestDataProvider(spy_file, options_file)
    config = create_config()
    
    print(f"[DEBUG] Config created, MAX_RETRIES: {config['MAX_RETRIES']}, RETRY_DELAY: {config['RETRY_DELAY']}")
    
    # Create trading engine (engine manages orders internally)
    trading_engine = TradingEngine(config, data_provider, mode="backtest")
    
    # Process all data rows
    try:
        print("[DEBUG] Starting data processing loop")
        row_count = 0
        for row in data_provider.stream():
            row_count += 1
            if row_count % 100 == 0:
                print(f"[DEBUG] Processed {row_count} rows, current time: {row['current_time']}")
            
            # Skip pre-market data
            if row['current_time'].time() < datetime.time(9, 30):
                continue
            
            # Set current time in data provider for options loading
            data_provider.set_current_time(row['current_time'])
            
            # Process row through engine with explicit parameters
            print(f"[DEBUG] Processing row {row_count}: {row['current_time']} - SPY ${row['close']:.2f}")
            result = trading_engine.process_row(
                current_time=row['current_time'],
                symbol=row['symbol'],
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume']
            )
            print(f"[DEBUG] Row {row_count} result: {result['action']}")
            
            # Add a safety check to prevent infinite loops
            if row_count > 10000:  # Safety limit
                print("[DEBUG] Safety limit reached, stopping backtest")
                break
                
    except KeyboardInterrupt:
        print("Backtest interrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"[DEBUG] Exception in main loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[DEBUG] Finishing backtest")
        trading_engine.finish()


if __name__ == "__main__":
    main()