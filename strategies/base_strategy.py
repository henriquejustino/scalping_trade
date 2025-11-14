from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, Tuple
from decimal import Decimal

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula sinais de compra/venda"""
        pass
    
    @abstractmethod
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        """
        Retorna (side, signal_strength)
        side: 'BUY', 'SELL', ou None
        signal_strength: 0.0 a 1.0
        """
        pass
    
    @abstractmethod
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """Calcula preço de stop loss"""
        pass
    
    @abstractmethod
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """Calcula preço de take profit"""
        pass