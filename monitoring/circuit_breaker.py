from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger

class CircuitBreaker:
    """Proteção contra operações ruins com stops automáticos"""
    
    def __init__(
        self,
        max_consecutive_losses: int = 5,
        max_hourly_drawdown: Decimal = Decimal('0.05'),
        max_daily_drawdown: Decimal = Decimal('0.15')
    ):
        self.max_consecutive_losses = max_consecutive_losses
        self.max_hourly_drawdown = max_hourly_drawdown
        self.max_daily_drawdown = max_daily_drawdown
        
        self.consecutive_losses = 0
        self.last_loss_time = None
        self.hourly_loss = Decimal('0')
        self.daily_loss = Decimal('0')
        self.peak_equity = Decimal('0')
        self.session_start = datetime.now()
    
    def check_circuit(self, pnl: Decimal, current_equity: Decimal) -> Tuple[bool, str]:
        """Verifica se deve disparar o circuit breaker"""
        
        # Update peak equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        # 1. Verificar perdas consecutivas
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self.max_consecutive_losses:
                return False, f"⛔ {self.consecutive_losses} perdas consecutivas!"
        else:
            self.consecutive_losses = 0
        
        # 2. Verificar drawdown horário
        self.hourly_loss += pnl if pnl < 0 else Decimal('0')
        if abs(self.hourly_loss) > self.peak_equity * self.max_hourly_drawdown:
            return False, f"⛔ Drawdown horário limite atingido!"
        
        # 3. Reset horário
        if datetime.now() - self.last_loss_time > timedelta(hours=1) if self.last_loss_time else True:
            self.hourly_loss = Decimal('0')
            self.last_loss_time = datetime.now()
        
        return True, "OK"