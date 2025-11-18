import pandas as pd
import numpy as np
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class OrderFlowStrategy(BaseStrategy):
    def __init__(self, atr_multiplier=1.8):
        super().__init__("Order_Flow")
        self.atr_multiplier = atr_multiplier
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Delta volume (buy - sell pressure)
        df['delta_volume'] = np.where(
            df['close'] >= df['open'],
            df['volume'],
            -df['volume']
        )
        
        df['cumulative_delta'] = df['delta_volume'].cumsum()
        df['delta_ma_14'] = df['delta_volume'].rolling(window=14).mean()
        df['delta_std'] = df['delta_volume'].rolling(window=14).std()
        
        # Volume profile
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / (df['volume_ma'] + 1e-10)
        
        # ATR usando pandas rolling corretamente
        df['tr'] = pd.DataFrame({
            'hl': df['high'] - df['low'],
            'hc': abs(df['high'] - df['close'].shift(1)),
            'lc': abs(df['low'] - df['close'].shift(1))
        }).max(axis=1)
        
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        # Força da pressão (z-score do delta volume)
        df['delta_zscore'] = (df['delta_volume'] - df['delta_ma_14']) / (df['delta_std'] + 1e-10)
        
        # Candle color
        df['is_bullish'] = df['close'] >= df['open']
        df['is_bearish'] = df['close'] < df['open']
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < 30:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        try:
            delta = float(df['delta_volume'].iloc[-1])
            delta_ma = float(df['delta_ma_14'].iloc[-1])
            delta_zscore = float(df['delta_zscore'].iloc[-1])
            volume_ratio = float(df['volume_ratio'].iloc[-1])
            is_bullish = bool(df['is_bullish'].iloc[-1])
            is_bearish = bool(df['is_bearish'].iloc[-1])
        except (KeyError, IndexError, TypeError):
            return None, 0.0
        
        # Valores default para NaN
        if pd.isna(delta_zscore):
            delta_zscore = 0.0
        if pd.isna(delta_ma):
            delta_ma = 0.0
        if pd.isna(volume_ratio):
            volume_ratio = 1.0
        
        # === LONG: Pressão compradora forte + volume alto + candle bullish ===
        if (delta > delta_ma and 
            delta_zscore > 1.5 and  # Z-score > 1.5 = significante
            volume_ratio > 1.0 and
            is_bullish):
            
            # Força baseada em intensidade da pressão e volume
            strength = min(
                0.5 + (delta_zscore / 5.0) + ((volume_ratio - 1) * 0.2),
                1.0
            )
            return 'BUY', max(strength, 0.4)
        
        # === SHORT: Pressão vendedora forte + volume alto + candle bearish ===
        elif (delta < delta_ma and 
              delta_zscore < -1.5 and
              volume_ratio > 1.0 and
              is_bearish):
            
            strength = min(
                0.5 + (abs(delta_zscore) / 5.0) + ((volume_ratio - 1) * 0.2),
                1.0
            )
            return 'SELL', max(strength, 0.4)
        
        return None, 0.0
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """SL: 1.8 ATR"""
        df = self.calculate_signals(df)
        
        atr = df['atr'].iloc[-1]
        if pd.isna(atr) or atr == 0:
            atr = 100
        
        atr = Decimal(str(atr))
        stop_distance = atr * Decimal(str(self.atr_multiplier))
        
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
        """TP: R:R 1:1.5"""
        df = self.calculate_signals(df)
        
        atr = df['atr'].iloc[-1]
        if pd.isna(atr) or atr == 0:
            atr = 100
        
        atr = Decimal(str(atr))
        tp_distance = atr * Decimal('2.7')
        
        if side == 'BUY':
            return entry_price + tp_distance
        else:
            return entry_price - tp_distance