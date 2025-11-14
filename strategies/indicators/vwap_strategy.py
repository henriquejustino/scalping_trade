import pandas as pd
import numpy as np
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class VWAPStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("VWAP_Strategy")
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / \
                     df['volume'].cumsum()
        
        # VWAP bands
        df['vwap_std'] = df['typical_price'].rolling(window=20).std()
        df['vwap_upper'] = df['vwap'] + (df['vwap_std'] * 2)
        df['vwap_lower'] = df['vwap'] - (df['vwap_std'] * 2)
        
        df['price_above_vwap'] = df['close'] > df['vwap']
        df['distance_from_vwap'] = (df['close'] - df['vwap']) / df['vwap'] * 100
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < 30:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        current_close = df['close'].iloc[-1]
        vwap = df['vwap'].iloc[-1]
        vwap_lower = df['vwap_lower'].iloc[-1]
        vwap_upper = df['vwap_upper'].iloc[-1]
        distance_pct = abs(df['distance_from_vwap'].iloc[-1])
        
        # LONG: preço abaixo do VWAP
        if current_close < vwap and current_close <= vwap_lower:
            strength = min(distance_pct / 2.0, 1.0)
            
            # Volume confirma
            if df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1]:
                strength = min(strength + 0.2, 1.0)
            
            return 'BUY', strength
        
        # SHORT: preço acima do VWAP
        elif current_close > vwap and current_close >= vwap_upper:
            strength = min(distance_pct / 2.0, 1.0)
            
            if df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1]:
                strength = min(strength + 0.2, 1.0)
            
            return 'SELL', strength
        
        return None, 0.0
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        df = self.calculate_signals(df)
        vwap_std = Decimal(str(df['vwap_std'].iloc[-1]))
        
        if side == 'BUY':
            return entry_price - (vwap_std * Decimal('1.5'))
        else:
            return entry_price + (vwap_std * Decimal('1.5'))
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        df = self.calculate_signals(df)
        vwap = Decimal(str(df['vwap'].iloc[-1]))
        
        if side == 'BUY':
            distance = vwap - entry_price
            return vwap + distance
        else:
            distance = entry_price - vwap
            return vwap - distance