
import pandas as pd
import ta
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class RSIStrategy(BaseStrategy):
    def __init__(self, period=14, oversold=30, overbought=70):
        super().__init__("RSI_Strategy")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df['rsi'] = ta.momentum.RSIIndicator(
            df['close'],
            window=self.period
        ).rsi()
        
        # RSI divergence
        df['price_higher_high'] = (df['high'] > df['high'].shift(1)) & \
                                   (df['high'].shift(1) > df['high'].shift(2))
        df['rsi_lower_high'] = (df['rsi'] < df['rsi'].shift(1)) & \
                               (df['rsi'].shift(1) < df['rsi'].shift(2))
        
        df['bearish_divergence'] = df['price_higher_high'] & df['rsi_lower_high']
        
        df['price_lower_low'] = (df['low'] < df['low'].shift(1)) & \
                                (df['low'].shift(1) < df['low'].shift(2))
        df['rsi_higher_low'] = (df['rsi'] > df['rsi'].shift(1)) & \
                               (df['rsi'].shift(1) > df['rsi'].shift(2))
        
        df['bullish_divergence'] = df['price_lower_low'] & df['rsi_higher_low']
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < self.period + 5:
            return None, 0.0
        
        df = self.calculate_signals(df)
        current_rsi = df['rsi'].iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        
        # LONG signal
        if current_rsi < self.oversold and prev_rsi < current_rsi:
            strength = 1.0 - (current_rsi / self.oversold)
            if df['bullish_divergence'].iloc[-1]:
                strength = min(strength + 0.2, 1.0)
            return 'BUY', strength
        
        # SHORT signal
        elif current_rsi > self.overbought and prev_rsi > current_rsi:
            strength = (current_rsi - self.overbought) / (100 - self.overbought)
            if df['bearish_divergence'].iloc[-1]:
                strength = min(strength + 0.2, 1.0)
            return 'SELL', strength
        
        return None, 0.0
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        atr = ta.volatility.AverageTrueRange(
            df['high'],
            df['low'],
            df['close'],
            window=14
        ).average_true_range().iloc[-1]
        
        atr_multiplier = Decimal('1.5')
        
        if side == 'BUY':
            return entry_price - (Decimal(str(atr)) * atr_multiplier)
        else:
            return entry_price + (Decimal(str(atr)) * atr_multiplier)
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        atr = ta.volatility.AverageTrueRange(
            df['high'],
            df['low'],
            df['close'],
            window=14
        ).average_true_range().iloc[-1]
        
        atr_multiplier = Decimal('3.0')
        
        if side == 'BUY':
            return entry_price + (Decimal(str(atr)) * atr_multiplier)
        else:
            return entry_price - (Decimal(str(atr)) * atr_multiplier)