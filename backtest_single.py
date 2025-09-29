"""
Backtest Data Provider
Streams historical data rows to the trading engine
"""

import pandas as pd
import datetime
import os
import sys
from pathlib import Path
from dateutil import tz
from typing import Optional, Iterator, Dict
from core.trading_engine import TradingEngine, DataProvider
from config.backtest_single import *
import duckdb
from config.polygon import POLYGON_API_KEY

# Remove ensure_parquet_exists and all CSV handling

class BacktestDataProvider(DataProvider):
    """Backtest data provider that streams historical Parquet data rows"""
    
    def __init__(self, spy_file: str, options_file: str):
        self.spy_file = spy_file
        self.options_file = options_file
        self.current_index = 0
        
        # Assume Parquet files are provided directly
        self.options_parquet = self.options_file
        self.spy_parquet = self.spy_file
        
        # Prepare DuckDB connection for streaming
        self.duckdb_conn = duckdb.connect(database=':memory:')
        self.spy_stream = self.duckdb_conn.execute(f"SELECT * FROM read_parquet('{self.spy_parquet}') ORDER BY datetime ASC").fetchdf().itertuples(index=False)
        print(f"[DEBUG] SPY Parquet streaming ready: {self.spy_parquet}")
    
    def stream(self) -> Iterator[Dict]:
        """Stream market data rows one at a time using DuckDB (no pandas in memory)"""
        import pandas as pd
        print(f"[DEBUG] Starting data stream from Parquet: {self.spy_parquet}")
        for idx, row in enumerate(self.spy_stream):
            if idx % 100 == 0:
                print(f"[DEBUG] Processing SPY row {idx}: {row.datetime}")
            # Handle both int (ms since epoch) and pandas.Timestamp
            if isinstance(row.datetime, (int, float)):
                current_time = datetime.datetime.utcfromtimestamp(row.datetime / 1000)
            elif hasattr(row.datetime, 'to_pydatetime'):
                current_time = row.datetime.to_pydatetime()
            else:
                current_time = row.datetime  # fallback, may already be datetime
            yield {
                'current_time': current_time,
                'open': row.open,
                'high': row.high,
                'low': row.low,
                'close': row.close,
                'volume': row.volume,
                'symbol': 'SPY'
            }
    
    def set_current_time(self, current_time: datetime.datetime):
        print(f"[DEBUG] Setting current time: {current_time}")
        # No need to store this anymore since we query on demand
    
    def get_option_chain(self, symbol: str, expiration_date: str, current_time: datetime.datetime = None) -> pd.DataFrame:
        print(f"[DEBUG] get_option_chain called - symbol: {symbol}, expiration: {expiration_date}, current_time: {current_time}")
        if current_time is None:
            print(f"[DEBUG] No current_time provided, cannot query options data")
            return pd.DataFrame()
        # Match on date (YYYY-MM-DD)
        date_str = current_time.strftime('%Y-%m-%d')
        query = f"""
            SELECT *,
                CASE contract_type WHEN 'call' THEN 'C' WHEN 'put' THEN 'P' ELSE NULL END AS option_type,
                strike_price AS strike,
                1.0 AS bid, 1.1 AS ask -- Dummy values for now
            FROM read_parquet('{self.options_parquet}')
            WHERE underlying_ticker = '{symbol}'
            AND date = '{date_str}'
            AND expiration_date = '{expiration_date}'
        """
        print(f"[DEBUG] Executing DuckDB query (Parquet): {query}")
        try:
            result_df = duckdb.query(query).to_df()
            print(f"[DEBUG] DuckDB query returned {len(result_df)} rows")
            if result_df.empty:
                print(f"[DEBUG] No data returned from DuckDB query for date {date_str}")
                return result_df
            # Only keep columns expected by engine
            keep_cols = ['option_type', 'strike', 'bid', 'ask', 'expiration_date', 'ticker', 'contract_type']
            for col in keep_cols:
                if col not in result_df.columns:
                    result_df[col] = None
            return result_df[keep_cols]
        except Exception as e:
            print(f"[DEBUG] DuckDB query failed: {e}")
            return pd.DataFrame()


def create_config() -> dict:
    """Create configuration for backtest mode"""
    return {
        # VIX-Based Strategy Parameters
        'VIX_THRESHOLD': VIX_THRESHOLD,
        'HIGH_VOL_MOVE_THRESHOLD': HIGH_VOL_MOVE_THRESHOLD,
        'HIGH_VOL_PREMIUM_MIN': HIGH_VOL_PREMIUM_MIN,
        'HIGH_VOL_PREMIUM_MAX': HIGH_VOL_PREMIUM_MAX,
        'HIGH_VOL_PROFIT_TARGET': HIGH_VOL_PROFIT_TARGET,
        'LOW_VOL_MOVE_THRESHOLD': LOW_VOL_MOVE_THRESHOLD,
        'LOW_VOL_PREMIUM_MIN': LOW_VOL_PREMIUM_MIN,
        'LOW_VOL_PREMIUM_MAX': LOW_VOL_PREMIUM_MAX,
        'LOW_VOL_PROFIT_TARGET': LOW_VOL_PROFIT_TARGET,
        
        # Core Strategy Parameters
        'REFERENCE_PRICE_TYPE': REFERENCE_PRICE_TYPE,
        'COOLDOWN_PERIOD': COOLDOWN_PERIOD,
        'RISK_PER_SIDE': RISK_PER_SIDE,
        'MAX_RETRIES': MAX_RETRIES,
        'RETRY_DELAY': RETRY_DELAY,
        'PRICE_WINDOW_SECONDS': PRICE_WINDOW_SECONDS,
        'MAX_ENTRY_TIME': datetime.time(15, 0),
        'STOP_LOSS_PERCENTAGE': STOP_LOSS_PERCENTAGE,
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
        'MODE': 'backtest',
        'POLYGON_API_KEY': POLYGON_API_KEY,
    }


def run_backtest(config: dict = None, spy_file: str = None, options_file: str = None, 
                return_results: bool = False) -> dict:
    """
    Run backtest with given configuration and return results
    
    Args:
        config: Configuration dictionary (uses create_config() if None)
        spy_file: Path to SPY data file (uses config if None)
        options_file: Path to options data file (uses config if None)
        return_results: Whether to return results dict instead of just running
        
    Returns:
        Results dictionary if return_results=True, None otherwise
    """
    print("[DEBUG] Starting backtest run")
    
    # Use provided config or create default
    if config is None:
        config = create_config()
    
    # Use provided files or get from config (fallback to None if not provided)
    if spy_file is None:
        spy_file = config.get('SPY_PATH')
    if options_file is None:
        options_file = config.get('OPT_PATH')
    
    # Validate that files are provided
    if spy_file is None or options_file is None:
        raise ValueError("SPY and options file paths must be provided either via arguments or config")
    
    print(f"[DEBUG] SPY file path: {spy_file}")
    print(f"[DEBUG] Options file path: {options_file}")
    
    # Update config with the actual file paths being used
    config['SPY_PATH'] = spy_file
    config['OPT_PATH'] = options_file
    
    # Create data provider
    data_provider = BacktestDataProvider(spy_file, options_file)
    
    print(f"[DEBUG] Config created, MAX_RETRIES: {config.get('MAX_RETRIES', 'N/A')}")
    
    # Create trading engine
    trading_engine = TradingEngine(config, data_provider, mode="backtest", telegram_config=None)
    
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
                
    except KeyboardInterrupt:
        print("Backtest interrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"[DEBUG] Exception in main loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[DEBUG] Finishing backtest")
        trading_engine.finish()
        
        # Return results if requested
        if return_results:
            summary = trading_engine.get_summary()
            status = trading_engine.get_status()
            
            # Calculate metrics
            total_trades = status.get('total_trades', 0)
            winning_trades = status.get('winning_trades', 0)
            losing_trades = status.get('losing_trades', 0)
            total_pnl = status.get('total_pnl', 0.0)
            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            max_drawdown = status.get('max_drawdown', 0.0)
            
            # Calculate additional metrics
            avg_win = status.get('avg_win', 0.0)
            avg_loss = status.get('avg_loss', 0.0)
            profit_factor = (abs(avg_win * winning_trades) / abs(avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else 0.0
            
            return {
                'config': config,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'max_drawdown': max_drawdown,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'data_file': os.path.basename(spy_file)
            }


def parse_data_directory(directory_name: str) -> dict:
    """
    Parse data directory name to extract file paths
    
    Args:
        directory_name: Directory name in format {start_date}_{end_date}_{interval}
                       e.g., "2025-09-03_2025-09-04_15min"
    
    Returns:
        Dictionary with SPY and options file paths
    """
    # Validate directory name format
    parts = directory_name.split('_')
    if len(parts) != 3:
        raise ValueError(f"Invalid directory format. Expected: {{start_date}}_{{end_date}}_{{interval}}, got: {directory_name}")
    
    start_date, end_date, interval = parts
    
    # Validate date formats
    try:
        datetime.datetime.strptime(start_date, "%Y-%m-%d")
        datetime.datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date format in directory name: {e}")
    
    # Validate interval format (should end with 'min')
    if not interval.endswith('min'):
        raise ValueError(f"Invalid interval format. Expected format like '15min', got: {interval}")
    
    # Construct full paths
    base_dir = os.path.join("./data", directory_name)
    
    spy_filename = f"spy_data_{start_date}_{end_date}_{interval}.parquet"
    options_filename = f"spy_options_0dte_contracts_{start_date}_{end_date}_{interval}.parquet"
    
    spy_path = os.path.join(base_dir, spy_filename)
    options_path = os.path.join(base_dir, options_filename)
    
    return {
        'spy_path': spy_path,
        'options_path': options_path,
        'directory': base_dir,
        'start_date': start_date,
        'end_date': end_date,
        'interval': interval
    }


def validate_data_files(file_paths: dict) -> None:
    """
    Validate that the data files exist
    
    Args:
        file_paths: Dictionary containing file paths from parse_data_directory()
    """
    spy_path = file_paths['spy_path']
    options_path = file_paths['options_path']
    
    if not os.path.exists(spy_path):
        raise FileNotFoundError(f"SPY data file not found: {spy_path}")
    
    if not os.path.exists(options_path):
        raise FileNotFoundError(f"Options data file not found: {options_path}")
    
    print(f"Found SPY data file: {spy_path}")
    print(f"Found Options data file: {options_path}")


def main():
    """Enhanced main backtest function with command line argument support"""
    
    # Check command line arguments
    if len(sys.argv) == 1:
        # No arguments provided - use config defaults
        print("WARNING: No data directory specified. Using config defaults...")
        print("USAGE: python backtest_single.py <data_directory>")
        print("EXAMPLE: python backtest_single.py 2025-09-03_2025-09-04_15min")
        print("Using config files for SPY and options paths")
        run_backtest()
        return
    
    if len(sys.argv) != 2:
        print("ERROR: Invalid number of arguments")
        print("Usage: python backtest_single.py <data_directory>")
        print("Example: python backtest_single.py 2025-09-03_2025-09-04_15min")
        print("")
        print("Directory format: {start_date}_{end_date}_{interval}")
        print("  - start_date: YYYY-MM-DD")
        print("  - end_date: YYYY-MM-DD") 
        print("  - interval: 1min, 5min, 15min, etc.")
        sys.exit(1)
    
    # Parse command line argument
    directory_name = sys.argv[1]
    
    try:
        # Parse and validate directory name
        print(f"Parsing data directory: {directory_name}")
        file_paths = parse_data_directory(directory_name)
        
        print(f"Date range: {file_paths['start_date']} to {file_paths['end_date']}")
        print(f"Interval: {file_paths['interval']}")
        print(f"Data directory: {file_paths['directory']}")
        
        # Validate that files exist
        validate_data_files(file_paths)
        
        # Run backtest with the specified files
        print(f"Starting backtest with data from {directory_name}")
        run_backtest(
            spy_file=file_paths['spy_path'],
            options_file=file_paths['options_path']
        )
        
    except ValueError as e:
        print(f"ERROR - Directory format error: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"ERROR - File not found: {e}")
        print("HINT: Make sure you have downloaded the data using download_polygon.py first")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()