import pandas as pd
import ta
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class BollingerBandsStrategy(BaseStrategy):
    def __init__(self, period=20, std_dev=2):
        super().__init__("Bollinger_Bands")
        self.period = period
        self.std_dev = std_dev
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        bb = ta.volatility.BollingerBands(
            df['close'],
            window=self.period,
            window_dev=self.std_dev
        )
        
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_width'] = bb.bollinger_wband()
        
        df['bb_percent'] = (df['close'] - df['bb_lower']) / \
                           (df['bb_upper'] - df['bb_lower'])
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < self.period + 5:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        current_close = df['close'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        bb_upper = df['bb_upper'].iloc[-1]
        bb_percent = df['bb_percent'].iloc[-1]
        bb_width = df['bb_width'].iloc[-1]
        
        # Volatilidade alta = melhores sinais
        volatility_factor = min(bb_width / 0.04, 1.0)
        
        # LONG: preço toca banda inferior
        if current_close <= bb_lower * 1.002:
            strength = (1.0 - bb_percent) * volatility_factor
            return 'BUY', min(strength, 1.0)
        
        # SHORT: preço toca banda superior
        elif current_close >= bb_upper * 0.998:
            strength = bb_percent * volatility_factor
            return 'SELL', min(strength, 1.0)
        
        return None, 0.0
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        df = self.calculate_signals(df)
        
        if side == 'BUY':
            bb_lower = Decimal(str(df['bb_lower'].iloc[-1]))
            distance = entry_price - bb_lower
            return entry_price - (distance * Decimal('1.5'))
        else:
            bb_upper = Decimal(str(df['bb_upper'].iloc[-1]))
            distance = bb_upper - entry_price
            return entry_price + (distance * Decimal('1.5'))
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        df = self.calculate_signals(df)
        bb_middle = Decimal(str(df['bb_middle'].iloc[-1]))
        
        if side == 'BUY':
            distance = bb_middle - entry_price
            return entry_price + (distance * Decimal('2.0'))
        else:
            distance = entry_price - bb_middle
            return entry_price - (distance * Decimal('2.0'))