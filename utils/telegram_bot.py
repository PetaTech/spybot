"""
Telegram Bot Integration for SPY Trading Bot
Sends detailed trading alerts to Telegram
"""

import requests
import json
import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    bot_token: str
    chat_id: str
    enabled: bool = True

class TelegramNotifier:
    """Telegram notification service for trading alerts"""
    
    def __init__(self, config: TelegramConfig, account_holder_name: str = "Trading Account"):
        self.config = config
        self.account_holder_name = account_holder_name
        self.base_url = f"https://api.telegram.org/bot{config.bot_token}"
        
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram"""
        if not self.config.enabled:
            return True
            
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.config.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
            
        except Exception as e:
            print(f"[TELEGRAM ERROR] Failed to send message: {e}")
            return False
    
    def send_signal_alert(self, signal_data: Dict) -> bool:
        """Send detailed signal detection alert"""
        message = f"""
🎯 <b>SIGNAL DETECTED</b>
👤 Account: {self.account_holder_name}
📅 Detection Time: {signal_data['detection_time'].strftime('%Y-%m-%d %H:%M:%S %Z')}
📈 Detection Condition: {signal_data['condition']}
💰 Market Price: ${signal_data['market_price']:.2f}
📊 Move: {signal_data['move_percent']:.2f}% ({signal_data['move_points']:.2f}pts)
🌊 VIX Regime: {signal_data['vix_regime']}
⚡ VIX Value: {signal_data.get('vix_value', 'N/A')}
🎲 Active Trades: {signal_data['active_trades']}
📍 Symbol: {signal_data['symbol']}
        """.strip()
        
        return self.send_message(message)
    
    def send_entry_alert(self, entry_data: Dict) -> bool:
        """Send detailed trade entry alert"""
        positions_text = ""
        for i, pos in enumerate(entry_data['positions'], 1):
            positions_text += f"\n  - {pos['type']} {pos['symbol']} {pos['strike']} Exp: {pos['expiration']} Entry: ${pos['entry_price']:.2f} Contracts: {pos['contracts']}"
        
        message = f"""
✅ <b>TRADE ENTERED #{entry_data['trade_id']}</b>
👤 Account: {self.account_holder_name}
📅 Entry Time: {entry_data['entry_time'].strftime('%Y-%m-%d %H:%M:%S %Z')}
💰 Market Price at Entry: ${entry_data['market_price']:.2f}
🎯 Total Risk: ${entry_data['total_risk']:.0f} (${entry_data['risk_per_side']:.0f} each side)

📋 Selected Options:{positions_text}

💵 Entry Cost: ${entry_data['entry_cost']:.2f}
💸 Commission: ${entry_data['commission']:.2f}
💰 Total Entry Cost: ${entry_data['total_entry_cost']:.2f}
⏳ Expiration: {entry_data['expiration_date']}
🎲 Trades Active at Entry: {entry_data['trades_active']}
📍 Symbol: {entry_data['symbol']}

🎯 <b>Limit Orders Placed:</b>
{entry_data.get('limit_orders_info', 'Limit orders placed for profit targets')}
        """.strip()
        
        return self.send_message(message)
    
    def send_limit_hit_alert(self, limit_data: Dict) -> bool:
        """Send limit order fill alert"""
        message = f"""
🎯 <b>LIMIT ORDER FILLED!</b>
👤 Account: {self.account_holder_name}
📅 Fill Time: {limit_data['fill_time'].strftime('%Y-%m-%d %H:%M:%S %Z')}
💰 {limit_data['option_type']} Strike {limit_data['strike']} FILLED @ ${limit_data['fill_price']:.2f}
📊 Profit: {limit_data['profit_percent']:.1f}%
⚡ Action: Cancelling other limit orders & market selling remaining positions
🔄 Trade ID: {limit_data['trade_id']}
        """.strip()
        
        return self.send_message(message)
    
    def send_exit_alert(self, exit_data: Dict) -> bool:
        """Send detailed trade exit alert"""
        win_emoji = "✅" if exit_data['pnl'] >= 0 else "❌"
        result_text = "WIN" if exit_data['pnl'] >= 0 else "LOSS"
        
        message = f"""
🏁 <b>TRADE #{exit_data['trade_id']} COMPLETE</b>
👤 Account: {self.account_holder_name}
📅 Exit Time: {exit_data['exit_time'].strftime('%Y-%m-%d %H:%M:%S %Z')}
⏱️ Holding Time: {exit_data['holding_time']}
📍 Exit Reason: {exit_data['exit_reason']}

💵 Entry Cost: ${exit_data['entry_cost']:.2f}
💸 Entry Commission: ${exit_data['entry_commission']:.2f}
💰 Total Entry Cost: ${exit_data['total_entry_cost']:.2f}

💵 Exit Value: ${exit_data['exit_value']:.2f}
💸 Exit Commission: ${exit_data['exit_commission']:.2f}

💰 <b>P&L: ${exit_data['pnl']:+.2f}</b>
📊 Result: {result_text} {win_emoji}

📈 Daily P&L: ${exit_data['daily_pnl']:+.2f}
🎲 Daily Trades: {exit_data['daily_trades']}
🏆 Total Trades: {exit_data['total_trades']}
📊 Win Rate: {exit_data['win_rate']:.1f}%
💰 Total P&L: ${exit_data['total_pnl']:+.2f}
        """.strip()
        
        return self.send_message(message)
    
    def send_stop_loss_alert(self, stop_data: Dict) -> bool:
        """Send stop loss alert"""
        message = f"""
🚨 <b>STOP LOSS TRIGGERED!</b>
👤 Account: {self.account_holder_name}
📅 Time: {stop_data['trigger_time'].strftime('%Y-%m-%d %H:%M:%S %Z')}
🔴 Trade #{stop_data['trade_id']}: -{stop_data['loss_percent']:.1f}% loss limit hit
⚡ Closing all positions immediately
💰 Estimated Loss: ${stop_data['estimated_loss']:.2f}
📊 Stop Loss Limit: {stop_data['stop_loss_limit']:.1f}%
        """.strip()
        
        return self.send_message(message)
    
    def send_daily_limit_alert(self, limit_data: Dict) -> bool:
        """Send daily limits alert"""
        message = f"""
⚠️ <b>DAILY LIMITS WARNING</b>
👤 Account: {self.account_holder_name}
📅 Date: {limit_data['date']}
🎲 Trades: {limit_data['trades_today']}/{limit_data['max_daily_trades']}
💰 Daily P&L: ${limit_data['daily_pnl']:+.2f} (Limit: ${limit_data['daily_loss_limit']:+.2f})
⚡ Status: {limit_data['status']}
        """.strip()
        
        return self.send_message(message)
    
    def send_system_status_alert(self, status_data: Dict) -> bool:
        """Send system status alert"""
        status_emoji = "✅" if status_data['status'] == 'started' else "🛑"
        
        message = f"""
🤖 <b>BOT {status_data['status'].upper()}</b> {status_emoji}
👤 Account: {self.account_holder_name}
📅 Time: {status_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S %Z')}
🎯 Mode: {status_data['mode'].title()}
🏪 Market: {status_data['market_status']}
🌊 VIX Regime: {status_data.get('vix_regime', 'Unknown')}
💰 Risk per Side: ${status_data.get('risk_per_side', 0):.0f}
📊 Total Risk per Trade: ${status_data.get('total_risk', 0):.0f}
        """.strip()
        
        if status_data['status'] == 'stopped':
            message += f"\n💰 Final P&L: ${status_data.get('final_pnl', 0):+.2f}"
            message += f"\n🎲 Total Trades: {status_data.get('total_trades', 0)}"
            
        return self.send_message(message)

    def test_connection(self) -> bool:
        """Test Telegram bot connection"""
        test_message = f"""
🧪 <b>TEST MESSAGE</b>
👤 Account: {self.account_holder_name}
📅 Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
✅ Telegram integration working!
        """.strip()
        
        return self.send_message(test_message)