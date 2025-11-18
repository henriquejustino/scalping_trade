import pandas as pd
import ta
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class EMACrossover(BaseStrategy):
    def __init__(self, fast_period=9, slow_period=21, atr_multiplier=1.8):
        super().__init__("EMA_Crossover")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.atr_multiplier = atr_multiplier
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
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
        
        # ATR para scaling
        df['atr'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=14
        ).average_true_range().fillna(100)
        
        # Crossovers com confirmação de preço
        df['ema_cross_up'] = (df['ema_fast'] > df['ema_slow']) & \
                             (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
        
        df['ema_cross_down'] = (df['ema_fast'] < df['ema_slow']) & \
                               (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))
        
        # Confirmação: preço acima/abaixo da EMA rápida
        df['price_above_fast_ema'] = df['close'] > df['ema_fast']
        df['price_below_fast_ema'] = df['close'] < df['ema_fast']
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < self.slow_period + 10:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        # LONG: Crossover up + preço acima EMA rápida
        if df['ema_cross_up'].iloc[-1] and df['price_above_fast_ema'].iloc[-1]:
            ema_diff_pct = abs(df['ema_diff_pct'].iloc[-1])
            
            # Força baseada na distância entre EMAs
            strength = min(0.5 + (ema_diff_pct / 2.0), 1.0)
            
            # Bônus se crossover foi recente (consolidação)
            if df['ema_cross_up'].iloc[-2]:
                strength = min(strength + 0.15, 1.0)
            
            return 'BUY', strength
        
        # SHORT: Crossover down + preço abaixo EMA rápida
        elif df['ema_cross_down'].iloc[-1] and df['price_below_fast_ema'].iloc[-1]:
            ema_diff_pct = abs(df['ema_diff_pct'].iloc[-1])
            strength = min(0.5 + (ema_diff_pct / 2.0), 1.0)
            
            if df['ema_cross_down'].iloc[-2]:
                strength = min(strength + 0.15, 1.0)
            
            return 'SELL', strength
        
        return None, 0.0
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """SL: 1.8 ATR ou EMA lenta (o que for mais distante)"""
        df = self.calculate_signals(df)
        
        atr = Decimal(str(df['atr'].iloc[-1]))
        ema_slow = Decimal(str(df['ema_slow'].iloc[-1]))
        
        atr_stop = atr * Decimal(str(self.atr_multiplier))
        
        if side == 'BUY':
            sl_atr = entry_price - atr_stop
            sl_ema = ema_slow * Decimal('0.995')  # 0.5% abaixo da EMA
            return max(sl_atr, sl_ema)
        else:
            sl_atr = entry_price + atr_stop
            sl_ema = ema_slow * Decimal('1.005')
            return min(sl_atr, sl_ema)
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """TP: R:R 1:1.5 (risco 2xATR, target 3xATR)"""
        df = self.calculate_signals(df)
        
        atr = Decimal(str(df['atr'].iloc[-1]))
        
        # SL é 2xATR, então TP deve ser 3xATR para R:R 1:1.5
        tp_distance = atr * Decimal('3.0')
        
        if side == 'BUY':
            return entry_price + tp_distance
        else:
            return entry_price - tp_distance