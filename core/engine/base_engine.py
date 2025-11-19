"""
Base Engine - Interface abstrata para Backtest e Live Trading
Garante consistência entre ambos os modos
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
import pandas as pd
from dataclasses import dataclass, field

@dataclass
class TradeLog:
    """Log estruturado de trade"""
    symbol: str
    side: str
    entry_time: datetime
    entry_price: Decimal
    entry_quantity: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    exit_time: Optional[datetime] = None
    exit_price: Optional[Decimal] = None
    exit_quantity: Optional[Decimal] = None
    exit_reason: Optional[str] = None
    pnl: Decimal = Decimal('0')
    pnl_pct: Decimal = Decimal('0')
    signal_strength: float = 0.0
    regime: str = "UNKNOWN"
    duration_seconds: int = 0
    winning: bool = False
    
    def to_dict(self):
        """Converte para dict para JSON/CSV"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_time': self.entry_time.isoformat(),
            'entry_price': float(self.entry_price),
            'entry_quantity': float(self.entry_quantity),
            'stop_loss': float(self.stop_loss),
            'take_profit': float(self.take_profit),
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'exit_price': float(self.exit_price) if self.exit_price else None,
            'exit_quantity': float(self.exit_quantity) if self.exit_quantity else None,
            'exit_reason': self.exit_reason,
            'pnl': float(self.pnl),
            'pnl_pct': float(self.pnl_pct),
            'signal_strength': self.signal_strength,
            'regime': self.regime,
            'duration_seconds': self.duration_seconds,
            'winning': self.winning
        }

@dataclass
class Position:
    """Posição aberta"""
    symbol: str
    side: str
    entry_price: Decimal
    entry_quantity: Decimal
    current_quantity: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    tp1: Decimal
    tp1_hit: bool = False
    tp2: Decimal = None
    tp2_hit: bool = False
    tp3: Decimal = None
    tp3_hit: bool = False
    entry_time: datetime = None
    signal_strength: float = 0.0
    regime: str = "UNKNOWN"
    trailing_stop: Optional[Decimal] = None
    max_profit: Decimal = Decimal('0')
    
    def calculate_pnl(self, current_price: Decimal) -> Decimal:
        """Calcula PnL não-realizado"""
        if self.side == 'BUY':
            return (current_price - self.entry_price) * self.current_quantity
        else:
            return (self.entry_price - current_price) * self.current_quantity
    
    def calculate_pnl_pct(self, current_price: Decimal) -> Decimal:
        """Calcula PnL em percentual"""
        if self.side == 'BUY':
            return ((current_price - self.entry_price) / self.entry_price) * Decimal('100')
        else:
            return ((self.entry_price - current_price) / self.entry_price) * Decimal('100')

class BaseEngine(ABC):
    """Interface base para motores de trading"""
    
    def __init__(self):
        self.trades: List[TradeLog] = []
        self.current_position: Optional[Position] = None
        self.equity_history: List[Dict] = []
        self.errors: List[Dict] = []
    
    @abstractmethod
    def run(self):
        """Executa o engine"""
        pass
    
    @abstractmethod
    def run(self):
        """Executa o engine (implementação específica em subclasses)"""
        pass
    
    @abstractmethod
    def validate_trade(self, side: str, entry: Decimal, sl: Decimal, tp: Decimal) -> bool:
        """Valida parâmetros do trade antes de executar"""
        pass
    
    @abstractmethod
    def execute_entry(self, *args, **kwargs) -> bool:
        """Executa entrada na posição"""
        pass
    
    @abstractmethod
    def execute_exit(self, *args, **kwargs) -> bool:
        """Executa saída da posição"""
        pass
    
    def add_error(self, error_type: str, message: str, severity: str = "WARNING"):
        """Log estruturado de erros"""
        self.errors.append({
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': message,
            'severity': severity
        })
    
    def get_performance_metrics(self) -> Dict:
        """Calcula métricas de performance"""
        if not self.trades:
            return {}
        
        df = pd.DataFrame([t.to_dict() for t in self.trades])
        
        total_trades = len(df)
        winning_trades = len(df[df['winning']])
        losing_trades = len(df[~df['winning']])
        
        total_pnl = df['pnl'].sum()
        avg_win = df[df['winning']]['pnl'].mean() if winning_trades > 0 else Decimal('0')
        avg_loss = df[~df['winning']]['pnl'].mean() if losing_trades > 0 else Decimal('0')
        
        profit_factor = (avg_win * winning_trades) / abs(avg_loss * losing_trades) \
                       if losing_trades > 0 and avg_loss != 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'total_pnl': float(total_pnl),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'profit_factor': float(profit_factor),
            'largest_win': float(df['pnl'].max()),
            'largest_loss': float(df['pnl'].min()),
            'avg_trade_duration': float(df['duration_seconds'].mean())
        }