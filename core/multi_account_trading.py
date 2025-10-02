"""
Multi-Account Trading Manager
Orchestrates multiple trading accounts with shared data feed and independent signals
"""

import time
import datetime
import threading
import signal
import sys
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from core.shared_data_provider import SharedDataProvider, MarketData
from core.account_manager import AccountManager
from utils.multi_account_telegram import MultiAccountTelegramManager
from config.accounts import (
    ACCOUNTS, get_enabled_accounts, get_data_source_account,
    ORCHESTRATION, MULTI_ACCOUNT_LOGGING,
    get_account_summary, validate_account_config
)
import config.strategy as strategy


class MultiAccountManager:
    """
    Orchestrates multiple trading accounts with shared data feed
    Each account processes the same market data independently for signal generation
    """

    def __init__(self, mode: str):
        """
        Initialize multi-account manager

        Args:
            mode: 'live' or 'paper'
        """
        if mode not in ['live', 'paper']:
            raise ValueError(f"Invalid mode: {mode}. Must be 'live' or 'paper'")

        self.mode = mode
        print(f"🏗️ Initializing Multi-Account Trading Manager ({mode.upper()} mode)")
        print("=" * 60)

        # Core components
        self.shared_data_provider: Optional[SharedDataProvider] = None
        self.account_managers: Dict[str, AccountManager] = {}
        self.telegram_manager = MultiAccountTelegramManager()

        # Threading
        self.running = False
        self.stopping = False  # Prevent multiple shutdown calls
        self.monitoring_thread = None
        self.executor = ThreadPoolExecutor(max_workers=20)  # For parallel processing

        # Statistics
        self.start_time = None
        self.total_market_data_processed = 0
        self.account_restart_counts = {}

        # Global risk tracking
        self.global_daily_pnl = 0.0
        self.global_open_positions = 0

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def initialize(self) -> bool:
        """Initialize all components"""
        try:
            # Validate and print account summary
            self._print_account_summary()

            # Initialize shared data provider
            if not self._initialize_data_provider():
                return False

            # Initialize account managers
            if not self._initialize_account_managers():
                return False

            # Initialize telegram notifications
            self._initialize_telegram()

            print("✅ Multi-Account Manager initialized successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize Multi-Account Manager: {e}")
            return False

    def _print_account_summary(self):
        """Print summary of accounts to be managed"""
        summary = get_account_summary(self.mode)
        print(f"📊 Account Summary ({self.mode.upper()} mode):")
        print(f"   Total accounts: {summary['total_accounts']}")
        print(f"   Enabled accounts: {summary['enabled_accounts']}")
        print(f"   Disabled accounts: {summary['disabled_accounts']}")

        enabled_accounts = get_enabled_accounts(self.mode)
        print(f"\n📋 Enabled Accounts for {self.mode.upper()} mode:")
        for i, account in enumerate(enabled_accounts, 1):
            overrides = len(account.get('strategy_overrides', {}))
            telegram = "✅" if account.get('telegram', {}).get('enabled') else "❌"
            account_ref = f"Account #{account.get('account_index', i-1)}"
            print(f"   {i}. {account_ref} ({account['mode']}) - "
                  f"{overrides} overrides, Telegram: {telegram}")

    def _initialize_data_provider(self) -> bool:
        """Initialize shared data provider"""
        try:
            print(f"\n🔌 Initializing Shared Data Provider...")

            # Get data source account for the specified mode
            data_source_account = get_data_source_account(self.mode)
            account_ref = f"Account #{data_source_account.get('account_index', 'Unknown')}"
            print(f"   Data source: {account_ref} ({data_source_account['mode']})")

            # Create shared data provider
            self.shared_data_provider = SharedDataProvider(data_source_account)

            # Test connection
            if not self.shared_data_provider.test_connection():
                account_ref = f"Account #{data_source_account.get('account_index', 'Unknown')}"
                print(f"❌ Failed to connect to data source: {account_ref}")
                return False

            print(f"✅ Shared Data Provider initialized")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize data provider: {e}")
            return False

    def _initialize_account_managers(self) -> bool:
        """Initialize all account managers"""
        try:
            print(f"\n👥 Initializing Account Managers for {self.mode.upper()} mode...")

            enabled_accounts = get_enabled_accounts(self.mode)
            if not enabled_accounts:
                print(f"❌ No enabled accounts found for {self.mode} mode")
                return False

            for account_config in enabled_accounts:
                try:
                    # Validate account configuration for the specified mode
                    account_index = account_config.get('account_index', 0)
                    validate_account_config(account_config, self.mode, account_index)

                    # Create account manager
                    account_ref = f"Account #{account_index}"
                    print(f"   Setting up: {account_ref} ({account_config['mode']})")

                    account_manager = AccountManager(account_config)
                    # Use account_name from AccountManager (fetched from API)
                    account_key = account_manager.account_name
                    self.account_managers[account_key] = account_manager
                    self.account_restart_counts[account_key] = 0

                    # Initialize VIX immediately for each engine before any data processing
                    try:
                        if hasattr(account_manager, 'trading_engine') and hasattr(account_manager.trading_engine, '_set_vix_parameters'):
                            # Ensure cache is primed then force refresh
                            if not hasattr(account_manager.trading_engine, '_vix_last_fetch_time'):
                                account_manager.trading_engine._vix_last_fetch_time = 0
                            account_manager.trading_engine._set_vix_parameters(force=True, target_datetime=None)
                    except Exception as e:
                        print(f"     ⚠️ VIX init failed for {account_key}: {e}")

                    # Attach shared data provider to this account's engine (enables option chain fetches)
                    try:
                        account_manager.trading_engine.data_provider = self.shared_data_provider
                        print(f"     🔗 Data provider attached to {account_manager.account_name}")
                    except Exception as e:
                        print(f"     ❌ Failed to attach data provider to {account_manager.account_name}: {e}")

                    # Register with shared data provider
                    # Use a closure to capture the account_key by value
                    def create_callback(acc_key):
                        return lambda data: self._process_account_data(acc_key, data)
                    
                    subscriber_id = self.shared_data_provider.add_subscriber(
                        create_callback(account_key)
                    )

                    print(f"     ✅ {account_manager.account_name} initialized (subscriber #{subscriber_id})")

                except Exception as e:
                    account_ref = f"Account #{account_config.get('account_index', 'Unknown')}"
                    print(f"     ❌ Failed to initialize {account_ref}: {e}")
                    continue

            if not self.account_managers:
                print("❌ No account managers initialized")
                return False

            print(f"✅ {len(self.account_managers)} account managers initialized")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize account managers: {e}")
            return False

    def _initialize_telegram(self):
        """Initialize telegram notifications for all accounts"""
        print(f"\n📱 Initializing Telegram Notifications...")

        telegram_count = 0
        for account_name, account_manager in self.account_managers.items():
            telegram_config = account_manager.get_telegram_config()
            if telegram_config and telegram_config.get('enabled'):
                if self.telegram_manager.add_account(account_name, telegram_config):
                    telegram_count += 1

        print(f"✅ {telegram_count} telegram notifiers initialized")

    def start(self) -> bool:
        """Start multi-account trading"""
        if self.running:
            print("⚠️ Multi-Account Manager already running")
            return False

        try:
            print(f"\n🚀 Starting Multi-Account Trading...")
            self.start_time = datetime.datetime.now()
            self.running = True

            # Start shared data provider
            self.shared_data_provider.start()

            # Start all account managers SIMULTANEOUSLY (no staggered startup)
            # This ensures all accounts have identical trading behavior
            print(f"   Starting all {len(self.account_managers)} accounts simultaneously...")
            for account_name, account_manager in self.account_managers.items():
                if account_manager.start():
                    print(f"   ✅ {account_name} started")
                else:
                    print(f"   ❌ {account_name} failed to start")
            
            # Send startup notifications after all accounts are started
            for account_name, account_manager in self.account_managers.items():
                if account_manager.is_running:
                    config_summary = account_manager.get_strategy_config_summary()
                    config_summary.update({
                        'account_id': account_manager.account_id,
                        'mode': account_manager.mode
                    })
                    self.telegram_manager.send_startup_message(account_name, config_summary)

            # Start monitoring thread
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()

            print(f"✅ Multi-Account Trading started with {len(self.account_managers)} accounts")
            print(f"📊 Monitoring started")
            print("=" * 60)

            return True

        except Exception as e:
            print(f"❌ Failed to start Multi-Account Trading: {e}")
            self.stop()
            return False

    def stop(self):
        """Stop multi-account trading"""
        if getattr(self, 'stopping', False):
            # Avoid duplicate logs on repeated stop calls
            return

        self.stopping = True
        print(f"\n🛑 Stopping Multi-Account Trading...")
        self.running = False

        # Stop shared data provider FIRST to prevent new data processing (non-blocking)
        if self.shared_data_provider and getattr(self.shared_data_provider, 'running', False):
            print("   🛑 Stopping data provider...")
            self.shared_data_provider.running = False  # Signal to stop, don't wait

        # Stop account managers
        for account_name, account_manager in self.account_managers.items():
            try:
                account_manager.stop()

                # Send shutdown telegram alert
                final_data = {
                    'timestamp': datetime.datetime.now(),
                    'mode': self.mode,
                    'total_pnl': getattr(account_manager.trading_engine, 'total_pnl', 0),
                    'total_trades': getattr(account_manager.trading_engine, 'total_trades', 0)
                }
                print(f"   📱 Sending shutdown alert for {account_name}...")
                success = self.telegram_manager.send_shutdown_alert(account_name, final_data)
                if success:
                    print(f"   ✅ Shutdown alert sent for {account_name}")
                else:
                    print(f"   ❌ Failed to send shutdown alert for {account_name}")

                print(f"   ✅ {account_name} stopped")
            except Exception as e:
                print(f"   ❌ Error stopping {account_name}: {e}")

        # Properly stop data provider with timeout
        if self.shared_data_provider:
            try:
                self.shared_data_provider.stop()
            except Exception as e:
                print(f"   ⚠️ Data provider stop timeout: {e}")

        # Stop monitoring thread
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)

        # Shutdown executor
        # ThreadPoolExecutor.shutdown has no 'timeout' parameter; wait and handle our own timeout externally if needed
        self.executor.shutdown(wait=True)

        print("✅ Multi-Account Trading stopped")

    def _process_account_data(self, account_name: str, market_data: MarketData):
        """Process market data for a specific account (called by shared data provider)"""
        try:
            account_manager = self.account_managers.get(account_name)
            if not account_manager:
                return

            # Process data through account manager
            result = account_manager.process_market_data(market_data)

            # Handle telegram notifications
            self._handle_notifications(account_name, result)

            # Update global statistics
            self.total_market_data_processed += 1


        except Exception as e:
            print(f"❌ Error processing data for {account_name}: {e}")
            self.telegram_manager.send_error_alert(account_name, str(e))

    def _handle_notifications(self, account_name: str, result: Dict):
        """Handle telegram notifications based on trading results"""
        action = result.get('action', '')
        print(f"[NOTIF DEBUG] Handling notifications for {account_name}, action={action}, signal_detected={result.get('signal_detected', False)}")

        # Handle signal alert (don't let it block other notifications)
        if result.get('signal_detected'):
            try:
                print(f"[NOTIF DEBUG] Sending signal alert for {account_name}")
                self.telegram_manager.send_signal_alert(account_name, result)
            except Exception as e:
                print(f"❌ Error sending signal alert for {account_name}: {e}")
                import traceback
                traceback.print_exc()

        # Handle entry alert
        if action == 'entry':
            try:
                print(f"[NOTIF DEBUG] Sending entry alert for {account_name}")
                success = self.telegram_manager.send_entry_alert(account_name, result)
                print(f"[NOTIF DEBUG] Entry alert sent: {success}")
            except Exception as e:
                print(f"❌ Error sending entry alert for {account_name}: {e}")
                import traceback
                traceback.print_exc()

        # Handle exit alert
        elif action == 'exit':
            try:
                print(f"[NOTIF DEBUG] Sending exit alert for {account_name}")
                # Use exit_data if available, otherwise use result
                exit_data = result.get('exit_data', result)
                self.telegram_manager.send_exit_alert(account_name, exit_data)
            except Exception as e:
                print(f"❌ Error sending exit alert for {account_name}: {e}")
                import traceback
                traceback.print_exc()

        # Handle error alert
        elif action == 'error':
            try:
                print(f"[NOTIF DEBUG] Sending error alert for {account_name}")
                error_msg = result.get('error', 'Unknown error')
                self.telegram_manager.send_error_alert(account_name, error_msg)
            except Exception as e:
                print(f"❌ Error sending error alert for {account_name}: {e}")
                import traceback
                traceback.print_exc()

    def _monitoring_loop(self):
        """Monitoring loop (runs in separate thread)"""
        check_interval = ORCHESTRATION.get('health_check_interval', 30)
        auto_restart = ORCHESTRATION.get('auto_restart_failed_accounts', True)
        max_restart_attempts = ORCHESTRATION.get('max_account_restart_attempts', 3)

        print(f"🔍 Monitoring started (check every {check_interval}s)")
        
        # Give accounts grace period to start and process initial data
        startup_grace_period = 10  # Wait 10 seconds before first health check
        print(f"   Waiting {startup_grace_period}s grace period for accounts to initialize...")
        time.sleep(startup_grace_period)

        while self.running:
            try:
                # Check account health
                for account_name, account_manager in self.account_managers.items():
                    if not account_manager.health_check():
                        print(f"⚠️ Health check failed for {account_name}")

                        if auto_restart and self.account_restart_counts[account_name] < max_restart_attempts:
                            print(f"🔄 Attempting to restart {account_name}")
                            if account_manager.restart():
                                self.account_restart_counts[account_name] += 1
                                print(f"✅ {account_name} restarted successfully")
                            else:
                                print(f"❌ Failed to restart {account_name}")

                # Check shared data provider health
                if not self.shared_data_provider.health_check():
                    print(f"⚠️ Shared data provider health check failed")

                # Print status every 10 minutes
                if hasattr(self, '_last_status_print'):
                    if (datetime.datetime.now() - self._last_status_print).total_seconds() > 600:
                        self._print_status()
                        self._last_status_print = datetime.datetime.now()
                else:
                    self._last_status_print = datetime.datetime.now()

                time.sleep(check_interval)

            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                time.sleep(10)


    def _print_status(self):
        """Print current status of all accounts"""
        print(f"\n📊 Multi-Account Status Report")
        print(f"   Runtime: {datetime.datetime.now() - self.start_time}")
        print(f"   Data processed: {self.total_market_data_processed:,}")

        # Data provider stats
        data_stats = self.shared_data_provider.get_stats()
        print(f"   Data source: {data_stats['data_source']} ({data_stats['data_points_collected']} points)")

        # Account stats
        print(f"   Account statuses:")
        for account_name, account_manager in self.account_managers.items():
            status = account_manager.get_status()
            print(f"     {account_name}: "
                  f"{'🟢' if status['running'] else '🔴'} "
                  f"Trades: {status.get('daily_trades', 0)} "
                  f"P&L: ${status.get('daily_pnl', 0.0):.2f}")

        # Telegram stats
        telegram_stats = self.telegram_manager.get_stats()
        print(f"   Telegram: {telegram_stats['active_accounts']}/{telegram_stats['total_accounts']} active, "
              f"{telegram_stats['total_notifications']} notifications sent")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        if signum == signal.SIGINT:
            print(f"\n⌨️  Ctrl+C pressed, shutting down gracefully...")
        elif signum == signal.SIGTERM:
            print(f"\n🛑 Termination signal received, shutting down gracefully...")
        else:
            print(f"\n🔔 Shutdown signal {signum} received, shutting down gracefully...")

        try:
            self.stop()
            print("✅ Shutdown complete")
        except Exception as e:
            print(f"❌ Error during shutdown: {e}")
        finally:
            sys.exit(0)

    def get_status(self) -> Dict:
        """Get comprehensive status of multi-account manager"""
        account_statuses = {}
        for account_name, account_manager in self.account_managers.items():
            account_statuses[account_name] = account_manager.get_status()

        return {
            'running': self.running,
            'start_time': self.start_time,
            'total_accounts': len(self.account_managers),
            'total_market_data_processed': self.total_market_data_processed,
            'data_provider_stats': self.shared_data_provider.get_stats() if self.shared_data_provider else None,
            'telegram_stats': self.telegram_manager.get_stats(),
            'account_statuses': account_statuses,
            'restart_counts': self.account_restart_counts
        }

    def run_forever(self):
        """Run the multi-account manager indefinitely"""
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n⌨️ Keyboard interrupt received")
        finally:
            self.stop()


def main(mode: str = None):
    """
    Main entry point for multi-account trading

    Args:
        mode: 'live' or 'paper'
    """
    if mode is None:
        print("❌ Mode must be specified: 'live' or 'paper'")
        print("Usage: python multi_account_trading.py <mode>")
        return

    print(f"🤖 SPY Multi-Account Trading Bot ({mode.upper()} Mode)")
    print("=" * 60)

    # Create and initialize manager
    manager = MultiAccountManager(mode)

    if not manager.initialize():
        print("❌ Failed to initialize, exiting...")
        return

    # Start trading
    if not manager.start():
        print("❌ Failed to start, exiting...")
        return

    # Run forever
    try:
        manager.run_forever()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        manager.stop()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("❌ Usage: python multi_account_trading.py <mode>")
        print("   mode: 'live' or 'paper'")
        sys.exit(1)

    mode = sys.argv[1].lower()
    if mode not in ['live', 'paper']:
        print("❌ Invalid mode. Must be 'live' or 'paper'")
        sys.exit(1)

    main(mode)