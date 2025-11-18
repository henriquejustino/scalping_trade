import pandas as pd
import numpy as np
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class VWAPStrategy(BaseStrategy):
    def __init__(self, atr_multiplier=1.8):
        super().__init__("VWAP_Strategy")
        self.atr_multiplier = atr_multiplier
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        
        # VWAP cumsum
        cumulative_tp_volume = (df['typical_price'] * df['volume']).cumsum()
        cumulative_volume = df['volume'].cumsum()
        
        # Evita divisão por zero
        df['vwap'] = cumulative_tp_volume / (cumulative_volume + 1e-10)
        
        # VWAP Bands com desvio padrão
        df['typical_price_deviation'] = (df['typical_price'] - df['vwap']).rolling(window=20).std()
        df['vwap_std'] = df['typical_price_deviation'].fillna(0)
        
        df['vwap_upper'] = df['vwap'] + (df['vwap_std'] * 2)
        df['vwap_lower'] = df['vwap'] - (df['vwap_std'] * 2)
        
        # ATR para scaling (usando pandas rolling)
        df['tr'] = pd.DataFrame({
            'hl': df['high'] - df['low'],
            'hc': abs(df['high'] - df['close'].shift(1)),
            'lc': abs(df['low'] - df['close'].shift(1))
        }).max(axis=1)
        
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        # Posição relativa ao VWAP
        df['distance_from_vwap'] = (df['close'] - df['vwap']) / (df['vwap'] + 1e-10) * 100
        df['price_above_vwap'] = df['close'] > df['vwap']
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < 50:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        current_close = df['close'].iloc[-1]
        vwap = df['vwap'].iloc[-1]
        vwap_lower = df['vwap_lower'].iloc[-1]
        vwap_upper = df['vwap_upper'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        distance_pct = abs(df['distance_from_vwap'].iloc[-1])
        
        # Volume confirma
        volume_ma = df['volume'].rolling(20).mean().iloc[-1]
        high_volume = df['volume'].iloc[-1] > volume_ma * 1.2
        
        # === LONG: Preço toca banda inferior + volume + reversão ===
        if current_close <= vwap_lower and current_close >= prev_close and high_volume:
            # Força baseada na distância
            strength = max(0.4, min(distance_pct / 3.0, 0.9))
            return 'BUY', strength
        
        # === SHORT: Preço toca banda superior + volume + reversão ===
        elif current_close >= vwap_upper and current_close <= prev_close and high_volume:
            strength = max(0.4, min(distance_pct / 3.0, 0.9))
            return 'SELL', strength
        
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
        
        # SL é 1.8xATR, TP é 2.7xATR para manter 1:1.5
        tp_distance = atr * Decimal('2.7')
        
        if side == 'BUY':
            return entry_price + tp_distance
        else:
            return entry_price - tp_distance