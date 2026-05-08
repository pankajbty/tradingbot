"""
Loads all bot configuration from the Django database (singleton models).
Falls back to config.py defaults if no DB row exists yet.

Usage (from management commands or anywhere Django is set up):
    from bot.config_loader import load_all_configs
    zerodha, risk, fixed_buy, ma, open_range, bollinger = load_all_configs()
"""

from .models import (
    BollingerConfig,
    FixedBuyConfig,
    MACrossoverConfig,
    OpenRangeConfig,
    RiskConfig,
    ZerodhaConfig,
)


def load_all_configs() -> tuple[dict, dict, dict, dict, dict, dict]:
    """
    Returns a 6-tuple of plain Python dicts in this order:
        (zerodha_cfg, risk_cfg, fixed_buy_cfg, ma_cfg, open_range_cfg, bollinger_cfg)

    Each dict has the exact same shape as the corresponding constant in config.py
    so the existing strategy / scheduler / trader code can use it without changes.
    """
    zerodha    = ZerodhaConfig.load().to_dict()
    risk       = RiskConfig.load().to_dict()
    fixed_buy  = FixedBuyConfig.load().to_dict()
    ma         = MACrossoverConfig.load().to_dict()
    open_range = OpenRangeConfig.load().to_dict()
    bollinger  = BollingerConfig.load().to_dict()

    return zerodha, risk, fixed_buy, ma, open_range, bollinger


def get_enabled_strategies() -> dict[str, bool]:
    """Returns which strategies are enabled according to the DB."""
    return {
        "fixed_buy":           FixedBuyConfig.load().enabled,
        "ma_crossover":        MACrossoverConfig.load().enabled,
        "open_range_breakout": OpenRangeConfig.load().enabled,
        "bollinger":           BollingerConfig.load().enabled,
    }
