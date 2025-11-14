from decimal import Decimal
from typing import Dict, List
from datetime import datetime, timedelta
from loguru import logger
import json

class PerformanceMonitor:
    def __init__(self):
        self.session_start = datetime.now()
        self.trades_history: List[Dict] = []
        self.equity_history: List[Dict] = []
        self.daily_pnl: Dict[str, Decimal] = {}
    
    def log_trade(self, trade: Dict):
        """Registra trade executado"""
        trade['timestamp'] = datetime.now()
        self.trades_history.append(trade)
        
        # Atualiza PnL diário
        date_key = trade['timestamp'].strftime('%Y-%m-%d')
        if date_key not in self.daily_pnl:
            self.daily_pnl[date_key] = Decimal('0')
        
        self.daily_pnl[date_key] += Decimal(str(trade.get('pnl', 0)))
    
    def log_equity(self, equity: Decimal):
        """Registra valor do capital"""
        self.equity_history.append({
            'timestamp': datetime.now(),
            'equity': float(equity)
        })
    
    def get_session_stats(self) -> Dict:
        """Retorna estatísticas da sessão"""
        if not self.trades_history:
            return {'message': 'Nenhum trade na sessão'}
        
        total_trades = len(self.trades_history)
        winning_trades = sum(1 for t in self.trades_history if t.get('pnl', 0) > 0)
        
        total_pnl = sum(Decimal(str(t.get('pnl', 0))) for t in self.trades_history)
        
        return {
            'session_duration': str(datetime.now() - self.session_start),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'total_pnl': float(total_pnl),
            'trades': self.trades_history[-10:]  # Últimos 10 trades
        }
    
    def get_daily_report(self) -> Dict:
        """Relatório diário"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        return {
            'date': today,
            'pnl': float(self.daily_pnl.get(today, Decimal('0'))),
            'trades_today': sum(
                1 for t in self.trades_history 
                if t['timestamp'].strftime('%Y-%m-%d') == today
            )
        }
    
    def save_session(self, filename: str = None):
        """Salva dados da sessão"""
        if filename is None:
            filename = f"data/logs/session_{self.session_start.strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {
            'session_start': self.session_start.isoformat(),
            'session_end': datetime.now().isoformat(),
            'stats': self.get_session_stats(),
            'daily_pnl': {k: float(v) for k, v in self.daily_pnl.items()},
            'trades': self.trades_history
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Sessão salva em: {filename}")