"""
Multi-Account Telegram Notification System
Manages separate telegram bots for each trading account
"""

import datetime
from typing import Dict, Optional, List
from utils.telegram_bot import TelegramNotifier, TelegramConfig


class MultiAccountTelegramManager:
    """
    Manages telegram notifications for multiple accounts
    Each account gets its own bot and chat for isolated notifications
    """

    def __init__(self):
        self.account_notifiers: Dict[str, TelegramNotifier] = {}
        self.notification_counts: Dict[str, int] = {}

    def add_account(self, account_name: str, telegram_config: Dict) -> bool:
        """
        Add telegram notifier for an account

        Args:
            account_name: Name of the account
            telegram_config: Telegram configuration from account config

        Returns:
            bool: True if successfully added
        """
        if not telegram_config.get('enabled', False):
            print(f"📱 Telegram disabled for account: {account_name}")
            return False

        try:
            config = TelegramConfig(
                bot_token=telegram_config['bot_token'],
                chat_id=telegram_config['chat_id'],
                enabled=telegram_config.get('enabled', True)
            )

            notifier = TelegramNotifier(config, account_holder_name=account_name)
            self.account_notifiers[account_name] = notifier
            self.notification_counts[account_name] = 0

            # Test the connection
            test_message = f"🤖 {account_name} telegram notifications activated"
            if notifier.send_message(test_message):
                print(f"📱 Telegram activated for account: {account_name}")
                return True
            else:
                print(f"❌ Telegram test failed for account: {account_name}")
                return False

        except Exception as e:
            print(f"❌ Failed to setup telegram for {account_name}: {e}")
            return False

    def send_signal_alert(self, account_name: str, signal_data: Dict) -> bool:
        """Send signal alert for specific account"""
        notifier = self.account_notifiers.get(account_name)
        if not notifier:
            return False

        try:
            # Enhance signal data with account info
            enhanced_signal_data = signal_data.copy()
            enhanced_signal_data['account_name'] = account_name

            # Backward-compat mapping: ensure required fields exist for TelegramNotifier
            # detection_time
            if 'detection_time' not in enhanced_signal_data:
                enhanced_signal_data['detection_time'] = enhanced_signal_data.get('timestamp', datetime.datetime.now())
            # market_price
            if 'market_price' not in enhanced_signal_data and 'price' in enhanced_signal_data:
                enhanced_signal_data['market_price'] = enhanced_signal_data['price']
            # move_points (optional)
            if 'move_points' not in enhanced_signal_data and 'move_percent' in enhanced_signal_data and 'market_price' in enhanced_signal_data:
                # Fallback: cannot compute exact points without window ref; set to 0.0 if missing
                enhanced_signal_data['move_points'] = enhanced_signal_data.get('move_points', 0.0)
            # condition text
            if 'condition' not in enhanced_signal_data:
                mp = enhanced_signal_data.get('move_percent', 0.0)
                enhanced_signal_data['condition'] = f"Move {mp:.2f}% in window, signal detected"
            # active_trades
            if 'active_trades' not in enhanced_signal_data and 'trades_active' in enhanced_signal_data:
                enhanced_signal_data['active_trades'] = enhanced_signal_data['trades_active']
            # symbol
            if 'symbol' not in enhanced_signal_data and 'account_symbol' in enhanced_signal_data:
                enhanced_signal_data['symbol'] = enhanced_signal_data['account_symbol']
            if 'symbol' not in enhanced_signal_data:
                enhanced_signal_data['symbol'] = 'SPY'
            # vix fields: prefer engine-provided values on the result
            if 'vix_regime' not in enhanced_signal_data and 'vix_regime' in signal_data:
                enhanced_signal_data['vix_regime'] = signal_data.get('vix_regime', 'Unknown')
            if 'vix_value' not in enhanced_signal_data and 'vix_value' in signal_data:
                enhanced_signal_data['vix_value'] = signal_data.get('vix_value', None)
            if 'vix_regime' not in enhanced_signal_data:
                enhanced_signal_data['vix_regime'] = 'Unknown'
            if 'vix_value' not in enhanced_signal_data:
                enhanced_signal_data['vix_value'] = None

            success = notifier.send_signal_alert(enhanced_signal_data)
            if success:
                self.notification_counts[account_name] += 1
            return success

        except Exception as e:
            print(f"❌ Failed to send signal alert for {account_name}: {e}")
            return False

    def send_entry_alert(self, account_name: str, entry_data: Dict) -> bool:
        """Send trade entry alert for specific account"""
        print(f"[TELEGRAM DEBUG] send_entry_alert called for {account_name}")
        print(f"[TELEGRAM DEBUG] entry_data keys: {list(entry_data.keys())}")
        notifier = self.account_notifiers.get(account_name)
        if not notifier:
            print(f"[TELEGRAM DEBUG] No notifier found for {account_name}")
            return False

        try:
            # Enhance entry data with account info
            enhanced_entry_data = entry_data.copy()
            enhanced_entry_data['account_name'] = account_name

            # Backfill required fields with safe defaults
            import datetime as _dt
            if 'entry_time' not in enhanced_entry_data or not isinstance(enhanced_entry_data.get('entry_time'), _dt.datetime):
                enhanced_entry_data['entry_time'] = _dt.datetime.now()
            if 'trade_id' not in enhanced_entry_data:
                enhanced_entry_data['trade_id'] = 0
            if 'market_price' not in enhanced_entry_data and 'price' in enhanced_entry_data:
                enhanced_entry_data['market_price'] = enhanced_entry_data['price']
            if 'total_risk' not in enhanced_entry_data:
                enhanced_entry_data['total_risk'] = 0
            if 'risk_per_side' not in enhanced_entry_data:
                enhanced_entry_data['risk_per_side'] = 0
            if 'entry_cost' not in enhanced_entry_data:
                enhanced_entry_data['entry_cost'] = 0.0
            if 'commission' not in enhanced_entry_data and 'entry_commission' in enhanced_entry_data:
                enhanced_entry_data['commission'] = enhanced_entry_data['entry_commission']
            if 'commission' not in enhanced_entry_data:
                enhanced_entry_data['commission'] = 0.0
            if 'total_entry_cost' not in enhanced_entry_data:
                enhanced_entry_data['total_entry_cost'] = enhanced_entry_data.get('entry_cost', 0.0) + enhanced_entry_data.get('commission', 0.0)
            if 'expiration_date' not in enhanced_entry_data:
                enhanced_entry_data['expiration_date'] = ''
            if 'trades_active' not in enhanced_entry_data and 'active_trades' in enhanced_entry_data:
                enhanced_entry_data['trades_active'] = enhanced_entry_data['active_trades']
            if 'trades_active' not in enhanced_entry_data:
                enhanced_entry_data['trades_active'] = 0
            if 'symbol' not in enhanced_entry_data:
                enhanced_entry_data['symbol'] = 'SPY'
            if 'limit_orders_info' not in enhanced_entry_data:
                enhanced_entry_data['limit_orders_info'] = 'Limit orders placed for profit targets'

            # Normalize positions: prefer entry_positions; convert objects to dicts if needed
            print(f"[TELEGRAM DEBUG] Normalizing positions...")
            print(f"[TELEGRAM DEBUG] entry_positions exists: {'entry_positions' in enhanced_entry_data}")
            print(f"[TELEGRAM DEBUG] positions exists: {'positions' in enhanced_entry_data}")
            positions_source = enhanced_entry_data.get('entry_positions') or enhanced_entry_data.get('positions') or []
            print(f"[TELEGRAM DEBUG] positions_source type: {type(positions_source)}, len: {len(positions_source) if positions_source else 0}")
            normalized_positions = []
            for i, p in enumerate(positions_source):
                print(f"[TELEGRAM DEBUG] Processing position {i}: type={type(p)}, is_dict={isinstance(p, dict)}")
                if isinstance(p, dict):
                    normalized_positions.append(p)
                    print(f"[TELEGRAM DEBUG] Position {i} added as dict: {p}")
                else:
                    try:
                        norm_pos = {
                            'type': getattr(p, 'type', '?'),
                            'symbol': getattr(p, 'symbol', 'SPY'),
                            'strike': getattr(p, 'strike', 0),
                            'expiration': getattr(p, 'expiration_date', ''),
                            'entry_price': getattr(p, 'entry_price', 0.0),
                            'contracts': getattr(p, 'contracts', 0)
                        }
                        normalized_positions.append(norm_pos)
                        print(f"[TELEGRAM DEBUG] Position {i} converted to dict: {norm_pos}")
                    except Exception as e:
                        print(f"[TELEGRAM DEBUG] Failed to normalize position {i}: {e}")
                        continue
            enhanced_entry_data['positions'] = normalized_positions
            print(f"[TELEGRAM DEBUG] About to call notifier.send_entry_alert with {len(normalized_positions)} positions")
            print(f"[TELEGRAM DEBUG] normalized_positions: {normalized_positions}")
            success = notifier.send_entry_alert(enhanced_entry_data)
            print(f"[TELEGRAM DEBUG] notifier.send_entry_alert returned: {success}")
            if success:
                self.notification_counts[account_name] += 1
            else:
                print(f"❌ Entry alert send returned False for {account_name}")
            return success

        except Exception as e:
            print(f"❌ Failed to send entry alert for {account_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def send_exit_alert(self, account_name: str, exit_data: Dict) -> bool:
        """Send trade exit alert for specific account"""
        notifier = self.account_notifiers.get(account_name)
        if not notifier:
            return False

        try:
            # Enhance exit data with account info
            enhanced_exit_data = exit_data.copy()
            enhanced_exit_data['account_name'] = account_name

            success = notifier.send_exit_alert(enhanced_exit_data)
            if success:
                self.notification_counts[account_name] += 1
            return success

        except Exception as e:
            print(f"❌ Failed to send exit alert for {account_name}: {e}")
            return False

    def send_account_status(self, account_name: str, status_data: Dict) -> bool:
        """Send account status update"""
        notifier = self.account_notifiers.get(account_name)
        if not notifier:
            return False

        try:
            # Format status message
            message = self._format_status_message(account_name, status_data)
            success = notifier.send_message(message)
            if success:
                self.notification_counts[account_name] += 1
            return success

        except Exception as e:
            print(f"❌ Failed to send status update for {account_name}: {e}")
            return False

    def send_error_alert(self, account_name: str, error_message: str) -> bool:
        """Send error alert for specific account"""
        notifier = self.account_notifiers.get(account_name)
        if not notifier:
            return False

        try:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            message = f"🚨 <b>{account_name} ERROR</b>\n\n"
            message += f"⏰ Time: {timestamp}\n"
            message += f"❌ Error: {error_message}\n\n"
            message += f"🔍 Check logs for details"

            success = notifier.send_message(message)
            if success:
                self.notification_counts[account_name] += 1
            return success

        except Exception as e:
            print(f"❌ Failed to send error alert for {account_name}: {e}")
            return False

    def send_startup_message(self, account_name: str, config_summary: Dict) -> bool:
        """Send startup message with account configuration"""
        notifier = self.account_notifiers.get(account_name)
        if not notifier:
            return False

        try:
            message = f"🚀 <b>{account_name} Started</b>\n\n"
            message += f"🏦 Account: {config_summary.get('account_id', 'N/A')}\n"
            message += f"🎯 Mode: {config_summary.get('mode', 'N/A')}\n"
            message += f"💰 Risk per side: ${config_summary.get('RISK_PER_SIDE', 'N/A')}\n"
            message += f"📊 Max daily trades: {config_summary.get('MAX_DAILY_TRADES', 'N/A')}\n"
            message += f"🛑 Stop loss: {config_summary.get('STOP_LOSS_PERCENTAGE', 'N/A')}%\n"

            message += f"\n✅ Ready for trading!"

            success = notifier.send_message(message)
            if success:
                self.notification_counts[account_name] += 1
            return success

        except Exception as e:
            print(f"❌ Failed to send startup message for {account_name}: {e}")
            return False

    def send_daily_summary(self, account_name: str, summary_data: Dict) -> bool:
        """Send daily trading summary"""
        notifier = self.account_notifiers.get(account_name)
        if not notifier:
            return False

        try:
            message = f"📊 <b>{account_name} Daily Summary</b>\n\n"
            message += f"📅 Date: {datetime.date.today()}\n"
            message += f"🔢 Trades: {summary_data.get('daily_trades', 0)}\n"
            message += f"💰 P&L: ${summary_data.get('daily_pnl', 0.0):.2f}\n"
            message += f"📈 Win Rate: {summary_data.get('win_rate', 0.0):.1f}%\n"
            message += f"🎯 Active Positions: {summary_data.get('active_trades', 0)}\n"

            total_pnl = summary_data.get('total_pnl', 0.0)
            if total_pnl > 0:
                message += f"🟢 Total P&L: +${total_pnl:.2f}"
            elif total_pnl < 0:
                message += f"🔴 Total P&L: ${total_pnl:.2f}"
            else:
                message += f"⚪ Total P&L: $0.00"

            success = notifier.send_message(message)
            if success:
                self.notification_counts[account_name] += 1
            return success

        except Exception as e:
            print(f"❌ Failed to send daily summary for {account_name}: {e}")
            return False

    def send_shutdown_alert(self, account_name: str, final_data: Dict) -> bool:
        """Send shutdown/stop alert for specific account"""
        print(f"[DEBUG] Looking for notifier for account: '{account_name}'")
        print(f"[DEBUG] Available notifiers: {list(self.account_notifiers.keys())}")

        notifier = self.account_notifiers.get(account_name)
        if not notifier:
            print(f"[DEBUG] No notifier found for '{account_name}'")
            return False

        try:
            # Use the existing system status alert method
            status_data = {
                'status': 'stopped',
                'timestamp': final_data.get('timestamp', datetime.datetime.now()),
                'mode': final_data.get('mode', 'unknown'),
                'market_status': 'CLOSED',
                'final_pnl': final_data.get('total_pnl', 0),
                'total_trades': final_data.get('total_trades', 0),
                'account_name': account_name
            }

            print(f"[DEBUG] Attempting to send shutdown alert with data: {status_data}")
            success = notifier.send_system_status_alert(status_data)
            print(f"[DEBUG] Telegram send result: {success}")
            if success:
                self.notification_counts[account_name] += 1
            return success

        except Exception as e:
            print(f"❌ Failed to send shutdown alert for {account_name}: {e}")
            return False

    def broadcast_message(self, message: str, exclude_accounts: List[str] = None) -> Dict[str, bool]:
        """
        Broadcast message to all accounts

        Args:
            message: Message to send
            exclude_accounts: List of account names to exclude

        Returns:
            Dict mapping account_name -> success status
        """
        if exclude_accounts is None:
            exclude_accounts = []

        results = {}
        for account_name, notifier in self.account_notifiers.items():
            if account_name in exclude_accounts:
                continue

            try:
                success = notifier.send_message(message)
                results[account_name] = success
                if success:
                    self.notification_counts[account_name] += 1
            except Exception as e:
                print(f"❌ Broadcast failed for {account_name}: {e}")
                results[account_name] = False

        return results

    def get_stats(self) -> Dict:
        """Get telegram notification statistics"""
        return {
            'total_accounts': len(self.account_notifiers),
            'active_accounts': len([n for n in self.account_notifiers.values() if n.config.enabled]),
            'notification_counts': self.notification_counts.copy(),
            'total_notifications': sum(self.notification_counts.values())
        }

    def _format_status_message(self, account_name: str, status_data: Dict) -> str:
        """Format account status message"""
        message = f"📊 <b>{account_name} Status</b>\n\n"
        message += f"🏃 Running: {'✅' if status_data.get('running') else '❌'}\n"
        message += f"📊 Data Points: {status_data.get('market_data_count', 0):,}\n"
        message += f"🎯 Active Trades: {status_data.get('active_trades', 0)}\n"
        message += f"📈 Daily Trades: {status_data.get('daily_trades', 0)}\n"
        message += f"💰 Daily P&L: ${status_data.get('daily_pnl', 0.0):.2f}\n"

        last_signal = status_data.get('last_signal_time')
        if last_signal:
            message += f"🔔 Last Signal: {last_signal.strftime('%H:%M:%S')}\n"

        last_trade = status_data.get('last_trade_time')
        if last_trade:
            message += f"💼 Last Trade: {last_trade.strftime('%H:%M:%S')}\n"

        return message

    def test_all_connections(self) -> Dict[str, bool]:
        """Test all telegram connections"""
        results = {}
        test_message = "🧪 Connection test"

        for account_name, notifier in self.account_notifiers.items():
            try:
                success = notifier.send_message(test_message)
                results[account_name] = success
            except Exception as e:
                print(f"❌ Test failed for {account_name}: {e}")
                results[account_name] = False

        return results

    def remove_account(self, account_name: str):
        """Remove telegram notifier for an account"""
        if account_name in self.account_notifiers:
            del self.account_notifiers[account_name]
            del self.notification_counts[account_name]
            print(f"📱 Removed telegram notifier for: {account_name}")

    def get_account_notifier(self, account_name: str) -> Optional[TelegramNotifier]:
        """Get telegram notifier for specific account"""
        return self.account_notifiers.get(account_name)