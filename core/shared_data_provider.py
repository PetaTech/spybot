"""
Shared Data Provider for Multi-Account Trading
Single data feed broadcasted to multiple account instances
"""

import time
import datetime
import threading
from typing import Dict, List, Optional, Callable
from queue import Queue, Empty
from dateutil import tz
from dataclasses import dataclass
from utils.tradier_api import set_api_credentials, get_spy_ohlc, test_connection, get_option_chain

@dataclass
class MarketData:
    """Standardized market data structure"""
    timestamp: datetime.datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    source_account: str

class SharedDataProvider:
    """
    Single data provider that broadcasts market data to multiple account managers
    Uses one Tradier account for data feed, distributes to all trading accounts
    """

    def __init__(self, data_source_account: Dict):
        """
        Initialize shared data provider

        Args:
            data_source_account: Account config to use for data feed
        """
        self.data_source_account = data_source_account
        self.api_url = data_source_account['api_url']
        self.access_token = data_source_account['access_token']
        self.account_id = data_source_account['account_id']
        # Use account index for identification since name field was removed
        account_index = data_source_account.get('account_index', 0)
        self.source_name = f"Account #{account_index} ({data_source_account['mode']})"

        # Set API credentials for data source
        set_api_credentials(self.api_url, self.access_token, self.account_id)

        # Data broadcasting
        self.subscribers: List[Callable[[MarketData], None]] = []
        self.subscriber_queues: List[Queue] = []

        # Threading
        self.running = False
        self.data_thread = None
        self.broadcast_thread = None

        # Data state
        self.latest_data: Optional[MarketData] = None
        self.data_count = 0
        self.error_count = 0
        self.last_error_time = None

        # Configuration
        self.polling_interval = 1  # 1 second
        self.max_queue_size = 100
        self.connection_timeout = 10
        
        # Option chain caching for synchronized option selection across accounts
        self.option_chain_cache = {}  # Key: "symbol_expiration" -> Value: (dataframe, timestamp)
        self.cache_duration = 5  # Cache option chains for 5 seconds
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_lock = threading.Lock()  # Thread safety for concurrent access

    def test_connection(self) -> bool:
        """Test connection to data source account"""
        try:
            return test_connection()
        except Exception as e:
            print(f"❌ SharedDataProvider connection test failed: {e}")
            return False

    def add_subscriber(self, callback: Callable[[MarketData], None]) -> int:
        """
        Add a subscriber callback function

        Args:
            callback: Function to call with new market data

        Returns:
            subscriber_id: ID for this subscriber
        """
        self.subscribers.append(callback)
        queue = Queue(maxsize=self.max_queue_size)
        self.subscriber_queues.append(queue)

        subscriber_id = len(self.subscribers) - 1
        print(f"📡 Added subscriber #{subscriber_id} to SharedDataProvider")
        return subscriber_id

    def remove_subscriber(self, subscriber_id: int):
        """Remove a subscriber"""
        if 0 <= subscriber_id < len(self.subscribers):
            self.subscribers[subscriber_id] = None
            print(f"📡 Removed subscriber #{subscriber_id} from SharedDataProvider")

    def start(self):
        """Start the shared data provider"""
        if self.running:
            print("⚠️ SharedDataProvider already running")
            return

        print(f"🚀 Starting SharedDataProvider with data source: {self.source_name}")

        # Test connection first
        if not self.test_connection():
            raise Exception(f"Failed to connect to data source account: {self.source_name}")

        self.running = True

        # Start data collection thread
        self.data_thread = threading.Thread(target=self._data_collection_loop, daemon=True)
        self.data_thread.start()

        # Start broadcast thread
        self.broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self.broadcast_thread.start()

        print(f"✅ SharedDataProvider started successfully")

    def stop(self):
        """Stop the shared data provider"""
        # Idempotent stop to avoid duplicate logs
        if not getattr(self, 'running', False):
            return
        print("🛑 Stopping SharedDataProvider...")
        self.running = False

        if self.data_thread:
            self.data_thread.join(timeout=5)
        if self.broadcast_thread:
            self.broadcast_thread.join(timeout=5)

        print("✅ SharedDataProvider stopped")

    def _data_collection_loop(self):
        """Main data collection loop (runs in separate thread)"""
        print(f"📊 Data collection loop started for {self.source_name}")

        while self.running:
            try:
                # Get current data
                now = datetime.datetime.now(tz=tz.gettz('America/New_York'))
                ohlc_data = get_spy_ohlc()

                if ohlc_data is None:
                    print(f"⚠️ No data received from {self.source_name} at {now.strftime('%H:%M:%S')}")
                    self.error_count += 1
                    time.sleep(5)
                    continue

                # Create market data object
                market_data = MarketData(
                    timestamp=now,
                    symbol='SPY',
                    open=ohlc_data['open'],
                    high=ohlc_data['high'],
                    low=ohlc_data['low'],
                    close=ohlc_data['close'],
                    volume=ohlc_data['volume'],
                    source_account=self.source_name
                )

                # Store latest data
                self.latest_data = market_data
                self.data_count += 1

                # Queue for broadcasting
                for queue in self.subscriber_queues:
                    try:
                        if not queue.full():
                            queue.put_nowait(market_data)
                    except Exception as e:
                        print(f"⚠️ Failed to queue data for subscriber: {e}")

                # Debug logging every 60 seconds
                if self.data_count % 60 == 0:
                    active_subs = len([s for s in self.subscribers if s is not None])
                    total_cache_requests = self.cache_hits + self.cache_misses
                    hit_rate = (self.cache_hits / total_cache_requests * 100) if total_cache_requests > 0 else 0
                    print(f"📊 SharedDataProvider: {self.data_count} data points collected, "
                          f"{active_subs} active subscribers, "
                          f"Cache: {self.cache_hits}/{total_cache_requests} hits ({hit_rate:.0f}%)")

                # Wait for next poll
                time.sleep(self.polling_interval)

            except Exception as e:
                self.error_count += 1
                self.last_error_time = datetime.datetime.now()
                print(f"❌ Error in data collection loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
        
        print(f"⚠️ Data collection loop EXITED for {self.source_name}! running={self.running}")

    def _broadcast_loop(self):
        """Broadcast loop to send data to subscribers (runs in separate thread)"""
        print("📡 Broadcast loop started")

        while self.running:
            try:
                # Process queued data for each subscriber
                for i, (callback, queue) in enumerate(zip(self.subscribers, self.subscriber_queues)):
                    if callback is None:
                        continue

                    try:
                        # Get data from queue (non-blocking)
                        market_data = queue.get_nowait()

                        # Call subscriber callback
                        callback(market_data)

                    except Empty:
                        # No data in queue for this subscriber
                        continue
                    except Exception as e:
                        print(f"❌ Error calling subscriber #{i} callback: {e}")

                # Small delay to prevent CPU spinning
                time.sleep(0.01)  # 10ms

            except Exception as e:
                print(f"❌ Error in broadcast loop: {e}")
                time.sleep(1)

    def get_latest_data(self) -> Optional[MarketData]:
        """Get the latest market data (synchronous)"""
        return self.latest_data

    def get_stats(self) -> Dict:
        """Get provider statistics including cache performance"""
        active_subscribers = len([s for s in self.subscribers if s is not None])
        total_cache_requests = self.cache_hits + self.cache_misses
        cache_hit_rate = (self.cache_hits / total_cache_requests * 100) if total_cache_requests > 0 else 0

        return {
            'running': self.running,
            'data_source': self.source_name,
            'data_points_collected': self.data_count,
            'error_count': self.error_count,
            'last_error_time': self.last_error_time,
            'active_subscribers': active_subscribers,
            'latest_data_time': self.latest_data.timestamp if self.latest_data else None,
            'queue_sizes': [q.qsize() for q in self.subscriber_queues],
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': f"{cache_hit_rate:.1f}%",
            'cached_chains': len(self.option_chain_cache)
        }

    def health_check(self) -> bool:
        """Check if provider is healthy"""
        if not self.running:
            print(f"[HEALTH] Data provider not running")
            return False

        # Check if threads are alive
        if self.data_thread and not self.data_thread.is_alive():
            print(f"[HEALTH] ❌ Data collection thread is DEAD!")
            return False
        
        if self.broadcast_thread and not self.broadcast_thread.is_alive():
            print(f"[HEALTH] ❌ Broadcast thread is DEAD!")
            return False

        # Check if we've received data recently (be more lenient - allow up to 5 minutes gap)
        if self.latest_data:
            now = datetime.datetime.now(tz=tz.gettz('America/New_York'))
            data_age = (now - self.latest_data.timestamp).total_seconds()
            if data_age > 300:  # No data for over 5 minutes
                print(f"[HEALTH] ❌ No data for {data_age:.0f}s (last: {self.latest_data.timestamp.strftime('%H:%M:%S')})")
                print(f"[HEALTH] Data count: {self.data_count}, Error count: {self.error_count}")
                print(f"[HEALTH] Collection thread alive: {self.data_thread.is_alive() if self.data_thread else 'None'}")
                return False
            elif data_age > 60:
                # Log warning but don't fail health check yet
                print(f"[HEALTH] ⚠️ No data for {data_age:.0f}s (last: {self.latest_data.timestamp.strftime('%H:%M:%S')})")

        # Check error rate
        if self.error_count > 10 and self.data_count > 0:
            error_rate = self.error_count / self.data_count
            if error_rate > 0.1:  # More than 10% error rate
                print(f"[HEALTH] ❌ High error rate: {error_rate:.1%} ({self.error_count}/{self.data_count})")
                return False

        return True
    
    def clear_option_chain_cache(self):
        """Clear the option chain cache (useful for debugging or forced refresh)"""
        with self.cache_lock:
            cache_size = len(self.option_chain_cache)
            self.option_chain_cache.clear()
            print(f"[CACHE] Cleared {cache_size} cached option chains")
    
    def get_cache_stats(self) -> Dict:
        """Get detailed cache statistics (thread-safe)"""
        with self.cache_lock:
            total_requests = self.cache_hits + self.cache_misses
            hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'cache_hits': self.cache_hits,
                'cache_misses': self.cache_misses,
                'total_requests': total_requests,
                'hit_rate': f"{hit_rate:.1f}%",
                'cached_entries': len(self.option_chain_cache),
                'cache_duration': self.cache_duration
            }

    # === Options Chain Access ===
    def get_option_chain(self, symbol: str, expiration: str, current_time: datetime.datetime):
        """Fetch option chain for given symbol/expiration using Tradier API with caching.
        
        Caching ensures all accounts receive identical option chains when processing
        the same signal, enabling consistent option selection across all accounts.
        
        Thread-safe: Uses lock to prevent race conditions when multiple accounts
        fetch option chains simultaneously.
        
        Args:
            symbol: Symbol to fetch options for (e.g., 'SPY')
            expiration: Expiration date in YYYY-MM-DD format
            current_time: Current market time (used for cache validation)
            
        Returns:
            DataFrame with option chain data or empty DataFrame on error
        """
        cache_key = f"{symbol}_{expiration}"
        now = time.time()
        
        # Thread-safe cache access
        with self.cache_lock:
            # Check cache first
            if cache_key in self.option_chain_cache:
                cached_df, cache_timestamp = self.option_chain_cache[cache_key]
                cache_age = now - cache_timestamp
                
                if cache_age < self.cache_duration:
                    self.cache_hits += 1
                    print(f"[CACHE HIT] Option chain for {symbol} {expiration} (age: {cache_age:.2f}s, hits: {self.cache_hits})")
                    return cached_df.copy()  # Return copy to prevent modification
            
            # Cache miss - increment counter inside lock
            self.cache_misses += 1
            print(f"[CACHE MISS] Fetching fresh option chain for {symbol} {expiration} (misses: {self.cache_misses})")
        
        # Fetch outside lock to avoid blocking other threads during API call
        try:
            import pandas as pd
            df = get_option_chain(symbol, expiration)
            
            # Store in cache (thread-safe)
            with self.cache_lock:
                # Double-check: another thread might have fetched while we were waiting
                if cache_key in self.option_chain_cache:
                    cached_df, cache_timestamp = self.option_chain_cache[cache_key]
                    cache_age = now - cache_timestamp
                    if cache_age < self.cache_duration:
                        # Another thread already cached this, use theirs
                        print(f"[CACHE] Another thread cached {symbol} {expiration} while we were fetching")
                        return cached_df.copy()
                
                # Store our fetched data
                self.option_chain_cache[cache_key] = (df, now)
                
                # Clean up old cache entries (keep only last 10 entries)
                if len(self.option_chain_cache) > 10:
                    # Remove oldest entry
                    oldest_key = min(self.option_chain_cache.keys(), 
                                   key=lambda k: self.option_chain_cache[k][1])
                    del self.option_chain_cache[oldest_key]
                    print(f"[CACHE CLEANUP] Removed old cache entry: {oldest_key}")
            
            return df
            
        except Exception as e:
            print(f"❌ SharedDataProvider.get_option_chain error: {e}")
            # Return empty DataFrame on failure to keep engine logic robust
            try:
                import pandas as pd
                return pd.DataFrame()
            except Exception:
                return []