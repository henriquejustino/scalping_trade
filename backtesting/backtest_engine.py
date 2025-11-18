import pandas as pd
from decimal import Decimal
from typing import Dict, List
from datetime import datetime
from loguru import logger
from core.data_manager import DataManager
from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
from strategies.market_detector import MarketRegimeDetector
from risk_management.position_sizer import PositionSizer
from risk_management.risk_calculator import RiskCalculator
import warnings
import numpy as np

warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)

class BacktestEngine:
    def __init__(
        self,
        data_manager: DataManager,
        strategy: SmartScalpingEnsemble,
        initial_capital: Decimal = Decimal('10000'),
        slippage_pct: Decimal = Decimal('0.005')  # 0.5% slippage
    ):
        self.data_manager = data_manager
        self.strategy = strategy
        self.regime_detector = MarketRegimeDetector()
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.slippage_pct = slippage_pct  # 0.5% padrão
        
        self.position_sizer = PositionSizer()
        self.risk_calculator = RiskCalculator()
        
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []
        self.current_position = None
        self.signal_log: List[Dict] = []
    
    def run_backtest(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """Executa backtest com slippage e validação de regime"""
        
        logger.info(f"Iniciando backtest: {symbol} de {start_date} até {end_date}")
        
        # Carrega dados
        df_5m = self.data_manager.get_ohlcv_data(symbol, '5m', limit=1500)
        df_15m = self.data_manager.get_ohlcv_data(symbol, '15m', limit=1500)
        
        if df_5m.empty or df_15m.empty:
            return {'error': 'Não foi possível carregar dados históricos'}
        
        logger.info(f"Dados carregados: {len(df_5m)} candles (5m), {len(df_15m)} candles (15m)")
        
        if len(df_5m) < 100:
            return {'error': 'Dados insuficientes para backtest'}
        
        # Itera pelos candles
        for i in range(100, len(df_5m)):
            current_time = df_5m.index[i]
            current_price = Decimal(str(df_5m['close'].iloc[i]))
            
            hist_5m = df_5m.iloc[:i+1].copy()
            hist_15m = df_15m[df_15m.index <= current_time].copy()
            
            if len(hist_15m) < 50:
                continue
            
            # === DETECTA REGIME DE MERCADO ===
            regime = self.regime_detector.detect_regime(hist_5m, hist_15m)
            
            # === VALIDA SE REGIME É TRADEABLE ===
            if not self.regime_detector.is_tradeable_regime(regime):
                logger.debug(f"Regime {regime} não tradeable. Pulando.")
                if self.current_position:
                    self._monitor_position(current_price, current_time)
                continue
            
            # Monitora posição existente
            if self.current_position is not None:
                self._monitor_position(current_price, current_time)
            else:
                # Calcula volume ratio
                volume_ma = hist_5m['volume'].rolling(20).mean().iloc[-1]
                volume_ratio = hist_5m['volume'].iloc[-1] / volume_ma if volume_ma > 0 else 1.0
                
                self._check_entry_signal(
                    symbol,
                    hist_5m,
                    hist_15m,
                    current_time,
                    current_price,
                    volume_ratio,
                    regime
                )
            
            # Atualiza equity
            equity = self.capital
            if self.current_position:
                pnl = self._calculate_position_pnl(current_price)
                equity += pnl
            
            self.equity_curve.append({
                'timestamp': current_time,
                'equity': float(equity),
                'capital': float(self.capital),
                'regime': regime
            })
        
        # Fecha posição final
        if self.current_position:
            self._close_position(current_price, current_time, "Fim do backtest")
        
        return self._generate_results()
    
    def _check_entry_signal(
        self,
        symbol: str,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        timestamp: datetime,
        current_price: Decimal,
        volume_ratio: float,
        regime: str
    ):
        """Verifica sinal com validações"""
        
        side, strength, details = self.strategy.get_ensemble_signal(df_5m, df_15m)
        
        signal_entry = {
            'timestamp': timestamp,
            'side': side,
            'strength': float(strength),
            'price': float(current_price),
            'volume_ratio': float(volume_ratio),
            'regime': regime,
            'traded': False
        }
        self.signal_log.append(signal_entry)
        
        if side is None:
            return
        
        # SL e TP
        stop_loss = self.strategy.calculate_stop_loss(df_5m, current_price, side)
        take_profit = self.strategy.calculate_take_profit(df_5m, current_price, side)
        
        # Sanity check
        if side == 'BUY':
            if stop_loss >= current_price:
                logger.warning(f"SL inválido: {stop_loss} >= {current_price}")
                return
        else:
            if stop_loss <= current_price:
                logger.warning(f"SL inválido: {stop_loss} <= {current_price}")
                return
        
        # === SLIPPAGE NA ENTRADA ===
        if side == 'BUY':
            slipped_entry = current_price * (Decimal('1') + self.slippage_pct)
        else:
            slipped_entry = current_price * (Decimal('1') - self.slippage_pct)
        
        # Position sizer COM VOLUME VALIDATION
        filters = {
            'tickSize': Decimal('0.01'),
            'stepSize': Decimal('0.001'),
            'minQty': Decimal('0.001'),
            'minNotional': Decimal('5.0')
        }
        
        quantity = self.position_sizer.calculate_dynamic_position_size(
            capital=self.capital,
            entry_price=slipped_entry,  # Usa preço com slippage
            stop_loss_price=stop_loss,
            symbol_filters=filters,
            signal_strength=strength,
            volume_ratio=volume_ratio  # Passa volume ratio
        )
        
        if quantity is None:
            logger.debug(f"Posição rejeitada (volume/tamanho inválido)")
            return
        
        # Calcula TPs
        distance = abs(take_profit - slipped_entry)
        
        from config.settings import settings
        if side == 'BUY':
            tp1 = slipped_entry + (distance * settings.TP1_PERCENTAGE)
            tp2 = slipped_entry + (distance * settings.TP2_PERCENTAGE)
            tp3 = take_profit
        else:
            tp1 = slipped_entry - (distance * settings.TP1_PERCENTAGE)
            tp2 = slipped_entry - (distance * settings.TP2_PERCENTAGE)
            tp3 = take_profit
        
        self.current_position = {
            'symbol': symbol,
            'side': side,
            'entry_price': slipped_entry,
            'original_entry': current_price,
            'entry_time': timestamp,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'tp1_hit': False,
            'tp2_hit': False,
            'tp3_hit': False,
            'current_quantity': quantity,
            'signal_strength': strength,
            'regime': regime
        }
        
        signal_entry['traded'] = True
        
        logger.info(
            f"📈 ENTRADA: {side} {quantity:.6f} @ ${slipped_entry:.2f} (slippage: {self.slippage_pct*100:.2f}%) "
            f"| SL: ${stop_loss:.2f} | TP: ${take_profit:.2f} "
            f"| Regime: {regime} | Vol: {volume_ratio:.2f}x"
        )
    
    def _monitor_position(self, current_price: Decimal, timestamp: datetime):
        """Monitora posição aberta"""
        
        pos = self.current_position
        
        # Verifica stop loss
        if pos['side'] == 'BUY':
            if current_price <= pos['stop_loss']:
                self._close_position(current_price, timestamp, "Stop Loss")
                return
        else:
            if current_price >= pos['stop_loss']:
                self._close_position(current_price, timestamp, "Stop Loss")
                return
        
        # Verifica take profit levels
        from config.settings import settings
        
        if pos['side'] == 'BUY':
            if not pos['tp1_hit'] and current_price >= pos['tp1']:
                pos['tp1_hit'] = True
                exit_qty = pos['current_quantity'] * settings.TP1_EXIT_RATIO
                self._partial_exit(exit_qty, current_price, timestamp, "TP1")
                pos['stop_loss'] = pos['entry_price']
            
            elif not pos['tp2_hit'] and current_price >= pos['tp2']:
                pos['tp2_hit'] = True
                exit_qty = pos['current_quantity'] * settings.TP2_EXIT_RATIO
                self._partial_exit(exit_qty, current_price, timestamp, "TP2")
            
            elif not pos['tp3_hit'] and current_price >= pos['tp3']:
                self._close_position(current_price, timestamp, "TP3")
        
        else:  # SELL
            if not pos['tp1_hit'] and current_price <= pos['tp1']:
                pos['tp1_hit'] = True
                exit_qty = pos['current_quantity'] * settings.TP1_EXIT_RATIO
                self._partial_exit(exit_qty, current_price, timestamp, "TP1")
                pos['stop_loss'] = pos['entry_price']
            
            elif not pos['tp2_hit'] and current_price <= pos['tp2']:
                pos['tp2_hit'] = True
                exit_qty = pos['current_quantity'] * settings.TP2_EXIT_RATIO
                self._partial_exit(exit_qty, current_price, timestamp, "TP2")
            
            elif not pos['tp3_hit'] and current_price <= pos['tp3']:
                self._close_position(current_price, timestamp, "TP3")
    
    def _calculate_position_pnl(self, current_price: Decimal) -> Decimal:
        """Calcula PnL"""
        pos = self.current_position
        
        if pos['side'] == 'BUY':
            return (current_price - pos['entry_price']) * pos['current_quantity']
        else:
            return (pos['entry_price'] - current_price) * pos['current_quantity']
    
    def _partial_exit(
        self,
        exit_quantity: Decimal,
        exit_price: Decimal,
        timestamp: datetime,
        reason: str
    ):
        """Saída parcial com slippage"""
        pos = self.current_position
        
        # Slippage na saída
        if pos['side'] == 'BUY':
            slipped_exit = exit_price * (Decimal('1') - self.slippage_pct)
            pnl = (slipped_exit - pos['entry_price']) * exit_quantity
        else:
            slipped_exit = exit_price * (Decimal('1') + self.slippage_pct)
            pnl = (pos['entry_price'] - slipped_exit) * exit_quantity
        
        self.capital += pnl
        pos['current_quantity'] -= exit_quantity
        
        logger.info(f"💰 Saída parcial {reason}: {exit_quantity:.6f} @ ${exit_price:.2f} | PnL: ${pnl:.2f}")
    
    def _close_position(
        self,
        exit_price: Decimal,
        timestamp: datetime,
        reason: str
    ):
        """Fecha posição com slippage"""
        pos = self.current_position
        
        # Slippage na saída
        if pos['side'] == 'BUY':
            slipped_exit = exit_price * (Decimal('1') - self.slippage_pct)
            pnl = (slipped_exit - pos['entry_price']) * pos['current_quantity']
        else:
            slipped_exit = exit_price * (Decimal('1') + self.slippage_pct)
            pnl = (pos['entry_price'] - slipped_exit) * pos['current_quantity']
        
        self.capital += pnl
        
        pnl_pct = (pnl / (pos['entry_price'] * pos['quantity'])) * Decimal('100')
        
        trade = {
            'symbol': pos['symbol'],
            'side': pos['side'],
            'entry_time': pos['entry_time'],
            'exit_time': timestamp,
            'entry_price': float(pos['entry_price']),
            'exit_price': float(exit_price),
            'quantity': float(pos['quantity']),
            'pnl': float(pnl),
            'pnl_pct': float(pnl_pct),
            'reason': reason,
            'signal_strength': pos['signal_strength'],
            'regime': pos['regime']
        }
        
        self.trades.append(trade)
        
        color = "🟢" if pnl > 0 else "🔴"
        duration = (timestamp - pos['entry_time']).total_seconds() / 60
        logger.info(
            f"{color} Posição fechada ({reason}): "
            f"PnL: ${pnl:.2f} ({pnl_pct:.2f}%) | {duration:.0f}m"
        )
        
        self.current_position = None
    
    def _generate_results(self) -> Dict:
        """Gera resultados"""
        
        if not self.trades:
            return {'error': 'Nenhum trade executado'}
        
        df_trades = pd.DataFrame(self.trades)
        
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['pnl'] > 0])
        losing_trades = len(df_trades[df_trades['pnl'] < 0])
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        total_pnl = df_trades['pnl'].sum()
        avg_win = df_trades[df_trades['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = df_trades[df_trades['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) \
                       if losing_trades > 0 and avg_loss != 0 else 0
        
        final_capital = self.capital
        total_return = ((final_capital - self.initial_capital) / self.initial_capital) * 100
        
        # Métricas
        df_equity = pd.DataFrame(self.equity_curve)
        df_equity['returns'] = df_equity['equity'].pct_change()
        sharpe = df_equity['returns'].mean() / df_equity['returns'].std() * (252 ** 0.5) \
                if df_equity['returns'].std() > 0 else 0
        
        df_equity['peak'] = df_equity['equity'].cummax()
        df_equity['drawdown'] = (df_equity['equity'] - df_equity['peak']) / df_equity['peak']
        max_drawdown = df_equity['drawdown'].min()
        
        results = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': float(total_pnl),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'profit_factor': profit_factor,
            'initial_capital': float(self.initial_capital),
            'final_capital': float(final_capital),
            'total_return_pct': float(total_return),
            'sharpe_ratio': sharpe,
            'max_drawdown': float(max_drawdown),
            'slippage_pct': float(self.slippage_pct * 100),
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }
        
        return results