"""
Loads all crypto bot configuration from the Django database (singleton models).
Falls back to crypto_config.py defaults if no DB row exists yet.

Usage (from management commands or anywhere Django is set up):
    from crypto.config_loader import load_all_configs
    exchange, risk, ema, supertrend, rsi_bb = load_all_configs()
"""
from __future__ import annotations

from .models import (
    CryptoExchangeConfig,
    CryptoRiskConfig,
    EMACrossoverConfig,
    RSIBBConfig,
    SupertrendConfig,
)


def load_exchange_config() -> dict:
    """Return exchange config as a plain dict."""
    return CryptoExchangeConfig.load().to_dict()


def load_risk_config() -> dict:
    """Return risk config as a plain dict."""
    return CryptoRiskConfig.load().to_dict()


def load_ema_config() -> dict:
    """Return EMA Crossover strategy config as a plain dict."""
    return EMACrossoverConfig.load().to_dict()


def load_supertrend_config() -> dict:
    """Return Supertrend strategy config as a plain dict."""
    return SupertrendConfig.load().to_dict()


def load_rsi_bb_config() -> dict:
    """Return RSI+BB strategy config as a plain dict."""
    return RSIBBConfig.load().to_dict()


def get_enabled_strategies() -> dict[str, bool]:
    """Return which crypto strategies are enabled according to the DB."""
    return {
        "ema_crossover": EMACrossoverConfig.load().enabled,
        "supertrend":    SupertrendConfig.load().enabled,
        "rsi_bb":        RSIBBConfig.load().enabled,
    }


def load_all_configs() -> tuple[dict, dict, dict, dict, dict]:
    """
    Returns a 5-tuple of plain Python dicts in this order:
        (exchange_cfg, risk_cfg, ema_cfg, supertrend_cfg, rsi_bb_cfg)

    Each dict has the exact same shape as the corresponding constant in
    crypto_config.py so the strategy / scheduler / trader code can use it
    without changes.
    """
    exchange   = load_exchange_config()
    risk       = load_risk_config()
    ema        = load_ema_config()
    supertrend = load_supertrend_config()
    rsi_bb     = load_rsi_bb_config()

    return exchange, risk, ema, supertrend, rsi_bb
