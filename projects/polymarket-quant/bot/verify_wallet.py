#!/usr/bin/env python3
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
bot_dir = Path(__file__).resolve().parent
parent_dir = bot_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from bot import config
from polymarket import AsyncSecureClient, RelayerApiKey

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("wallet_verifier")

async def verify():
    print("\n" + "="*65)
    print("       POLYMARKET WALLET & AUTHENTICATION DIAGNOSTIC")
    print("="*65)

    if not config.SIGNER_PRIVATE_KEY or not config.POLYMARKET_WALLET_ADDRESS:
        print("\n❌ ERROR: Credentials missing in bot/.env!")
        print("Please ensure SIGNER_PRIVATE_KEY and POLYMARKET_WALLET_ADDRESS are set.")
        print("="*65 + "\n")
        return False

    print(f"Configured Wallet Address: {config.POLYMARKET_WALLET_ADDRESS}")
    print("Connecting to Polymarket CLOB exchange via EIP-712 signer...")

    kwargs = {
        "private_key": config.SIGNER_PRIVATE_KEY,
        "wallet": config.POLYMARKET_WALLET_ADDRESS,
    }
    if config.POLYMARKET_RELAYER_API_KEY and config.POLYMARKET_RELAYER_API_KEY_ADDRESS:
        print("Using Polymarket Relayer API Key for gasless transactions.")
        kwargs["api_key"] = RelayerApiKey(
            key=config.POLYMARKET_RELAYER_API_KEY,
            address=config.POLYMARKET_RELAYER_API_KEY_ADDRESS,
        )

    try:
        async with await AsyncSecureClient.create(**kwargs) as client:
            print("✅ Polymarket CLOB authentication successful!")
            print(f"   Wallet Type: {client.wallet_type}")

            # 1. Check Collateral (USDC) Balance & Allowance
            try:
                bal = await client.get_balance_allowance(asset_type="COLLATERAL")
                actual_usdc = bal.balance / 1e6 if bal.balance > 10000 else bal.balance
                print(f"   USDC Collateral Balance:   {actual_usdc:.2f} USDC")
            except Exception as e:
                print(f"   ⚠️ Could not fetch collateral balance: {e}")

            # 2. Check Trading Approvals
            try:
                approvals = await client.get_trading_approvals_state()
                print(f"   Trading Approvals Ready:    {'YES' if approvals.is_fully_approved else 'NO (Approvals Required)'}")
                if not approvals.is_fully_approved:
                    print("\n⚠️ Note: Wallet requires one-time trading approvals on Polygon.")
                    print("You can approve them automatically via: python3 bot/verify_wallet.py --approve")
            except Exception as e:
                print(f"   ⚠️ Could not fetch trading approvals state: {e}")

            print("="*65)
            print("Diagnostic Complete: Read-only verification succeeded. Zero orders placed.\n")
            return True

    except Exception as e:
        print(f"\n❌ AUTHENTICATION FAILED: {e}")
        print("="*65 + "\n")
        return False

async def main():
    if "--approve" in sys.argv:
        kwargs = {
            "private_key": config.SIGNER_PRIVATE_KEY,
            "wallet": config.POLYMARKET_WALLET_ADDRESS,
        }
        if config.POLYMARKET_RELAYER_API_KEY and config.POLYMARKET_RELAYER_API_KEY_ADDRESS:
            kwargs["api_key"] = RelayerApiKey(
                key=config.POLYMARKET_RELAYER_API_KEY,
                address=config.POLYMARKET_RELAYER_API_KEY_ADDRESS,
            )
        async with await AsyncSecureClient.create(**kwargs) as client:
            print("Submitting trading approvals to Polymarket contracts...")
            await client.setup_trading_approvals()
            print("✅ Trading approvals granted successfully!")
    else:
        await verify()

if __name__ == "__main__":
    asyncio.run(main())
