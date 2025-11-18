import pandas as pd
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from loguru import logger
from strategies.indicators.rsi_strategy import RSIStrategy
from strategies.indicators.ema_crossover import EMACrossover
from strategies.indicators.bollinger_bands import BollingerBandsStrategy
from strategies.indicators.vwap_strategy import VWAPStrategy
from strategies.indicators.order_flow import OrderFlowStrategy

class SmartScalpingEnsemble:
    """
    Ensemble Simplificado para Scalping:
    - Prioriza sinais alinhados entre timeframes
    - Stop Loss e Take Profit baseados em ATR (não em % fixo)
    - Thresholds adaptativos
    """
    
    def __init__(self):
        # Todas as estratégias
        self.strategies = {
            'rsi': RSIStrategy(),
            'ema': EMACrossover(),
            'bb': BollingerBandsStrategy(),
            'vwap': VWAPStrategy(),
            'order_flow': OrderFlowStrategy()
        }
        
        # Pesos equilibrados
        self.weights = {
            'rsi': 0.25,
            'ema': 0.25,
            'bb': 0.20,
            'vwap': 0.15,
            'order_flow': 0.15
        }
    
    def get_ensemble_signal(
        self,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame
    ) -> Tuple[Optional[str], float, Dict]:
        """
        Procura por convergência entre:
        1. Múltiplas estratégias NO MESMO TIMEFRAME
        2. Alinhamento entre timeframes (5m e 15m)
        """
        
        signals_5m = {}
        signals_15m = {}
        
        # === COLETA SINAIS ===
        for name, strategy in self.strategies.items():
            try:
                side_5m, strength_5m = strategy.get_entry_signal(df_5m)
                signals_5m[name] = (side_5m, strength_5m)
                
                side_15m, strength_15m = strategy.get_entry_signal(df_15m)
                signals_15m[name] = (side_15m, strength_15m)
            except Exception as e:
                logger.debug(f"Erro em {name}: {e}")
                signals_5m[name] = (None, 0.0)
                signals_15m[name] = (None, 0.0)
        
        # === ANÁLISE DE CONVERGÊNCIA ===
        # Conta quantas estratégias sinalizam BUY/SELL em cada timeframe
        buy_count_5m = sum(1 for s, _ in signals_5m.values() if s == 'BUY')
        sell_count_5m = sum(1 for s, _ in signals_5m.values() if s == 'SELL')
        buy_count_15m = sum(1 for s, _ in signals_15m.values() if s == 'BUY')
        sell_count_15m = sum(1 for s, _ in signals_15m.values() if s == 'SELL')
        
        # === SCORING COM PESOS ===
        buy_score_5m = 0.0
        sell_score_5m = 0.0
        
        for name, (side, strength) in signals_5m.items():
            if side == 'BUY':
                buy_score_5m += strength * self.weights[name]
            elif side == 'SELL':
                sell_score_5m += strength * self.weights[name]
        
        buy_score_15m = 0.0
        sell_score_15m = 0.0
        
        for name, (side, strength) in signals_15m.items():
            if side == 'BUY':
                buy_score_15m += strength * self.weights[name]
            elif side == 'SELL':
                sell_score_15m += strength * self.weights[name]
        
        # === COMBINAÇÃO DE SCORES ===
        # 5m = 65% da decisão (entrada rápida)
        # 15m = 35% da decisão (confirmação de tendência)
        
        final_buy_score = (buy_score_5m * 0.65) + (buy_score_15m * 0.35)
        final_sell_score = (sell_score_5m * 0.65) + (sell_score_15m * 0.35)
        
        # === BÔNUS POR ALINHAMENTO ===
        # Se ambos timeframes concordam, aumenta confiança
        if buy_count_5m >= 2 and buy_count_15m >= 2:
            final_buy_score *= 1.25  # 25% de bônus
        
        if sell_count_5m >= 2 and sell_count_15m >= 2:
            final_sell_score *= 1.25
        
        # === PENALIDADE POR DIVERGÊNCIA ===
        # Se 5m e 15m discordam, reduz confiança
        if (buy_score_5m > 0.4 and sell_score_15m > 0.4):
            final_buy_score *= 0.5  # Penalidade severa
        
        if (sell_score_5m > 0.4 and buy_score_15m > 0.4):
            final_sell_score *= 0.5
        
        # === THRESHOLD ADAPTATIVO ===
        # Com muita convergência (3+ sinais): threshold baixo
        # Com pouca convergência: threshold alto
        
        if buy_count_5m >= 3 or buy_count_15m >= 3:
            buy_threshold = 0.25
        elif buy_count_5m >= 2 or buy_count_15m >= 2:
            buy_threshold = 0.35
        else:
            buy_threshold = 0.45
        
        if sell_count_5m >= 3 or sell_count_15m >= 3:
            sell_threshold = 0.25
        elif sell_count_5m >= 2 or sell_count_15m >= 2:
            sell_threshold = 0.35
        else:
            sell_threshold = 0.45
        
        # === DECISÃO FINAL ===
        details = {
            'buy_score': round(final_buy_score, 4),
            'sell_score': round(final_sell_score, 4),
            'buy_threshold': buy_threshold,
            'sell_threshold': sell_threshold,
            'buy_agreements_5m': buy_count_5m,
            'sell_agreements_5m': sell_count_5m,
            'buy_agreements_15m': buy_count_15m,
            'sell_agreements_15m': sell_count_15m,
            'signals_5m': {k: (v[0], round(v[1], 3)) for k, v in signals_5m.items()},
            'signals_15m': {k: (v[0], round(v[1], 3)) for k, v in signals_15m.items()}
        }
        
        if final_buy_score > final_sell_score and final_buy_score > buy_threshold:
            final_strength = min(final_buy_score, 1.0)
            logger.info(
                f"✅ SINAL LONG - Score: {final_buy_score:.3f} "
                f"(Threshold: {buy_threshold}) | Acordos: 5m={buy_count_5m} 15m={buy_count_15m}"
            )
            return 'BUY', final_strength, details
        
        elif final_sell_score > final_buy_score and final_sell_score > sell_threshold:
            final_strength = min(final_sell_score, 1.0)
            logger.info(
                f"✅ SINAL SHORT - Score: {final_sell_score:.3f} "
                f"(Threshold: {sell_threshold}) | Acordos: 5m={sell_count_5m} 15m={sell_count_15m}"
            )
            return 'SELL', final_strength, details
        
        return None, 0.0, details
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """
        SL baseado em ATR (robusto para different volatilidades)
        Usa mediana de todos os estratégias
        """
        stop_losses = []
        
        for strategy in self.strategies.values():
            try:
                sl = strategy.calculate_stop_loss(df, entry_price, side)
                if sl:
                    stop_losses.append(float(sl))
            except Exception as e:
                pass
        
        if not stop_losses:
            # Fallback: 2% de distância
            if side == 'BUY':
                return entry_price * Decimal('0.98')
            else:
                return entry_price * Decimal('1.02')
        
        # Mediana é mais robusta que média
        stop_losses.sort()
        median = stop_losses[len(stop_losses) // 2]
        return Decimal(str(median))
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """
        TP: Mantém R:R razoável (~1:1.5)
        Usa mediana
        """
        take_profits = []
        
        for strategy in self.strategies.values():
            try:
                tp = strategy.calculate_take_profit(df, entry_price, side)
                if tp:
                    take_profits.append(float(tp))
            except Exception as e:
                pass
        
        if not take_profits:
            # Fallback
            if side == 'BUY':
                return entry_price * Decimal('1.03')
            else:
                return entry_price * Decimal('0.97')
        
        take_profits.sort()
        median = take_profits[len(take_profits) // 2]
        return Decimal(str(median))