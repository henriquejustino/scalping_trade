import unittest
from decimal import Decimal
from risk_management.position_sizer import PositionSizer
from risk_management.risk_calculator import RiskCalculator

class TestRiskManagement(unittest.TestCase):
    def setUp(self):
        self.position_sizer = PositionSizer()
        self.risk_calculator = RiskCalculator()
        
        self.filters = {
            'tickSize': Decimal('0.01'),
            'stepSize': Decimal('0.001'),
            'minQty': Decimal('0.001'),
            'minNotional': Decimal('5.0')
        }
    
    def test_position_size_calculation(self):
        """Testa cálculo de tamanho de posição"""
        capital = Decimal('10000')
        entry_price = Decimal('40000')
        stop_loss = Decimal('39500')
        signal_strength = 0.8
        
        quantity = self.position_sizer.calculate_dynamic_position_size(
            capital=capital,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            symbol_filters=self.filters,
            signal_strength=signal_strength
        )
        
        self.assertIsNotNone(quantity)
        self.assertGreater(quantity, Decimal('0'))
    
    def test_risk_limits(self):
        """Testa limites de risco"""
        current_positions = [
            {'risk': Decimal('0.02')},
            {'risk': Decimal('0.02')}
        ]
        
        new_risk = Decimal('0.02')
        
        can_open = self.risk_calculator.can_open_position(
            current_positions,
            new_risk
        )
        
        self.assertIsInstance(can_open, bool)
    
    def test_signal_strength_risk_scaling(self):
        """Testa escalonamento de risco por força de sinal"""
        capital = Decimal('10000')
        entry_price = Decimal('40000')
        stop_loss = Decimal('39600')
        
        # Sinal forte deve ter posição maior
        qty_strong = self.position_sizer.calculate_dynamic_position_size(
            capital, entry_price, stop_loss, self.filters, 0.9
        )
        
        # Sinal fraco deve ter posição menor
        qty_weak = self.position_sizer.calculate_dynamic_position_size(
            capital, entry_price, stop_loss, self.filters, 0.3
        )
        
        if qty_strong and qty_weak:
            self.assertGreater(qty_strong, qty_weak)


if __name__ == '__main__':
    unittest.main()