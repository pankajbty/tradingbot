"""
Intraday MIS trading bot for NSE stocks via Zerodha Kite Connect.

Daily usage:
    1. python auth.py          # generate fresh access token (once per day)
    2. python main.py          # run the trading bot
"""
from logger import setup_logger

logger = setup_logger("TradingApp")

from config import ENABLED_STRATEGIES
from market_data import MarketData
from risk_manager import RiskManager
from scheduler import TradingScheduler
from strategies import BollingerBandStrategy, FixedBuyStrategy, MACrossoverStrategy, OpenRangeBreakoutStrategy
from trader import Trader


def main():
    logger.info("=" * 60)
    logger.info("  Trading Bot Starting")
    logger.info("=" * 60)

    trader      = Trader()
    market_data = MarketData(trader.kite)
    risk_mgr    = RiskManager(trader)

    all_strategies = {
        "fixed_buy":           FixedBuyStrategy(trader, market_data, risk_mgr),
        "ma_crossover":        MACrossoverStrategy(trader, market_data, risk_mgr),
        "open_range_breakout": OpenRangeBreakoutStrategy(trader, market_data, risk_mgr),
        "bollinger":           BollingerBandStrategy(trader, market_data, risk_mgr),
    }

    active = {k: v for k, v in all_strategies.items() if k in ENABLED_STRATEGIES}
    logger.info(f"Active strategies: {list(active.keys())}")

    scheduler = TradingScheduler(active, risk_mgr, market_data)
    scheduler.setup()
    scheduler.run()


if __name__ == "__main__":
    main()
