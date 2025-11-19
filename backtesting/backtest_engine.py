"""
Backtest Engine V2 - Versão Corrigida e Robusta
Correções principais:
1. Capital sempre atualizado (não fica preso ao inicial)
2. Timeframes sincronizados
3. Validações de trade rigorosas
4. Tracking de drawdown em tempo real
5. Slippage realista
"""
import pandas as pd
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from loguru import logger
import numpy as np

from core.data.data_synchronizer import DataSynchronizer
from core.engine.base_engine import BaseEngine, Position, TradeLog
from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
from strategies.market_detector import MarketRegimeDetector
from strategies.signal_validator import SignalValidator
from risk_management.position_sizer import PositionSizerV2
from risk_management.risk_calculator import RiskCalculator
from execution.slippage_model import SlippageModel

logger.add("data/logs/backtest_v2_{time}.log", rotation="1 day")

class BacktestEngineV2(BaseEngine):
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
        super().__init__()
        
        self.data_manager = data_manager
        self.strategy = strategy
        self.regime_detector = MarketRegimeDetector()
        self.signal_validator = SignalValidator()
        self.position_sizer = PositionSizerV2()
        self.risk_calculator = RiskCalculator()
        self.slippage_model = SlippageModel()
        
        # Capital tracking CORRETO
        self.initial_capital = initial_capital
        self.closed_trades_pnl = Decimal('0')  # PnL de trades fechados
        
        self.risk_per_trade = risk_per_trade
        self.max_positions = max_positions
        self.max_drawdown = max_drawdown
        
        # Tracking de drawdown
        self.peak_equity = initial_capital
        self.peak_daily_equity = initial_capital
        self.daily_start_equity = initial_capital
        
        # Estado
        self.stop_trading = False
        self.daily_loss = Decimal('0')
    
    @property
    def current_capital(self) -> Decimal:
        """
        ✅ CORRIGIDO: Capital real = inicial - posições em risco + PnL fechado
        """
        unrealized_pnl = Decimal('0')
        if self.current_position:
            unrealized_pnl = self.current_position.calculate_pnl(
                self.current_price
            )
        
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
            f"🚀 BACKTEST V2: {symbol}\n"
            f"Período: {start_date} até {end_date}\n"
            f"Capital Inicial: ${self.initial_capital}\n"
            f"{'='*80}\n"
        )
        
        try:
            # === 1. CARREGAR DADOS ===
            df_5m = self.data_manager.get_ohlcv_data(symbol, '5m', limit=1500)
            df_15m = self.data_manager.get_ohlcv_data(symbol, '15m', limit=1500)
            
            if df_5m.empty or df_15m.empty:
                return {'error': 'Dados históricos não disponíveis'}
            
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
                
                self.current_price = Decimal(str(df_5m['close'].iloc[i]))
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
        """
        ✅ NOVO: Validação completa de trade antes de entrar
        """
        
        # 1. SL deve estar no lado correto
        if side == 'BUY':
            if sl >= entry:
                logger.debug(f"❌ SL inválido BUY: {sl} >= {entry}")
                return False
            if tp <= entry:
                logger.debug(f"❌ TP inválido BUY: {tp} <= {entry}")
                return False
        else:
            if sl <= entry:
                logger.debug(f"❌ SL inválido SELL: {sl} <= {entry}")
                return False
            if tp >= entry:
                logger.debug(f"❌ TP inválido SELL: {tp} >= {entry}")
                return False
        
        # 2. R:R deve ser aceitável (mínimo 1:1)
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = reward / risk if risk > 0 else 0
        
        if rr < Decimal('1.0'):
            logger.debug(f"❌ R:R insuficiente: {rr:.2f}:1")
            return False
        
        # 3. SL não deve estar muito perto
        min_sl_distance = entry * Decimal('0.002')  # 0.2%
        if risk < min_sl_distance:
            logger.debug(f"❌ SL muito perto: {risk} < {min_sl_distance}")
            return False
        
        # 4. TP não deve estar muito longe (limite de risco)
        max_tp_distance = entry * Decimal('0.10')  # 10%
        if reward > max_tp_distance:
            logger.debug(f"❌ TP muito distante: {reward} > {max_tp_distance}")
            return False
        
        return True
    
    def execute_entry(self) -> bool:
        """✅ IMPLEMENTADO: Entrada com validações"""
        # Implementado em _check_entry_signal
        pass
    
    def execute_exit(self) -> bool:
        """✅ IMPLEMENTADO: Saída com validações"""
        # Implementado em _monitor_position
        pass
    
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
        
        # 1. Valida regime
        if not self.regime_detector.is_tradeable_regime(regime):
            logger.debug(f"Regime não-tradeable: {regime}")
            return
        
        # 2. Calcula volume ratio
        volume_ma = df_5m['volume'].rolling(20).mean().iloc[-1]
        volume_ratio = df_5m['volume'].iloc[-1] / volume_ma if volume_ma > 0 else 1.0
        
        # 3. Obtém sinal
        side, strength, details = self.strategy.get_ensemble_signal(df_5m, df_15m)
        
        # 4. Valida sinal
        if side is None:
            return
        
        if not self.signal_validator.validate(side, strength, df_5m, df_15m):
            logger.debug("Sinal rejeitado pela validação")
            return
        
        # 5. Calcula SL e TP
        stop_loss = self.strategy.calculate_stop_loss(df_5m, current_price, side)
        take_profit = self.strategy.calculate_take_profit(df_5m, current_price, side)
        
        # 6. ✅ VALIDA trade
        if not self.validate_trade(side, current_price, stop_loss, take_profit):
            logger.debug(f"Trade rejeitado: inválido {side} @ {current_price}")
            return
        
        # 7. Calcula quantidade
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
            signal_strength=strength,
            volume_ratio=volume_ratio
        )
        
        if quantity is None:
            logger.debug("Posição rejeitada (tamanho inválido)")
            return
        
        # 8. ✅ APLICA SLIPPAGE REALISTA
        entry_with_slippage = self.slippage_model.apply_entry_slippage(
            current_price, side, volume_ratio, regime
        )
        
        # 9. Cria posição
        distance = abs(take_profit - entry_with_slippage)
        from config.settings import settings
        
        if side == 'BUY':
            tp1 = entry_with_slippage + (distance * settings.TP1_PERCENTAGE)
            tp2 = entry_with_slippage + (distance * settings.TP2_PERCENTAGE)
        else:
            tp1 = entry_with_slippage - (distance * settings.TP1_PERCENTAGE)
            tp2 = entry_with_slippage - (distance * settings.TP2_PERCENTAGE)
        
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
            signal_strength=strength,
            regime=regime
        )
        
        logger.info(
            f"✅ ENTRADA: {side} {quantity:.6f} {symbol} @ "
            f"${entry_with_slippage:.2f} | "
            f"SL: ${stop_loss:.2f} | TP: ${take_profit:.2f} | "
            f"Força: {strength:.2f} | Regime: {regime}"
        )
    
    def _monitor_position(
        self,
        position: Position,
        current_price: Decimal,
        timestamp: datetime
    ):
        """Monitora posição aberta"""
        
        # 1. Verifica stop loss
        if position.side == 'BUY':
            if current_price <= position.stop_loss:
                self._close_position(position, current_price, timestamp, "Stop Loss")
                return
        else:
            if current_price >= position.stop_loss:
                self._close_position(position, current_price, timestamp, "Stop Loss")
                return
        
        # 2. Verifica take profit levels
        from config.settings import settings
        
        if position.side == 'BUY':
            if not position.tp1_hit and current_price >= position.tp1:
                position.tp1_hit = True
                exit_qty = position.current_quantity * settings.TP1_EXIT_RATIO
                self._partial_exit(position, exit_qty, current_price, timestamp, "TP1")
                position.stop_loss = position.entry_price  # Move SL para breakeven
            
            elif not position.tp2_hit and current_price >= position.tp2:
                position.tp2_hit = True
                exit_qty = position.current_quantity * settings.TP2_EXIT_RATIO
                self._partial_exit(position, exit_qty, current_price, timestamp, "TP2")
            
            elif not position.tp3_hit and current_price >= position.take_profit:
                self._close_position(position, current_price, timestamp, "TP3")
        
        else:  # SELL
            if not position.tp1_hit and current_price <= position.tp1:
                position.tp1_hit = True
                exit_qty = position.current_quantity * settings.TP1_EXIT_RATIO
                self._partial_exit(position, exit_qty, current_price, timestamp, "TP1")
                position.stop_loss = position.entry_price
            
            elif not position.tp2_hit and current_price <= position.tp2:
                position.tp2_hit = True
                exit_qty = position.current_quantity * settings.TP2_EXIT_RATIO
                self._partial_exit(position, exit_qty, current_price, timestamp, "TP2")
            
            elif not position.tp3_hit and current_price <= position.take_profit:
                self._close_position(position, current_price, timestamp, "TP3")
        
        # 3. Update max profit
        unrealized_pnl_pct = position.calculate_pnl_pct(current_price)
        if unrealized_pnl_pct > position.max_profit:
            position.max_profit = unrealized_pnl_pct
    
    def _partial_exit(
        self,
        position: Position,
        exit_quantity: Decimal,
        exit_price: Decimal,
        timestamp: datetime,
        reason: str
    ):
        """Saída parcial com slippage"""
        
        # ✅ APLICA SLIPPAGE NA SAÍDA
        exit_with_slippage = self.slippage_model.apply_exit_slippage(
            exit_price, position.side, Decimal('1.0'), position.regime
        )
        
        if position.side == 'BUY':
            pnl = (exit_with_slippage - position.entry_price) * exit_quantity
        else:
            pnl = (position.entry_price - exit_with_slippage) * exit_quantity
        
        self.closed_trades_pnl += pnl
        position.current_quantity -= exit_quantity
        
        logger.info(
            f"💰 Saída parcial {reason}: {exit_quantity:.6f} @ "
            f"${exit_price:.2f} | PnL: ${pnl:.2f} | "
            f"Restante: {position.current_quantity:.6f}"
        )
    
    def _close_position(
        self,
        position: Position,
        exit_price: Decimal,
        timestamp: datetime,
        reason: str
    ):
        """Fecha posição com slippage"""
        
        # ✅ APLICA SLIPPAGE NA SAÍDA
        exit_with_slippage = self.slippage_model.apply_exit_slippage(
            exit_price, position.side, Decimal('1.0'), position.regime
        )
        
        if position.side == 'BUY':
            pnl = (exit_with_slippage - position.entry_price) * position.current_quantity
        else:
            pnl = (position.entry_price - exit_with_slippage) * position.current_quantity
        
        self.closed_trades_pnl += pnl
        
        pnl_pct = (pnl / (position.entry_price * position.entry_quantity)) * Decimal('100')
        duration = (timestamp - position.entry_time).total_seconds()
        
        # Registra trade
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
            winning=pnl > 0
        )
        
        self.trades.append(trade)
        
        color = "🟢" if pnl > 0 else "🔴"
        logger.info(
            f"{color} Posição fechada ({reason}): "
            f"PnL: ${pnl:.2f} ({pnl_pct:.2f}%) | {duration/60:.0f}m"
        )
        
        self.current_position = None
        
        # ✅ Update daily loss
        if pnl < 0:
            self.daily_loss += abs(pnl)
    
    def _record_equity(self, timestamp: datetime, regime: str):
        """Registra equity e valida drawdowns"""
        
        current_eq = self.current_equity
        
        # Update peak equity
        if current_eq > self.peak_equity:
            self.peak_equity = current_eq
        if current_eq > self.peak_daily_equity:
            self.peak_daily_equity = current_eq
        
        # ✅ Calcula drawdown
        drawdown = (self.peak_equity - current_eq) / self.peak_equity if self.peak_equity > 0 else Decimal('0')
        
        # ✅ Valida limite de drawdown
        if drawdown > self.max_drawdown:
            logger.critical(
                f"⛔ DRAWDOWN LIMITE ATINGIDO: {float(drawdown)*100:.2f}% > {float(self.max_drawdown)*100:.2f}%"
            )
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
        
        profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) \
                       if losing_trades > 0 and avg_loss != 0 else 0
        
        final_capital = self.current_capital
        total_return = ((final_capital - self.initial_capital) / self.initial_capital) * 100
        
        # Sharpe ratio
        df_equity['returns'] = df_equity['equity'].pct_change()
        sharpe = df_equity['returns'].mean() / df_equity['returns'].std() * (252 ** 0.5) \
                if df_equity['returns'].std() > 0 else 0
        
        max_drawdown = df_equity['drawdown'].min()
        
        results = {
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
        
        logger.info(f"\n{'='*80}")
        logger.info(f"RESULTADOS: {symbol}")
        logger.info(f"{'='*80}")
        logger.info(f"Total de Trades: {total_trades}")
        logger.info(f"Win Rate: {win_rate*100:.2f}%")
        logger.info(f"Profit Factor: {profit_factor:.2f}")
        logger.info(f"Sharpe Ratio: {sharpe:.2f}")
        logger.info(f"Max Drawdown: {max_drawdown*100:.2f}%")
        logger.info(f"Retorno Total: {total_return:.2f}%")
        logger.info(f"{'='*80}\n")
        
        return results