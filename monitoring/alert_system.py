"""
Sistema de Alertas V2 e Performance Monitor - Monitoramento Completo
"""
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
import json

# ============================================================================
# FILE: monitoring/alert_system_v2.py
# ============================================================================

class AlertSystemV2:
    """Sistema de alertas robusto com múltiplos canais"""
    
    def __init__(
        self,
        max_consecutive_losses: int = 5,
        max_daily_loss_pct: Decimal = Decimal('5'),
        min_win_rate: float = 0.40
    ):
        self.max_consecutive_losses = max_consecutive_losses
        self.max_daily_loss_pct = max_daily_loss_pct
        self.min_win_rate = min_win_rate
        
        self.alerts = []
        self.consecutive_losses = 0
        self.daily_loss = Decimal('0')
        self.peak_equity = Decimal('0')
        self.session_start = datetime.now()
    
    def alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "WARNING",
        channels: List[str] = None
    ):
        """
        ✅ NOVO: Dispara alerta em múltiplos canais
        channels: ['log', 'email', 'telegram', 'discord']
        """
        
        alert_obj = {
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'message': message,
            'severity': severity
        }
        
        self.alerts.append(alert_obj)
        
        # Log
        if severity == "CRITICAL":
            logger.critical(f"🚨 {alert_type}: {message}")
        elif severity == "ERROR":
            logger.error(f"❌ {alert_type}: {message}")
        else:
            logger.warning(f"⚠️ {alert_type}: {message}")
        
        # Canais (TODO: implementar integração)
        if channels is None:
            channels = ['log']
        
        for channel in channels:
            self._send_via_channel(channel, alert_obj)
    
    def _send_via_channel(self, channel: str, alert: Dict):
        """Envia alerta via canal específico"""
        
        if channel == 'email':
            logger.info(f"📧 Email seria enviado: {alert['message']}")
        elif channel == 'telegram':
            logger.info(f"📱 Telegram seria enviado: {alert['message']}")
        elif channel == 'discord':
            logger.info(f"💬 Discord seria enviado: {alert['message']}")
    
    def check_drawdown(self, current_equity: Decimal, initial_equity: Decimal) -> bool:
        """Verifica drawdown máximo"""
        
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        drawdown = ((self.peak_equity - current_equity) / self.peak_equity) * Decimal('100') \
                  if self.peak_equity > 0 else Decimal('0')
        
        if drawdown >= Decimal('10'):
            self.alert(
                'DRAWDOWN_ALERT',
                f"Drawdown de {float(drawdown):.2f}% atingido!",
                "WARNING"
            )
            return True
        
        return False
    
    def check_daily_loss(self, daily_pnl: Decimal, initial_equity: Decimal) -> bool:
        """Verifica perda diária máxima"""
        
        loss_pct = (abs(daily_pnl) / initial_equity) * Decimal('100')
        
        if daily_pnl < 0 and loss_pct >= self.max_daily_loss_pct:
            self.alert(
                'DAILY_LOSS_ALERT',
                f"Perda diária de {float(loss_pct):.2f}% atingida!",
                "ERROR"
            )
            return True
        
        return False
    
    def check_win_rate(self, winning_trades: int, total_trades: int) -> bool:
        """Verifica win rate mínimo"""
        
        if total_trades < 20:  # Mínimo de trades
            return False
        
        win_rate = winning_trades / total_trades
        
        if win_rate < self.min_win_rate:
            self.alert(
                'WIN_RATE_ALERT',
                f"Win rate de {win_rate*100:.2f}% abaixo do mínimo ({self.min_win_rate*100}%)",
                "WARNING"
            )
            return True
        
        return False
    
    def check_consecutive_losses(self, recent_trades: List[Dict], max_consecutive: int = 5) -> bool:
        """Verifica sequência de perdas"""
        
        if len(recent_trades) < max_consecutive:
            return False
        
        consecutive_losses = 0
        for trade in reversed(recent_trades):
            if trade.get('pnl', 0) < 0:
                consecutive_losses += 1
                if consecutive_losses >= max_consecutive:
                    self.alert(
                        'CONSECUTIVE_LOSSES_ALERT',
                        f"{consecutive_losses} perdas consecutivas detectadas!",
                        "ERROR"
                    )
                    return True
            else:
                break
        
        return False
    
    def should_stop_trading(self) -> bool:
        """Verifica se deve parar de operar"""
        
        critical_alerts = ['DRAWDOWN_ALERT', 'DAILY_LOSS_ALERT', 'CONSECUTIVE_LOSSES_ALERT']
        recent_critical = [
            a for a in self.alerts[-10:]
            if a['type'] in critical_alerts
        ]
        
        if len(recent_critical) >= 2:
            self.alert(
                'CIRCUIT_BREAKER',
                'MÚLTIPLOS ALERTAS CRÍTICOS - PARANDO OPERAÇÕES',
                'CRITICAL'
            )
            return True
        
        return False
    
    def get_alerts_summary(self) -> Dict:
        """Retorna resumo dos alertas"""
        return {
            'total_alerts': len(self.alerts),
            'recent_alerts': self.alerts[-20:],
            'should_stop': self.should_stop_trading()
        }