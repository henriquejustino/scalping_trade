"""
Backtest Engine - Versao Corrigida e Robusta
Correções principais:
1. Capital sempre atualizado (não fica preso ao inicial)
2. Timeframes sincronizados
3. Validações de trade rigorosas
4. Tracking de drawdown em tempo real
5. Slippage realista
6. TODOS os tipos Decimal/float devidamente convertidos
"""
import pandas as pd
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger
import numpy as np

from core.data.data_synchronizer import DataSynchronizer
from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
from strategies.market_detector import MarketRegimeDetector
from strategies.signal_validator import SignalValidator
from risk_management.position_sizer import PositionSizerV2
from risk_management.risk_calculator import RiskCalculator
from execution.slippage_model import SlippageModel
from core.engine.base_engine import Position, TradeLog

logger.add("data/logs/backtest_{time}.log", rotation="1 day")

class BacktestEngine:
    """Engine de backtest robusto com validações completas"""
    
    def __init__(
        self,
        data_manager,
        strategy: SmartScalpingEnsemble,
        initial_capital: Decimal = Decimal('10000'),
        risk_per_trade: Decimal = Decimal('0.02'),
        max_positions: int = 3,
        max_drawdown: Decimal = Decimal('0.15')
    ):
        self.data_manager = data_manager
        self.strategy = strategy
        self.regime_detector = MarketRegimeDetector()
        self.signal_validator = SignalValidator()
        self.position_sizer = PositionSizerV2()
        self.risk_calculator = RiskCalculator()
        self.slippage_model = SlippageModel()
        
        # Capital tracking CORRETO
        self.initial_capital = Decimal(str(initial_capital))
        self.closed_trades_pnl = Decimal('0')
        
        self.risk_per_trade = Decimal(str(risk_per_trade))
        self.max_positions = max_positions
        self.max_drawdown = Decimal(str(max_drawdown))
        
        # Tracking de drawdown
        self.peak_equity = self.initial_capital
        self.peak_daily_equity = self.initial_capital
        self.daily_start_equity = self.initial_capital
        
        # Estado
        self.stop_trading = False
        self.daily_loss = Decimal('0')
        
        # Histórico
        self.trades: List[TradeLog] = []
        self.current_position = None
        self.equity_history: List[Dict] = []
        self.errors: List[Dict] = []
        self.current_price = Decimal('0')
    
    @property
    def current_capital(self) -> Decimal:
        """Capital real = inicial - posições em risco + PnL fechado"""
        unrealized_pnl = Decimal('0')
        if self.current_position:
            unrealized_pnl = self.current_position.calculate_pnl(self.current_price)
        
        return self.initial_capital + self.closed_trades_pnl + unrealized_pnl
    
    @property
    def current_equity(self) -> Decimal:
        """Equity total (capital + posição aberta)"""
        return self.current_capital
    
    def run_backtest(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """Executa backtest completo com todas as validações"""
        
        logger.info(
            f"\n{'='*80}\n"
            f"BACKTEST: {symbol}\n"
            f"Periodo: {start_date} ate {end_date}\n"
            f"Capital Inicial: ${self.initial_capital}\n"
            f"{'='*80}\n"
        )
        
        try:
            # === 1. CARREGAR DADOS ===
            df_5m = self.data_manager.get_ohlcv_data(symbol, '5m', limit=1500)
            df_15m = self.data_manager.get_ohlcv_data(symbol, '15m', limit=1500)
            
            if df_5m.empty or df_15m.empty:
                return {'error': 'Dados historicos nao disponveis'}
            
            # === 2. SINCRONIZAR TIMEFRAMES ===
            try:
                df_5m, df_15m = DataSynchronizer.prepare_data_for_backtest(
                    df_5m, df_15m, start_date, end_date, min_candles=50
                )
            except Exception as e:
                return {'error': f'Erro ao sincronizar dados: {str(e)}'}
            
            if len(df_5m) < 50 or len(df_15m) < 10:
                return {'error': 'Dados insuficientes para backtest'}
            
            # === 3. ITERAR PELOS CANDLES ===
            for i in range(100, len(df_5m)):
                if self.stop_trading:
                    logger.warning("Backtest parado por limite de drawdown")
                    break
                
                self.current_price = Decimal(str(float(df_5m['close'].iloc[i])))
                current_time = df_5m.index[i]
                
                # Pega histórico até este ponto
                hist_5m = df_5m.iloc[:i+1].copy()
                hist_15m = df_15m[df_15m.index <= current_time].copy()
                
                if len(hist_15m) < 50:
                    continue
                
                # Detecta regime
                regime = self.regime_detector.detect_regime(hist_5m, hist_15m)
                
                # Monitora posição aberta
                if self.current_position is not None:
                    self._monitor_position(self.current_position, self.current_price, current_time)
                else:
                    # Procura novo sinal
                    self._check_entry_signal(
                        symbol, hist_5m, hist_15m, current_time,
                        self.current_price, regime
                    )
                
                # Registra equity
                self._record_equity(current_time, regime)
            
            # Fecha posição final
            if self.current_position:
                self._close_position(
                    self.current_position,
                    self.current_price,
                    df_5m.index[-1],
                    "Fim do backtest"
                )
            
            # === 4. GERA RESULTADOS ===
            return self._generate_results(symbol)
        
        except Exception as e:
            logger.error(f"Erro fatal no backtest: {e}", exc_info=True)
            self.add_error("BACKTEST_ERROR", str(e), "CRITICAL")
            return {'error': f'Erro no backtest: {str(e)}'}
    
    def validate_trade(self, side: str, entry: Decimal, sl: Decimal, tp: Decimal) -> bool:
        """Validação completa de trade antes de entrar"""
        
        entry = Decimal(str(entry))
        sl = Decimal(str(sl))
        tp = Decimal(str(tp))
        
        # 1. SL deve estar no lado correto
        if side == 'BUY':
            if sl >= entry:
                logger.debug(f"SL invalido BUY: {sl} >= {entry}")
                return False
            if tp <= entry:
                logger.debug(f"TP invalido BUY: {tp} <= {entry}")
                return False
        else:
            if sl <= entry:
                logger.debug(f"SL invalido SELL: {sl} <= {entry}")
                return False
            if tp >= entry:
                logger.debug(f"TP invalido SELL: {tp} >= {entry}")
                return False
        
        # 2. R:R deve ser aceitável (mínimo 1:1)
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = reward / risk if risk > Decimal('0') else Decimal('0')
        
        if rr < Decimal('1.0'):
            logger.debug(f"R:R insuficiente: {rr:.2f}:1")
            return False
        
        # 3. SL não deve estar muito perto
        min_sl_distance = entry * Decimal('0.002')
        if risk < min_sl_distance:
            logger.debug(f"SL muito perto: {risk} < {min_sl_distance}")
            return False
        
        return True
    
    def _check_entry_signal(
        self,
        symbol: str,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        timestamp: datetime,
        current_price: Decimal,
        regime: str
    ):
        """Verifica e valida sinal de entrada"""
        
        try:
            # 1. Valida regime
            if not self.regime_detector.is_tradeable_regime(regime):
                return
            
            # 2. Calcula volume ratio - TIPO CORRETO
            try:
                volume_ma = float(df_5m['volume'].rolling(20).mean().iloc[-1])
                current_vol = float(df_5m['volume'].iloc[-1])
                volume_ratio = current_vol / volume_ma if volume_ma > 0 else 1.0
            except:
                return
            
            # 3. Obtém sinal
            side, strength, details = self.strategy.get_ensemble_signal(df_5m, df_15m)
            
            if side is None:
                return
            
            # 4. Valida sinal
            try:
                if not self.signal_validator.validate(side, strength, df_5m, df_15m):
                    return
            except:
                return
            
            # 5. Calcula SL e TP - CONVERTE PARA DECIMAL
            try:
                stop_loss = Decimal(str(float(self.strategy.calculate_stop_loss(df_5m, current_price, side))))
                take_profit = Decimal(str(float(self.strategy.calculate_take_profit(df_5m, current_price, side))))
            except:
                return
            
            # 6. Valida trade
            if not self.validate_trade(side, current_price, stop_loss, take_profit):
                return
            
            # 7. Calcula quantidade
            try:
                filters = {
                    'tickSize': Decimal('0.01'),
                    'stepSize': Decimal('0.001'),
                    'minQty': Decimal('0.001'),
                    'minNotional': Decimal('5.0')
                }
                
                quantity = self.position_sizer.calculate_dynamic_position_size(
                    capital=self.current_capital,
                    entry_price=current_price,
                    stop_loss_price=stop_loss,
                    symbol_filters=filters,
                    signal_strength=float(strength),
                    volume_ratio=volume_ratio
                )
            except Exception as e:
                logger.debug(f"Erro ao calcular posicao: {e}")
                return
            
            if quantity is None:
                return
            
            # 8. Aplica slippage - TIPO CORRETO
            try:
                entry_with_slippage = Decimal(str(float(self.slippage_model.apply_entry_slippage(
                    current_price, side, volume_ratio, regime
                ))))
            except:
                entry_with_slippage = current_price
            
            # 9. Cria posição - CONVERSÃO SEGURA
            try:
                distance = abs(take_profit - entry_with_slippage)
                from config.settings import settings
                
                tp1_pct = Decimal(str(float(settings.TP1_PERCENTAGE)))
                tp2_pct = Decimal(str(float(settings.TP2_PERCENTAGE)))
                
                if side == 'BUY':
                    tp1 = entry_with_slippage + (distance * tp1_pct)
                    tp2 = entry_with_slippage + (distance * tp2_pct)
                else:
                    tp1 = entry_with_slippage - (distance * tp1_pct)
                    tp2 = entry_with_slippage - (distance * tp2_pct)
                
                self.current_position = Position(
                    symbol=symbol,
                    side=side,
                    entry_price=entry_with_slippage,
                    entry_quantity=quantity,
                    current_quantity=quantity,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    tp1=tp1,
                    tp1_hit=False,
                    tp2=tp2,
                    tp2_hit=False,
                    tp3=take_profit,
                    tp3_hit=False,
                    entry_time=timestamp,
                    signal_strength=float(strength),
                    regime=regime
                )
                
                logger.info(
                    f"ENTRADA: {side} {quantity:.6f} {symbol} @ "
                    f"${entry_with_slippage:.2f}"
                )
            except Exception as e:
                logger.debug(f"Erro ao criar posicao: {e}")
        
        except Exception as e:
            logger.error(f"Erro em _check_entry_signal: {e}", exc_info=True)
    
    def _monitor_position(self, position: Position, current_price: Decimal, timestamp: datetime):
        """Monitora posição aberta"""
        
        # Verifica stop loss
        if position.side == 'BUY':
            if current_price <= position.stop_loss:
                self._close_position(position, current_price, timestamp, "Stop Loss")
                return
        else:
            if current_price >= position.stop_loss:
                self._close_position(position, current_price, timestamp, "Stop Loss")
                return
        
        # Verifica take profit levels
        from config.settings import settings
        
        if position.side == 'BUY':
            if not position.tp1_hit and current_price >= position.tp1:
                position.tp1_hit = True
                exit_qty = position.current_quantity * Decimal(str(float(settings.TP1_EXIT_RATIO)))
                self._partial_exit(position, exit_qty, current_price, timestamp, "TP1")
                position.stop_loss = position.entry_price
            
            elif not position.tp2_hit and current_price >= position.tp2:
                position.tp2_hit = True
                exit_qty = position.current_quantity * Decimal(str(float(settings.TP2_EXIT_RATIO)))
                self._partial_exit(position, exit_qty, current_price, timestamp, "TP2")
            
            elif not position.tp3_hit and current_price >= position.take_profit:
                self._close_position(position, current_price, timestamp, "TP3")
        
        else:
            if not position.tp1_hit and current_price <= position.tp1:
                position.tp1_hit = True
                exit_qty = position.current_quantity * Decimal(str(float(settings.TP1_EXIT_RATIO)))
                self._partial_exit(position, exit_qty, current_price, timestamp, "TP1")
                position.stop_loss = position.entry_price
            
            elif not position.tp2_hit and current_price <= position.tp2:
                position.tp2_hit = True
                exit_qty = position.current_quantity * Decimal(str(float(settings.TP2_EXIT_RATIO)))
                self._partial_exit(position, exit_qty, current_price, timestamp, "TP2")
            
            elif not position.tp3_hit and current_price <= position.take_profit:
                self._close_position(position, current_price, timestamp, "TP3")
    
    def _partial_exit(self, position: Position, exit_quantity: Decimal, exit_price: Decimal, timestamp: datetime, reason: str):
        """Saída parcial com slippage"""
        
        exit_price = Decimal(str(exit_price))
        exit_quantity = Decimal(str(exit_quantity))
        
        try:
            exit_with_slippage = Decimal(str(float(self.slippage_model.apply_exit_slippage(
                exit_price, position.side, 1.0, position.regime
            ))))
        except:
            exit_with_slippage = exit_price
        
        if position.side == 'BUY':
            pnl = (exit_with_slippage - position.entry_price) * exit_quantity
        else:
            pnl = (position.entry_price - exit_with_slippage) * exit_quantity
        
        self.closed_trades_pnl += pnl
        position.current_quantity -= exit_quantity
        
        logger.info(f"Saida parcial {reason}: {exit_quantity:.6f} @ ${exit_price:.2f} | PnL: ${pnl:.2f}")
    
    def _close_position(self, position: Position, exit_price: Decimal, timestamp: datetime, reason: str):
        """Fecha posição com slippage"""
        
        exit_price = Decimal(str(exit_price))
        
        try:
            exit_with_slippage = Decimal(str(float(self.slippage_model.apply_exit_slippage(
                exit_price, position.side, 1.0, position.regime
            ))))
        except:
            exit_with_slippage = exit_price
        
        if position.side == 'BUY':
            pnl = (exit_with_slippage - position.entry_price) * position.current_quantity
        else:
            pnl = (position.entry_price - exit_with_slippage) * position.current_quantity
        
        self.closed_trades_pnl += pnl
        
        pnl_pct = (pnl / (position.entry_price * position.entry_quantity)) * Decimal('100') if position.entry_price > Decimal('0') else Decimal('0')
        duration = (timestamp - position.entry_time).total_seconds()
        
        trade = TradeLog(
            symbol=position.symbol,
            side=position.side,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            entry_quantity=position.entry_quantity,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            exit_time=timestamp,
            exit_price=exit_with_slippage,
            exit_quantity=position.current_quantity,
            exit_reason=reason,
            pnl=pnl,
            pnl_pct=pnl_pct,
            signal_strength=position.signal_strength,
            regime=position.regime,
            duration_seconds=int(duration),
            winning=pnl > Decimal('0')
        )
        
        self.trades.append(trade)
        
        logger.info(f"Posicao fechada ({reason}): PnL: ${pnl:.2f} ({pnl_pct:.2f}%)")
        
        self.current_position = None
    
    def _record_equity(self, timestamp: datetime, regime: str):
        """Registra equity e valida drawdowns"""
        
        current_eq = self.current_equity
        
        if current_eq > self.peak_equity:
            self.peak_equity = current_eq
        if current_eq > self.peak_daily_equity:
            self.peak_daily_equity = current_eq
        
        drawdown = (self.peak_equity - current_eq) / self.peak_equity if self.peak_equity > Decimal('0') else Decimal('0')
        
        if drawdown > self.max_drawdown:
            logger.critical(f"DRAWDOWN LIMITE ATINGIDO: {float(drawdown)*100:.2f}%")
            self.stop_trading = True
        
        self.equity_history.append({
            'timestamp': timestamp,
            'equity': float(current_eq),
            'capital': float(self.closed_trades_pnl + self.initial_capital),
            'drawdown': float(drawdown),
            'regime': regime
        })
    
    def _generate_results(self, symbol: str) -> Dict:
        """Gera relatório de resultados"""
        
        if not self.trades:
            return {'error': 'Nenhum trade executado'}
        
        df_trades = pd.DataFrame([t.to_dict() for t in self.trades])
        df_equity = pd.DataFrame(self.equity_history)
        
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['winning']])
        losing_trades = len(df_trades[~df_trades['winning']])
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        total_pnl = df_trades['pnl'].sum()
        avg_win = df_trades[df_trades['winning']]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = df_trades[~df_trades['winning']]['pnl'].mean() if losing_trades > 0 else 0
        
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else 0
        
        final_capital = self.current_capital
        total_return = ((final_capital - self.initial_capital) / self.initial_capital) * 100 if self.initial_capital > 0 else 0
        
        df_equity['returns'] = df_equity['equity'].pct_change()
        sharpe = df_equity['returns'].mean() / df_equity['returns'].std() * (252 ** 0.5) if df_equity['returns'].std() > 0 else 0
        
        max_drawdown = df_equity['drawdown'].min()
        
        return {
            'symbol': symbol,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': float(win_rate),
            'total_pnl': float(total_pnl),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'profit_factor': float(profit_factor),
            'initial_capital': float(self.initial_capital),
            'final_capital': float(final_capital),
            'total_return_pct': float(total_return),
            'sharpe_ratio': float(sharpe),
            'max_drawdown': float(max_drawdown),
            'trades': [t.to_dict() for t in self.trades],
            'equity_curve': self.equity_history,
            'errors': self.errors
        }
    
    def add_error(self, error_type: str, message: str, severity: str = "WARNING"):
        """Log estruturado de erros"""
        self.errors.append({
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': message,
            'severity': severity
        })