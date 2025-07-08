import requests
import pandas as pd
import duckdb
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SPYDataPipeline:
    def __init__(self, polygon_api_key: str, data_interval: int):
        """
        Initialize the SPY data pipeline.
        
        Args:
            polygon_api_key: Your Polygon.io API key
            data_interval: Data interval in minutes (1, 5, 15, 30, 60, etc.)
        """
        self.polygon_api_key = polygon_api_key
        self.headers = {"Authorization": f"Bearer {polygon_api_key}"}
        self.base_url = "https://api.polygon.io"
        self.data_interval = data_interval
        self.request_delay = 0.1  # seconds between requests to avoid rate limits
        self.retry_delay = 15  # seconds to wait on rate limit
        self.session = requests.Session()
        
    def _is_weekday(self, date: datetime) -> bool:
        """Check if the date is a weekday (Monday=0, Sunday=6)"""
        return date.weekday() < 5  # Monday=0 to Friday=4
    
    def _get_date_range(self, start_date: str, end_date: str) -> list:
        """Get list of weekdays between start and end dates"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        dates = []
        current = start
        while current <= end:
            if self._is_weekday(current):
                dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        
        return dates
    
    def download_spy_data(self, date_str: str) -> Optional[pd.DataFrame]:
        """
        Download SPY data for a specific date with the specified interval.
        
        Args:
            date_str: Date in YYYY-MM-DD format
            
        Returns:
            DataFrame with SPY data or None if no data
        """
        url = f"https://api.polygon.io/v2/aggs/ticker/SPY/range/{self.data_interval}/minute/{date_str}/{date_str}?adjusted=true&sort=asc&limit=50000&apiKey={self.polygon_api_key}"
        
        try:
            resp = requests.get(url)
            
            if resp.status_code == 200:
                data = resp.json()
                if "results" in data and data["results"]:
                    df = pd.DataFrame(data["results"])
                    # Convert timestamp and rename columns
                    df["t"] = pd.to_datetime(df["t"], unit="ms")
                    df.rename(columns={
                        "t": "datetime", 
                        "o": "open", 
                        "h": "high", 
                        "l": "low", 
                        "c": "close", 
                        "v": "volume"
                    }, inplace=True)
                    df["date"] = date_str
                    
                    # Keep only the expected columns to avoid schema mismatch
                    expected_columns = ["datetime", "open", "high", "low", "close", "volume", "date"]
                    df = df[expected_columns]
                    
                    logger.info(f"✅ SPY {self.data_interval}min data downloaded for {date_str}: {len(df)} records")
                    return df
                else:
                    logger.warning(f"⚠️ No SPY results for {date_str}")
                    return None
                    
            elif resp.status_code == 429:
                logger.warning(f"⏳ Rate limit hit for SPY on {date_str}. Waiting {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
                return self.download_spy_data(date_str)  # Retry
                
            else:
                logger.error(f"❌ SPY Error {resp.status_code} on {date_str}")
                return None
                
        except Exception as e:
            logger.error(f"💥 Exception downloading SPY data for {date_str}: {e}")
            return None
    
    def get_spy_options_contracts(self, expiration_date: str, as_of_date: str) -> List[Dict]:
        """
        Get all SPY options contracts for a specific expiration date
        
        Args:
            expiration_date: Contract expiration date in YYYY-MM-DD format
            as_of_date: Point in time date in YYYY-MM-DD format
            
        Returns:
            List of contract dictionaries
        """
        url = f"{self.base_url}/v3/reference/options/contracts"
        params = {
            'underlying_ticker': 'SPY',
            'expiration_date': expiration_date,
            'as_of': as_of_date,
            'expired': 'false',
            'limit': 1000,
            'apikey': self.polygon_api_key
        }
        
        all_contracts = []
        
        while True:
            try:
                response = self.session.get(url, params=params)
                
                if response.status_code == 429:
                    logger.warning(f"⏳ Rate limit hit for options contracts. Waiting {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                    continue
                    
                response.raise_for_status()
                data = response.json()
                
                if 'results' in data and data['results']:
                    all_contracts.extend(data['results'])
                    logger.info(f"Fetched {len(data['results'])} contracts (Total: {len(all_contracts)})")
                
                # Check if there are more pages
                if 'next_url' in data and data['next_url']:
                    url = data['next_url']
                    params = {'apikey': self.polygon_api_key}  # next_url already contains other params
                    time.sleep(self.request_delay)
                else:
                    break
                    
            except Exception as e:
                logger.error(f"💥 Exception getting options contracts: {e}")
                break
        
        return all_contracts
    
    def download_spy_options_contracts(self, date_str: str) -> Optional[pd.DataFrame]:
        """
        Download SPY options contracts for same-day expiration
        
        Args:
            date_str: Date in YYYY-MM-DD format
            
        Returns:
            DataFrame with SPY options contracts data or None if no data
        """
        logger.info(f"📅 Fetching SPY options contracts for same-day expiration: {date_str}")
        
        # Get all SPY options contracts that expire on the same day
        contracts = self.get_spy_options_contracts(date_str, date_str)
        logger.info(f"📊 Found {len(contracts)} SPY options contracts with same-day expiration")
        
        if not contracts:
            logger.warning("⚠️ No same-day expiration contracts found!")
            return None
        
        # Convert contracts to DataFrame
        options_data = []
        
        for contract in contracts:
            option_info = {
                'ticker': contract.get('ticker'),
                'underlying_ticker': contract.get('underlying_ticker'),
                'contract_type': contract.get('contract_type'),
                'strike_price': contract.get('strike_price'),
                'expiration_date': contract.get('expiration_date'),
                'shares_per_contract': contract.get('shares_per_contract', 100),
                'exercise_style': contract.get('exercise_style'),
                'primary_exchange': contract.get('primary_exchange'),
                'date': date_str,
            }
            options_data.append(option_info)
        
        logger.info(f"✅ Data collection complete:")
        logger.info(f"📊 Total contracts processed: {len(contracts)}")
        
        if not options_data:
            logger.warning("⚠️ No options data collected!")
            return None
        
        # Convert to DataFrame
        try:
            df = pd.DataFrame(options_data)
            logger.info(f"📊 DataFrame created with shape: {df.shape}")
            
            # Sort by contract type and strike price
            df = df.sort_values(['contract_type', 'strike_price'])
            
            return df
            
        except Exception as e:
            logger.error(f"💥 Error creating DataFrame: {e}")
            return None
    
    def save_to_parquet(self, spy_df: pd.DataFrame, options_df: pd.DataFrame, 
                       start_date: str, end_date: str, output_dir: str) -> Tuple[str, str]:
        """
        Save SPY and options data to Parquet files.
        
        Args:
            spy_df: Combined SPY DataFrame
            options_df: Combined SPY options DataFrame
            start_date: Start date for filename
            end_date: End date for filename
            output_dir: Directory to save files
            
        Returns:
            Tuple of (spy_parquet_path, options_parquet_path)
        """
        spy_parquet_path = None
        options_parquet_path = None
        
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Save SPY data
            if not spy_df.empty:
                spy_parquet_path = os.path.join(output_dir, f"spy_data_{start_date}_{end_date}_{self.data_interval}min.parquet")
                spy_df.to_parquet(spy_parquet_path, compression='snappy', index=False)
                logger.info(f"✅ Saved {len(spy_df)} SPY records to {spy_parquet_path}")
                logger.info(f"📊 SPY file size: {os.path.getsize(spy_parquet_path) / (1024*1024):.2f} MB")
            
            # Save SPY options data (0DTE contracts)
            if not options_df.empty:
                options_parquet_path = os.path.join(output_dir, f"spy_options_0dte_contracts_{start_date}_{end_date}_{self.data_interval}min.parquet")
                options_df.to_parquet(options_parquet_path, compression='snappy', index=False)
                logger.info(f"✅ Saved {len(options_df)} SPY options contracts (0DTE) records to {options_parquet_path}")
                logger.info(f"📊 Options file size: {os.path.getsize(options_parquet_path) / (1024*1024):.2f} MB")
                
        except Exception as e:
            logger.error(f"💥 Error saving to Parquet: {e}")
            raise
            
        return spy_parquet_path, options_parquet_path
    
    def run_pipeline(self, start_date: str, end_date: str, 
                     output_dir: str = "/data/") -> Tuple[str, str]:
        """
        Run the complete data pipeline.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            output_dir: Directory to save the Parquet files
            
        Returns:
            Tuple of (spy_parquet_path, options_parquet_path)
        """
        logger.info(f"🚀 Starting SPY data pipeline from {start_date} to {end_date}")
        logger.info(f"📊 Data interval: {self.data_interval} minutes")
        logger.info(f"🎯 Options: Same-day expiration contracts")
        
        # Get weekdays in the date range
        dates = self._get_date_range(start_date, end_date)
        logger.info(f"📅 Processing {len(dates)} weekdays")
        
        # Initialize data containers
        spy_data_frames = []
        options_data_frames = []
        
        # Download data for each date
        for date_str in dates:
            logger.info(f"📅 Processing {date_str}...")
            
            # Download SPY data
            spy_df = self.download_spy_data(date_str)
            if spy_df is not None:
                spy_data_frames.append(spy_df)
            
            # Add delay between requests
            time.sleep(self.request_delay)
            
            # Download SPY options contracts (0DTE)
            options_df = self.download_spy_options_contracts(date_str)
            if options_df is not None:
                options_data_frames.append(options_df)
            
            # Add delay between requests
            time.sleep(self.request_delay)
        
        # Combine all data
        combined_spy_df = pd.concat(spy_data_frames, ignore_index=True) if spy_data_frames else pd.DataFrame()
        combined_options_df = pd.concat(options_data_frames, ignore_index=True) if options_data_frames else pd.DataFrame()
        
        # Save to Parquet files
        spy_parquet_path, options_parquet_path = self.save_to_parquet(
            combined_spy_df, combined_options_df, start_date, end_date, output_dir
        )
        
        logger.info(f"🎉 Pipeline completed! Files saved to: {output_dir}")
        logger.info(f"📊 Total SPY records: {len(combined_spy_df)}")
        logger.info(f"📊 Total SPY options contracts (0DTE) records: {len(combined_options_df)}")
        
        return spy_parquet_path, options_parquet_path


def load_polygon_api_key():
    """Load Polygon API key from config file"""
    try:
        # Try to import from config/polygon.py
        sys.path.append(os.path.join(os.path.dirname(__file__), 'config'))
        from polygon import POLYGON_API_KEY
        return POLYGON_API_KEY
    except ImportError:
        logger.error("❌ Could not import POLYGON_API_KEY from config/polygon.py")
        logger.error("Please create config/polygon.py with: POLYGON_API_KEY = 'your_api_key_here'")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error loading API key: {e}")
        sys.exit(1)


def parse_date(date_str: str) -> str:
    """Parse and validate date string, convert to YYYY-MM-DD format"""
    try:
        # Parse the date (handles both YYYY-M-D and YYYY-MM-DD formats)
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        try:
            # Try without leading zeros
            parts = date_str.split('-')
            if len(parts) == 3:
                year, month, day = parts
                parsed_date = datetime(int(year), int(month), int(day))
                return parsed_date.strftime("%Y-%m-%d")
        except:
            pass
        
        logger.error(f"❌ Invalid date format: {date_str}")
        logger.error("Please use YYYY-MM-DD or YYYY-M-D format")
        sys.exit(1)


def main():
    """Main function that handles command line arguments"""
    
    # Check command line arguments
    if len(sys.argv) != 4:
        print("Usage: python data.py <start_date> <end_date> <data_interval_minutes>")
        print("Example: python data.py 2025-6-2 2025-7-3 1")
        print("         python data.py 2025-6-2 2025-7-3 5")
        print("         python data.py 2025-6-2 2025-7-3 15")
        print("Date format: YYYY-MM-DD or YYYY-M-D")
        print("Data interval: 1, 5, 15, 30, 60 minutes")
        print("Note: Only same-day expiration options contracts (0DTE) will be downloaded")
        sys.exit(1)
    
    # Parse command line arguments
    start_date_input = sys.argv[1]
    end_date_input = sys.argv[2]
    data_interval = int(sys.argv[3])
    
    # Parse and validate dates
    start_date = parse_date(start_date_input)
    end_date = parse_date(end_date_input)
    
    # Validate date range
    if datetime.strptime(start_date, "%Y-%m-%d") > datetime.strptime(end_date, "%Y-%m-%d"):
        logger.error("❌ Start date must be before or equal to end date")
        sys.exit(1)
    
    # Validate data interval
    valid_intervals = [1, 5, 15, 30, 60]
    if data_interval not in valid_intervals:
        logger.error(f"❌ Data interval must be one of: {valid_intervals}")
        sys.exit(1)
    
    # Load API key from config
    polygon_api_key = load_polygon_api_key()
    
    # Configuration
    OUTPUT_DIR = "./data"
    
    logger.info(f"🚀 Starting SPY data pipeline")
    logger.info(f"📅 Date range: {start_date} to {end_date}")
    logger.info(f"📊 Data interval: {data_interval} minutes")
    logger.info(f"🎯 Options contracts: Same-day expiration (0DTE)")
    logger.info(f"🔑 API key loaded from config/polygon.py")
    logger.info(f"💾 Output format: Parquet")
    logger.info(f"📁 Output directory: {OUTPUT_DIR}")
    
    # Initialize and run pipeline
    pipeline = SPYDataPipeline(polygon_api_key, data_interval)
    
    try:
        spy_parquet_path, options_parquet_path = pipeline.run_pipeline(start_date, end_date, OUTPUT_DIR)
        
        print(f"\n✅ Success! Parquet files created:")
        print(f"📁 SPY data: {spy_parquet_path}")
        print(f"📁 Options contracts data (0DTE): {options_parquet_path}")
        
    except Exception as e:
        logger.error(f"💥 Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    main()