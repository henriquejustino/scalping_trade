from decimal import Decimal
from typing import Optional
from loguru import logger
from datetime import datetime

class AlertSystem:
    def __init__(
        self,
        max_drawdown_pct: Decimal = Decimal('10'),
        max_daily_loss_pct: Decimal = Decimal('5'),
        min_win_rate: float = 0.40
    ):
        self.max_drawdown_pct = max_drawdown_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.min_win_rate = min_win_rate
        
        self.alerts_triggered: list = []
        self.daily_loss = Decimal('0')
        self.peak_equity = Decimal('0')
    
    def check_drawdown(self, current_equity: Decimal, initial_equity: Decimal) -> bool:
        """Verifica drawdown máximo"""
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        drawdown = ((self.peak_equity - current_equity) / self.peak_equity) * Decimal('100')
        
        if drawdown >= self.max_drawdown_pct:
            self._trigger_alert(
                'DRAWDOWN_ALERT',
                f"Drawdown de {drawdown:.2f}% atingido! (máximo: {self.max_drawdown_pct}%)"
            )
            return True
        
        return False
    
    def check_daily_loss(self, daily_pnl: Decimal, initial_equity: Decimal) -> bool:
        """Verifica perda diária máxima"""
        loss_pct = (abs(daily_pnl) / initial_equity) * Decimal('100')
        
        if daily_pnl < 0 and loss_pct >= self.max_daily_loss_pct:
            self._trigger_alert(
                'DAILY_LOSS_ALERT',
                f"Perda diária de {loss_pct:.2f}% atingida! (máximo: {self.max_daily_loss_pct}%)"
            )
            return True
        
        return False
    
    def check_win_rate(self, winning_trades: int, total_trades: int) -> bool:
        """Verifica win rate mínimo"""
        if total_trades < 20:  # Mínimo de trades para análise
            return False
        
        win_rate = winning_trades / total_trades
        
        if win_rate < self.min_win_rate:
            self._trigger_alert(
                'WIN_RATE_ALERT',
                f"Win rate de {win_rate*100:.2f}% abaixo do mínimo ({self.min_win_rate*100}%)"
            )
            return True
        
        return False
    
    def check_consecutive_losses(self, recent_trades: list, max_consecutive: int = 5) -> bool:
        """Verifica sequência de perdas"""
        if len(recent_trades) < max_consecutive:
            return False
        
        consecutive_losses = 0
        for trade in reversed(recent_trades):
            if trade.get('pnl', 0) < 0:
                consecutive_losses += 1
                if consecutive_losses >= max_consecutive:
                    self._trigger_alert(
                        'CONSECUTIVE_LOSSES_ALERT',
                        f"{consecutive_losses} perdas consecutivas detectadas!"
                    )
                    return True
            else:
                break
        
        return False
    
    def _trigger_alert(self, alert_type: str, message: str):
        """Dispara alerta"""
        alert = {
            'type': alert_type,
            'message': message,
            'timestamp': datetime.now()
        }
        
        self.alerts_triggered.append(alert)
        
        logger.warning(f"🚨 ALERTA: {message}")
        
        # Aqui você pode adicionar integração com:
        # - Telegram
        # - Discord
        # - Email
        # - SMS
    
    def should_stop_trading(self) -> bool:
        """Verifica se deve parar de operar"""
        critical_alerts = ['DRAWDOWN_ALERT', 'DAILY_LOSS_ALERT', 'CONSECUTIVE_LOSSES_ALERT']
        
        recent_critical = [
            a for a in self.alerts_triggered[-5:]
            if a['type'] in critical_alerts
        ]
        
        if len(recent_critical) >= 2:
            logger.error("⛔ MÚLTIPLOS ALERTAS CRÍTICOS - PARANDO OPERAÇÕES")
            return True
        
        return False
    
    def get_alerts_summary(self) -> dict:
        """Retorna resumo dos alertas"""
        return {
            'total_alerts': len(self.alerts_triggered),
            'recent_alerts': self.alerts_triggered[-10:],
            'should_stop': self.should_stop_trading()
        }