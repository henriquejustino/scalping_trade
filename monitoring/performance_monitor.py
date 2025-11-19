from decimal import Decimal
from typing import Dict, List
from datetime import datetime, timedelta
from loguru import logger
import json

class PerformanceMonitor:
    """Monitora performance em tempo real"""
    
    def __init__(self):
        self.session_start = datetime.now()
        self.trades_history: List[Dict] = []
        self.equity_history: List[Dict] = []
        self.daily_pnl: Dict[str, Decimal] = {}
        self.signals_logged: List[Dict] = []
    
    def log_trade(self, trade: Dict):
        """Registra trade executado"""
        
        trade['timestamp'] = datetime.now()
        self.trades_history.append(trade)
        
        # Update daily PnL
        date_key = trade['timestamp'].strftime('%Y-%m-%d')
        if date_key not in self.daily_pnl:
            self.daily_pnl[date_key] = Decimal('0')
        
        self.daily_pnl[date_key] += Decimal(str(trade.get('pnl', 0)))
    
    def log_equity(self, equity: Decimal, regime: str = "UNKNOWN"):
        """Registra valor do capital"""
        
        self.equity_history.append({
            'timestamp': datetime.now(),
            'equity': float(equity),
            'regime': regime
        })
    
    def log_signal(self, symbol: str, side: str, strength: float):
        """Registra sinal gerado"""
        
        self.signals_logged.append({
            'timestamp': datetime.now(),
            'symbol': symbol,
            'side': side,
            'strength': strength
        })
    
    def get_session_stats(self) -> Dict:
        """Retorna estatísticas da sessão"""
        
        if not self.trades_history:
            return {'message': 'Nenhum trade na sessão'}
        
        total_trades = len(self.trades_history)
        winning_trades = sum(1 for t in self.trades_history if t.get('pnl', 0) > 0)
        total_pnl = sum(Decimal(str(t.get('pnl', 0))) for t in self.trades_history)
        
        duration = datetime.now() - self.session_start
        
        return {
            'session_duration': str(duration),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'total_pnl': float(total_pnl),
            'avg_trade_duration': str(duration / total_trades) if total_trades > 0 else '0'
        }
    
    def get_daily_report(self) -> Dict:
        """Relatório diário"""
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        today_trades = [
            t for t in self.trades_history
            if t['timestamp'].strftime('%Y-%m-%d') == today
        ]
        
        return {
            'date': today,
            'trades_today': len(today_trades),
            'pnl_today': float(self.daily_pnl.get(today, Decimal('0'))),
            'signals_today': len([s for s in self.signals_logged 
                                  if s['timestamp'].strftime('%Y-%m-%d') == today])
        }
    
    def get_win_rate_by_symbol(self) -> Dict:
        """Win rate por símbolo"""
        
        by_symbol = {}
        
        for trade in self.trades_history:
            symbol = trade.get('symbol', 'UNKNOWN')
            if symbol not in by_symbol:
                by_symbol[symbol] = {'wins': 0, 'total': 0}
            
            by_symbol[symbol]['total'] += 1
            if trade.get('pnl', 0) > 0:
                by_symbol[symbol]['wins'] += 1
        
        result = {}
        for symbol, data in by_symbol.items():
            result[symbol] = {
                'win_rate': data['wins'] / data['total'] if data['total'] > 0 else 0,
                'trades': data['total']
            }
        
        return result
    
    def save_session(self, filename: str = None):
        """Salva dados da sessão"""
        
        if filename is None:
            timestamp = self.session_start.strftime('%Y%m%d_%H%M%S')
            filename = f"data/logs/session_{timestamp}.json"
        
        data = {
            'session_start': self.session_start.isoformat(),
            'session_end': datetime.now().isoformat(),
            'stats': self.get_session_stats(),
            'daily_pnl': {k: float(v) for k, v in self.daily_pnl.items()},
            'trades': self.trades_history,
            'equity_history': self.equity_history[:100]  # Últimos 100 registros
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"✅ Sessão salva em: {filename}")
        except Exception as e:
            logger.error(f"Erro ao salvar sessão: {e}")
    
    def get_performance_summary(self) -> str:
        """Retorna resumo de performance formatado"""
        
        stats = self.get_session_stats()
        daily = self.get_daily_report()
        wr_by_symbol = self.get_win_rate_by_symbol()
        
        summary = f"""
{'='*60}
📊 PERFORMANCE SUMMARY
{'='*60}
Sessão: {stats.get('session_duration', 'N/A')}
Trades: {stats.get('total_trades', 0)} (Ganhos: {stats.get('winning_trades', 0)})
Win Rate: {stats.get('win_rate', 0)*100:.2f}%
PnL Total: ${stats.get('total_pnl', 0):,.2f}

Hoje:
  Trades: {daily['trades_today']}
  PnL: ${daily['pnl_today']:,.2f}
  Sinais: {daily['signals_today']}

Por Símbolo:
"""
        for symbol, wr_data in wr_by_symbol.items():
            summary += f"  {symbol}: WR={wr_data['win_rate']*100:.1f}% ({wr_data['trades']} trades)\n"
        
        summary += f"{'='*60}\n"
        
        return summary