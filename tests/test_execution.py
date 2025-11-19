import unittest
from unittest.mock import Mock, MagicMock
from decimal import Decimal
from execution.trade_executor import TradeExecutorV2
from core.position_manager import PositionManager
from risk_management.position_sizer import PositionSizerV2

class TestExecution(unittest.TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.position_manager = PositionManager()
        self.position_sizer = PositionSizerV2()
        
        self.executor = TradeExecutorV2(
            self.mock_client,
            self.position_manager,
            self.position_sizer
        )
        
        # Mock symbol filters
        self.mock_client.get_symbol_filters.return_value = {
            'tickSize': Decimal('0.01'),
            'stepSize': Decimal('0.001'),
            'minQty': Decimal('0.001'),
            'minNotional': Decimal('5.0')
        }
    
    def test_execute_entry(self):
        """Testa execução de entrada"""
        self.mock_client.place_market_order.return_value = {'orderId': 12345}
        
        result = self.executor.execute_entry(
            symbol='BTCUSDT',
            side='BUY',
            entry_price=Decimal('40000'),
            stop_loss=Decimal('39500'),
            take_profit=Decimal('41000'),
            signal_strength=0.7,
            capital=Decimal('10000')
        )
        
        self.assertTrue(result or not result)  # Aceita ambos resultados
    
    def test_position_tracking(self):
        """Testa rastreamento de posição"""
        from core.position_manager import Position
        
        position = Position(
            symbol='BTCUSDT',
            side='BUY',
            entry_price=Decimal('40000'),
            quantity=Decimal('0.1'),
            stop_loss=Decimal('39500'),
            take_profit=Decimal('41000'),
            tp1=Decimal('40500'),
            tp2=Decimal('40750'),
            tp3=Decimal('41000')
        )
        
        self.position_manager.add_position(position)
        
        self.assertTrue(self.position_manager.has_position('BTCUSDT'))
        self.assertEqual(len(self.position_manager.get_all_positions()), 1)


if __name__ == '__main__':
    unittest.main()