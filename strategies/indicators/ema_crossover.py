import pandas as pd
import ta
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class EMACrossover(BaseStrategy):
    def __init__(self, fast_period=9, slow_period=21):
        super().__init__("EMA_Crossover")
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df['ema_fast'] = ta.trend.EMAIndicator(
            df['close'],
            window=self.fast_period
        ).ema_indicator()
        
        df['ema_slow'] = ta.trend.EMAIndicator(
            df['close'],
            window=self.slow_period
        ).ema_indicator()
        
        df['ema_diff'] = df['ema_fast'] - df['ema_slow']
        df['ema_diff_pct'] = (df['ema_diff'] / df['ema_slow']) * 100
        
        df['crossover_up'] = (df['ema_fast'] > df['ema_slow']) & \
                             (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
        
        df['crossover_down'] = (df['ema_fast'] < df['ema_slow']) & \
                               (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < self.slow_period + 5:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        if df['crossover_up'].iloc[-1]:
            ema_diff_pct = abs(df['ema_diff_pct'].iloc[-1])
            strength = min(ema_diff_pct / 2.0, 1.0)
            
            # Confirma tendência
            if df['close'].iloc[-1] > df['ema_fast'].iloc[-1]:
                strength = min(strength + 0.15, 1.0)
            
            return 'BUY', strength
        
        elif df['crossover_down'].iloc[-1]:
            ema_diff_pct = abs(df['ema_diff_pct'].iloc[-1])
            strength = min(ema_diff_pct / 2.0, 1.0)
            
            if df['close'].iloc[-1] < df['ema_fast'].iloc[-1]:
                strength = min(strength + 0.15, 1.0)
            
            return 'SELL', strength
        
        return None, 0.0
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        df = self.calculate_signals(df)
        
        if side == 'BUY':
            ema_slow = Decimal(str(df['ema_slow'].iloc[-1]))
            atr = ta.volatility.AverageTrueRange(
                df['high'], df['low'], df['close'], window=14
            ).average_true_range().iloc[-1]
            return ema_slow - (Decimal(str(atr)) * Decimal('0.5'))
        else:
            ema_slow = Decimal(str(df['ema_slow'].iloc[-1]))
            atr = ta.volatility.AverageTrueRange(
                df['high'], df['low'], df['close'], window=14
            ).average_true_range().iloc[-1]
            return ema_slow + (Decimal(str(atr)) * Decimal('0.5'))
    
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
        
        if side == 'BUY':
            return entry_price + (Decimal(str(atr)) * Decimal('2.5'))
        else:
            return entry_price - (Decimal(str(atr)) * Decimal('2.5'))