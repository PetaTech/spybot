"""
SPY Multi-Account Trading Bot - Main Entry Point
Usage: python start.py <mode>
       python start.py live    # Start live trading
       python start.py paper   # Start paper trading
"""

import sys
import os

# Fix Windows encoding for emojis - must be done BEFORE any imports that print
if sys.platform == "win32":
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # Try to reconfigure stdout/stderr for UTF-8
    try:
        import codecs
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7 fallback
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

from core.multi_account_trading import main


def print_usage():
    """Print usage information"""
    print("🤖 SPY Multi-Account Trading Bot")
    print("=" * 50)
    print()
    print("Usage:")
    print("  python start.py live     # Start live trading mode")
    print("  python start.py paper    # Start paper trading mode")
    print()
    print("Before starting:")
    print("  1. Configure accounts in config/accounts.py")
    print("  2. Set up telegram bots for notifications")
    print("  3. Test with paper mode first!")
    print()
    print("Examples:")
    print("  python start.py paper    # Safe testing with sandbox")
    print("  python start.py live     # Real money trading")


def validate_setup():
    """Validate basic setup before starting"""
    errors = []

    # Check if accounts config exists
    if not os.path.exists('config/accounts.py'):
        errors.append("config/accounts.py not found")

    # Check if strategy config exists
    if not os.path.exists('config/strategy.py'):
        errors.append("config/strategy.py not found")

    # Check if logs directory exists
    if not os.path.exists('logs'):
        os.makedirs('logs', exist_ok=True)
        print("📁 Created logs directory")

    # Check if logs/accounts directory exists
    if not os.path.exists('logs/accounts'):
        os.makedirs('logs/accounts', exist_ok=True)
        print("📁 Created logs/accounts directory")

    return errors


def main_entry():
    """Main entry point"""
    if len(sys.argv) != 2:
        print_usage()
        sys.exit(1)

    mode = sys.argv[1].lower()
    if mode not in ['live', 'paper']:
        print("❌ Invalid mode. Must be 'live' or 'paper'")
        print()
        print_usage()
        sys.exit(1)

    # Validate setup
    print("🔍 Validating setup...")
    errors = validate_setup()
    if errors:
        print("❌ Setup validation failed:")
        for error in errors:
            print(f"   • {error}")
        sys.exit(1)

    print("✅ Setup validation passed")
    print()

    # Show warning for live mode
    if mode == 'live':
        print("⚠️  LIVE TRADING MODE WARNING ⚠️")
        print("=" * 40)
        print("• You are about to start LIVE trading with REAL MONEY")
        print("• Make sure you have tested thoroughly in paper mode")
        print("• Check your account configurations carefully")
        print("• Monitor the bot closely during live trading")
        print("=" * 40)
        print()

        response = input("Type 'YES' to confirm live trading: ").strip()
        if response != 'YES':
            print("❌ Live trading cancelled")
            sys.exit(1)

    elif mode == 'paper':
        print("✅ PAPER TRADING MODE")
        print("=" * 30)
        print("• Safe testing with sandbox accounts")
        print("• No real money at risk")
        print("• Perfect for strategy validation")
        print("=" * 30)
        print()

    # Import and validate accounts configuration
    try:
        from config.accounts import get_enabled_accounts, get_account_summary

        enabled_accounts = get_enabled_accounts(mode)
        if not enabled_accounts:
            print(f"❌ No enabled accounts found for {mode} mode")
            print("   Check config/accounts.py and enable some accounts")
            sys.exit(1)

        summary = get_account_summary(mode)
        print(f"📊 Found {summary['enabled_accounts']} enabled accounts for {mode} mode")

    except Exception as e:
        print(f"❌ Error loading account configuration: {e}")
        sys.exit(1)

    # Start the bot
    print(f"🚀 Starting SPY Multi-Account Trading Bot in {mode.upper()} mode...")
    print()

    try:
        main(mode)
    except KeyboardInterrupt:
        print("\n⌨️  Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main_entry()