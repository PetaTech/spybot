"""
Account Manager for Multi-Account Trading
Manages individual account with strategy overrides and independent signal processing
"""

import datetime
import os
import logging
import requests
from typing import Dict, Optional, Any
from dataclasses import asdict

from core.trading_engine import TradingEngine
from core.shared_data_provider import MarketData
from utils.tradier_api import set_api_credentials
from config.strategy import *  # Import all default strategy settings


class AccountManager:
    """
    Manages a single trading account with strategy overrides
    Processes shared market data independently for signal generation
    """

    def __init__(self, account_config: Dict):
        """
        Initialize account manager

        Args:
            account_config: Account configuration from config/accounts.py
        """
        self.account_config = account_config
        self.account_index = account_config.get('account_index', 0)
        self.account_id = account_config['account_id']
        self.access_token = account_config['access_token']
        self.api_url = account_config['api_url']
        self.mode = account_config['mode']  # 'live' or 'paper'
        self.enabled = account_config.get('enabled', True)

        # Fetch account name from Tradier API
        self.account_name = self._fetch_account_name()
        
        # Simple check: if name is just account ID, it means credentials failed
        if self.account_name.startswith(f"Account {self.account_id}"):
            print(f"❌ CREDENTIAL PROBLEM for Account #{self.account_index}")
            print(f"   Cannot fetch account name - credentials may be invalid")
            print(f"   Account will be skipped for security")
            raise ValueError(f"Account #{self.account_index} has credential problems - cannot proceed")

        # Set up logging for this account
        self._setup_logging()

        # Build strategy configuration with overrides
        self.strategy_config = self._build_strategy_config()

        # DO NOT set global API credentials here - each account will use its own via api_url/access_token/account_id params
        # The trading engine's order executor will use the account-specific credentials passed in

        # Create trading engine for this account
        self.trading_engine = TradingEngine(
            config=self.strategy_config,
            data_provider=None,  # We'll provide data via process_market_data()
            mode=self.mode,
            api_url=self.api_url,
            access_token=self.access_token,
            account_id=self.account_id,
            telegram_config=self.get_telegram_config()
        )

        # Initialize VIX parameters at startup to avoid Unknown/None in first alerts
        try:
            if hasattr(self.trading_engine, '_set_vix_parameters'):
                # Force an initial refresh; method already caches thereafter
                self.trading_engine._set_vix_parameters(force=True, target_datetime=None)
        except Exception as e:
            self.log(f"Initial VIX initialization failed: {e}", level='WARNING')

        # Account state
        self.is_running = False
        self.market_data_count = 0
        self.last_signal_time = None
        self.last_trade_time = None

        self.log(f"AccountManager initialized for {self.account_name} ({self.mode} mode)")

    def _fetch_account_name(self) -> str:
        """
        Fetch account name from Tradier API

        Returns:
            str: Account name from Tradier API or fallback name
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json'
            }

            # Get user profile to fetch account name
            url = f"{self.api_url}/user/profile"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                profile = data.get('profile', {})
                account_name = profile.get('name', profile.get('account', {}).get('account_number', ''))

                if account_name:
                    return f"{account_name} ({self.mode.upper()})"

            # If profile doesn't work, try account endpoint
            url = f"{self.api_url}/accounts/{self.account_id}"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                account = data.get('account', {})
                account_name = account.get('account_number', account.get('type', ''))

                if account_name:
                    return f"{account_name} ({self.mode.upper()})"

            # Fallback to account ID if API calls fail
            return f"Account {self.account_id} ({self.mode.upper()})"

        except Exception as e:
            # Fallback to a default name if API call fails
            fallback_name = f"Account {self.account_index} ({self.mode.upper()})"
            print(f"⚠️ Failed to fetch account name from Tradier API: {e}")
            print(f"   Using fallback name: {fallback_name}")
            return fallback_name

    def _setup_logging(self):
        """Setup separate logging for this account"""
        log_config = self.account_config.get('logging', {})
        # Use configured log prefix or fallback to account index
        log_prefix = log_config.get('log_prefix', f'account{self.account_index}_{self.mode}')
        log_level = log_config.get('log_level', 'INFO')

        # Create logs/accounts directory if it doesn't exist
        log_dir = 'logs/accounts'
        os.makedirs(log_dir, exist_ok=True)

        # Setup logger for this account using account index for consistency
        logger_name = f"account_{self.account_index}_{self.mode}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(getattr(logging, log_level))

        # Create file handler
        log_file = os.path.join(log_dir, f"{log_prefix}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level))

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)

        # Add handler if not already added
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)

    def _build_strategy_config(self) -> Dict[str, Any]:
        """
        Build strategy configuration with overrides
        Uses config/strategy.py as base, applies account-specific overrides
        """
        # Start with all default strategy settings
        strategy_config = {}

        # Get all uppercase variables from config.strategy (default settings)
        import config.strategy as default_strategy
        for attr_name in dir(default_strategy):
            if not attr_name.startswith('_') and attr_name.isupper():
                strategy_config[attr_name] = getattr(default_strategy, attr_name)

        # Apply account-specific overrides
        strategy_overrides = self.account_config.get('strategy_overrides', {})
        for key, value in strategy_overrides.items():
            if key in strategy_config:
                old_value = strategy_config[key]
                strategy_config[key] = value
                self.log(f"Strategy override: {key} = {value} (was {old_value})")
            else:
                strategy_config[key] = value
                self.log(f"Strategy addition: {key} = {value}")

        # Add account-specific metadata
        strategy_config.update({
            'ACCOUNT_NAME': self.account_name,
            'ACCOUNT_ID': self.account_id,
            'MODE': self.mode,
            'LOG_DIR': f'logs/accounts',
            'LOG_PREFIX': self.account_config.get('logging', {}).get('log_prefix', self.account_name.lower())
        })

        # Convert time strings to datetime.time objects if needed
        if 'MAX_ENTRY_TIME' in strategy_config and isinstance(strategy_config['MAX_ENTRY_TIME'], str):
            strategy_config['MAX_ENTRY_TIME'] = datetime.datetime.strptime(
                strategy_config['MAX_ENTRY_TIME'], '%H:%M'
            ).time()

        return strategy_config

    def start(self):
        """Start the account manager"""
        if not self.enabled:
            self.log(f"Account {self.account_name} is disabled, not starting")
            return False

        self.log(f"Starting account manager for {self.account_name}")
        self.is_running = True
        return True

    def stop(self):
        """Stop the account manager"""
        self.log(f"Stopping account manager for {self.account_name}")
        self.is_running = False

        # Finish trading engine properly
        if hasattr(self.trading_engine, 'finish'):
            self.trading_engine.finish()

    def get_status(self) -> Dict:
        """Get current account status"""
        status = {
            'account_name': self.account_name,
            'account_id': self.account_id,
            'mode': self.mode,
            'enabled': self.enabled,
            'running': self.is_running,
            'market_data_count': self.market_data_count,
            'last_signal_time': self.last_signal_time,
            'last_trade_time': self.last_trade_time,
        }

        # Add trading engine status if available
        if hasattr(self.trading_engine, 'get_status'):
            engine_status = self.trading_engine.get_status()
            status.update({
                'active_trades': len(getattr(self.trading_engine, 'active_trades', [])),
                'daily_trades': getattr(self.trading_engine, 'daily_trades', 0),
                'daily_pnl': getattr(self.trading_engine, 'daily_pnl', 0.0),
                'total_pnl': getattr(self.trading_engine, 'total_pnl', 0.0),
            })

        return status

    def get_strategy_config_summary(self) -> Dict:
        """Get summary of strategy configuration for this account"""
        key_settings = [
            'RISK_PER_SIDE', 'MAX_DAILY_TRADES', 'MAX_DAILY_LOSS',
            'STOP_LOSS_PERCENTAGE', 'COOLDOWN_PERIOD', 'PRICE_WINDOW_SECONDS',
            'VIX_THRESHOLD', 'HIGH_VOL_MOVE_THRESHOLD', 'LOW_VOL_MOVE_THRESHOLD'
        ]

        summary = {}
        for key in key_settings:
            if key in self.strategy_config:
                summary[key] = self.strategy_config[key]

        # Add override information
        overrides = self.account_config.get('strategy_overrides', {})
        summary['overrides_applied'] = list(overrides.keys())
        summary['override_count'] = len(overrides)
        summary['account_overrides'] = overrides  # Add actual override values

        return summary

    def log(self, message: str, level: str = 'INFO'):
        """Log message for this account"""
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(f"[{self.account_name}] {message}")

        # Also print to console for important messages
        if level in ['ERROR', 'WARNING']:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] [{self.account_name}] {level}: {message}")


    def update_config(self, new_overrides: Dict):
        """
        Update strategy overrides dynamically
        Note: This requires restarting the trading engine
        """
        self.log(f"Updating strategy configuration with: {new_overrides}")

        # Update account config
        if 'strategy_overrides' not in self.account_config:
            self.account_config['strategy_overrides'] = {}

        self.account_config['strategy_overrides'].update(new_overrides)

        # Rebuild strategy config
        self.strategy_config = self._build_strategy_config()

        # Note: In a full implementation, you'd need to restart the trading engine
        # For now, just log the change
        self.log("Strategy configuration updated (restart required for full effect)")

    def get_telegram_config(self) -> Optional[Dict]:
        """Get telegram configuration for this account"""
        return self.account_config.get('telegram')

    def can_trade(self, current_time: datetime.datetime) -> bool:
        """
        Check if this account can trade based on its state

        Args:
            current_time: Current market time

        Returns:
            bool: True if account can trade, False otherwise
        """
        engine = self.trading_engine

        # Check if account is enabled and running
        if not self.enabled or not self.is_running:
            return False

        # Check cooldown period
        if engine.last_trade_time is not None:
            cooldown = self.strategy_config.get('COOLDOWN_PERIOD', 20 * 60)
            seconds_since_last_trade = (current_time - engine.last_trade_time).total_seconds()
            if seconds_since_last_trade < cooldown:
                return False

        # Check daily trade limit
        max_daily_trades = self.strategy_config.get('MAX_DAILY_TRADES', 5)
        if engine.daily_trades >= max_daily_trades:
            return False

        # Check daily loss limit
        max_daily_loss = self.strategy_config.get('MAX_DAILY_LOSS', 1000)
        if engine.daily_pnl <= -max_daily_loss:
            return False

        # Check emergency stop loss
        emergency_stop_loss = self.strategy_config.get('EMERGENCY_STOP_LOSS', 2000)
        if engine.total_pnl <= -emergency_stop_loss:
            return False

        return True

    def get_cannot_trade_reason(self, current_time: datetime.datetime) -> str:
        """
        Get reason why account cannot trade

        Args:
            current_time: Current market time

        Returns:
            str: Reason why account cannot trade
        """
        engine = self.trading_engine

        if not self.enabled:
            return "Account disabled"

        if not self.is_running:
            return "Account not running"

        # Check cooldown
        if engine.last_trade_time is not None:
            cooldown = self.strategy_config.get('COOLDOWN_PERIOD', 20 * 60)
            seconds_since_last_trade = (current_time - engine.last_trade_time).total_seconds()
            if seconds_since_last_trade < cooldown:
                remaining = cooldown - seconds_since_last_trade
                return f"In cooldown ({remaining:.0f}s remaining)"

        # Check daily trade limit
        max_daily_trades = self.strategy_config.get('MAX_DAILY_TRADES', 5)
        if engine.daily_trades >= max_daily_trades:
            return f"Max daily trades reached ({engine.daily_trades}/{max_daily_trades})"

        # Check daily loss limit
        max_daily_loss = self.strategy_config.get('MAX_DAILY_LOSS', 1000)
        if engine.daily_pnl <= -max_daily_loss:
            return f"Max daily loss reached (${engine.daily_pnl:.2f}/-${max_daily_loss})"

        # Check emergency stop loss
        emergency_stop_loss = self.strategy_config.get('EMERGENCY_STOP_LOSS', 2000)
        if engine.total_pnl <= -emergency_stop_loss:
            return f"Emergency stop loss triggered (${engine.total_pnl:.2f}/-${emergency_stop_loss})"

        return "Ready to trade"