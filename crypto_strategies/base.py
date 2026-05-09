from abc import ABC, abstractmethod


class CryptoBaseStrategy(ABC):
    def __init__(self, trader, market_data, risk_manager):
        self.trader       = trader
        self.market_data  = market_data
        self.risk_manager = risk_manager

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def run(self):
        """Execute one iteration of the strategy."""
        pass
