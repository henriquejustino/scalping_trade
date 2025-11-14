import pandas as pd
import numpy as np
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class OrderFlowStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("Order_Flow")
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Delta volume (buy - sell pressure)
        df['delta_volume'] = np.where(
            df['close'] > df['open'],
            df['volume'],
            -df['volume']
        )
        
        df['cumulative_delta'] = df['delta_volume'].cumsum()
        df['delta_ma'] = df['delta_volume'].rolling(window=14).mean()
        
        # Volume profile
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # Price momentum
        df['price_change'] = df['close'].pct_change()
        df['volume_weighted_price'] = df['price_change'] * df['volume_ratio']
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < 30:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        delta = df['delta_volume'].iloc[-1]
        delta_ma = df['delta_ma'].iloc[-1]
        volume_ratio = df['volume_ratio'].iloc[-1]
        
        # LONG: buying pressure
        if delta > 0 and delta > delta_ma * 1.5 and volume_ratio > 1.2:
            strength = min((delta / abs(delta_ma)) / 5.0, 1.0)
            strength = min(strength * volume_ratio, 1.0)
            return 'BUY', strength
        
        # SHORT: selling pressure
        elif delta < 0 and delta < delta_ma * 1.5 and volume_ratio > 1.2:
            strength = min((abs(delta) / abs(delta_ma)) / 5.0, 1.0)
            strength = min(strength * volume_ratio, 1.0)
            return 'SELL', strength
        
        return None, 0.0
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        recent_range = df['high'].tail(10).max() - df['low'].tail(10).min()
        stop_distance = Decimal(str(recent_range)) * Decimal('0.4')
        
        if side == 'BUY':
            return entry_price - stop_distance
        else:
            return entry_price + stop_distance
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        recent_range = df['high'].tail(10).max() - df['low'].tail(10).min()
        tp_distance = Decimal(str(recent_range)) * Decimal('0.8')
        
        if side == 'BUY':
            return entry_price + tp_distance
        else:
            return entry_price - tp_distance