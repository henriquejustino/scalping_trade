import unittest
import pandas as pd
import numpy as np
from decimal import Decimal
from strategies.indicators.rsi_strategy import RSIStrategy
from strategies.indicators.ema_crossover import EMACrossover

class TestStrategies(unittest.TestCase):
    def setUp(self):
        """Cria dados de teste"""
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100, freq='5min')
        
        self.df = pd.DataFrame({
            'open': np.random.uniform(40000, 41000, 100),
            'high': np.random.uniform(40000, 41000, 100),
            'low': np.random.uniform(40000, 41000, 100),
            'close': np.random.uniform(40000, 41000, 100),
            'volume': np.random.uniform(100, 1000, 100)
        }, index=dates)
        
        self.df['high'] = self.df[['open', 'close']].max(axis=1) + 100
        self.df['low'] = self.df[['open', 'close']].min(axis=1) - 100
    
    def test_rsi_strategy(self):
        """Testa RSI Strategy"""
        strategy = RSIStrategy()
        
        side, strength = strategy.get_entry_signal(self.df)
        
        self.assertIn(side, ['BUY', 'SELL', None])
        self.assertGreaterEqual(strength, 0.0)
        self.assertLessEqual(strength, 1.0)
    
    def test_ema_crossover(self):
        """Testa EMA Crossover"""
        strategy = EMACrossover()
        
        side, strength = strategy.get_entry_signal(self.df)
        
        self.assertIn(side, ['BUY', 'SELL', None])
        self.assertGreaterEqual(strength, 0.0)
        self.assertLessEqual(strength, 1.0)
    
    def test_stop_loss_calculation(self):
        """Testa cálculo de stop loss"""
        strategy = RSIStrategy()
        entry_price = Decimal('40500')
        
        sl_buy = strategy.calculate_stop_loss(self.df, entry_price, 'BUY')
        sl_sell = strategy.calculate_stop_loss(self.df, entry_price, 'SELL')
        
        self.assertLess(sl_buy, entry_price)
        self.assertGreater(sl_sell, entry_price)


if __name__ == '__main__':
    unittest.main()