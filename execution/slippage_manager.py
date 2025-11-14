from decimal import Decimal
from typing import Dict
from loguru import logger

class SlippageManager:
    """Gerencia e monitora slippage nas execuções"""
    
    def __init__(self, max_slippage_pct: Decimal = Decimal('0.5')):
        self.max_slippage_pct = max_slippage_pct
        self.slippage_history = []
    
    def calculate_slippage(
        self,
        expected_price: Decimal,
        executed_price: Decimal,
        side: str
    ) -> Decimal:
        """Calcula slippage percentual"""
        if side == 'BUY':
            slippage = ((executed_price - expected_price) / expected_price) * Decimal('100')
        else:
            slippage = ((expected_price - executed_price) / expected_price) * Decimal('100')
        
        return slippage
    
    def is_acceptable_slippage(
        self,
        expected_price: Decimal,
        executed_price: Decimal,
        side: str
    ) -> bool:
        """Verifica se slippage está aceitável"""
        slippage = self.calculate_slippage(expected_price, executed_price, side)
        
        self.slippage_history.append({
            'expected': float(expected_price),
            'executed': float(executed_price),
            'slippage_pct': float(slippage),
            'side': side
        })
        
        if abs(slippage) > self.max_slippage_pct:
            logger.warning(
                f"Slippage alto: {slippage:.3f}% "
                f"(máximo: {self.max_slippage_pct}%)"
            )
            return False
        
        return True
    
    def get_average_slippage(self) -> Dict:
        """Retorna slippage médio"""
        if not self.slippage_history:
            return {'avg_slippage': 0, 'count': 0}
        
        total = sum(abs(s['slippage_pct']) for s in self.slippage_history)
        avg = total / len(self.slippage_history)
        
        return {
            'avg_slippage': avg,
            'count': len(self.slippage_history),
            'max_slippage': max(abs(s['slippage_pct']) for s in self.slippage_history)
        }