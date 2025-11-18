import pandas as pd
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from loguru import logger

# Importa TODAS as estratégias
from strategies.indicators.rsi_strategy import RSIStrategy
from strategies.indicators.ema_crossover import EMACrossover
from strategies.indicators.bollinger_bands import BollingerBandsStrategy
from strategies.indicators.vwap_strategy import VWAPStrategy
from strategies.indicators.order_flow import OrderFlowStrategy

# Novas estratégias
from strategies.indicators.ema_vwap_strategy import EMAVWAPCrossover
from strategies.indicators.pullback_ema_strategy import PullbackEMAStrategy
from strategies.indicators.bollinger_rsi_advanced import BollingerRSIAdvanced
from strategies.indicators.breakout_reteste_strategy import BreakoutRetesteStrategy
from strategies.indicators.liquidez_strategy import LiquidezStrategy

# Market Regime Detector
from strategies.market_detector import MarketRegimeDetector


class SmartScalpingEnsemble:
    """
    Ensemble Inteligente que:
    1. Detecta tipo de mercado
    2. Ativa automaticamente as melhores estratégias para aquele regime
    3. Combina sinais de forma ponderada
    """
    
    def __init__(self):
        # === TODAS AS ESTRATÉGIAS DISPONÍVEIS ===
        self.all_strategies = {
            # Originais
            'rsi': RSIStrategy(),
            'ema': EMACrossover(),
            'bb': BollingerBandsStrategy(),
            'vwap': VWAPStrategy(),
            'order_flow': OrderFlowStrategy(),
            
            # Novas
            'ema_vwap': EMAVWAPCrossover(),
            'pullback': PullbackEMAStrategy(),
            'bollinger_rsi': BollingerRSIAdvanced(),
            'breakout': BreakoutRetesteStrategy(),
            'liquidez': LiquidezStrategy()
        }
        
        # Detector de regime
        self.regime_detector = MarketRegimeDetector()
        
        # === MAPEAMENTO: REGIME -> ESTRATÉGIAS ===
        self.regime_strategies = {
            'TRENDING_UP': {
                'ema_vwap': 0.30,      # EMA + VWAP para tendência
                'pullback': 0.30,       # Pullback na tendência
                'ema': 0.20,            # EMA crossover
                'vwap': 0.20            # VWAP confirmation
            },
            'TRENDING_DOWN': {
                'ema_vwap': 0.30,
                'pullback': 0.30,
                'ema': 0.20,
                'vwap': 0.20
            },
            'RANGING': {
                'bollinger_rsi': 0.35,  # BB + RSI para reversão
                'bb': 0.25,              # Bollinger puro
                'rsi': 0.25,             # RSI puro
                'vwap': 0.15             # Mean reversion no VWAP
            },
            'HIGH_VOLATILITY': {
                'liquidez': 0.40,        # Captura liquidez
                'bollinger_rsi': 0.30,   # Extremos
                'order_flow': 0.30       # Pressão compradora/vendedora
            },
            'BREAKOUT_FORMING': {
                'breakout': 0.50,        # Especialista em breakout
                'ema_vwap': 0.25,        # Confirma direção
                'order_flow': 0.25       # Confirma pressão
            }
        }
        
        self.current_regime = None
        self.active_strategies = {}
    
    def get_ensemble_signal(
        self,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame
    ) -> Tuple[Optional[str], float, Dict]:
        """
        Retorna sinal consolidado:
        1. Detecta regime
        2. Ativa estratégias apropriadas
        3. Combina sinais
        """
        
        # === DETECTA REGIME DO MERCADO ===
        self.current_regime = self.regime_detector.detect_regime(df_5m, df_15m)
        
        # === SELECIONA ESTRATÉGIAS PARA O REGIME ===
        self.active_strategies = self.regime_strategies.get(
            self.current_regime,
            self.regime_strategies['RANGING']  # Fallback
        )
        
        logger.info(f"📊 Regime: {self.current_regime}")
        logger.info(f"🎯 Estratégias ativas: {list(self.active_strategies.keys())}")
        
        # === COLETA SINAIS DAS ESTRATÉGIAS ATIVAS ===
        signals_5m = {}
        signals_15m = {}
        
        for name, weight in self.active_strategies.items():
            strategy = self.all_strategies[name]
            
            try:
                # Sinais do 5m
                side_5m, strength_5m = strategy.get_entry_signal(df_5m)
                signals_5m[name] = (side_5m, strength_5m, weight)
                
                # Sinais do 15m (confirmação)
                side_15m, strength_15m = strategy.get_entry_signal(df_15m)
                signals_15m[name] = (side_15m, strength_15m)
                
            except Exception as e:
                logger.warning(f"Erro em {name}: {e}")
                signals_5m[name] = (None, 0.0, weight)
                signals_15m[name] = (None, 0.0)
        
        # === CALCULA FORÇA PONDERADA ===
        buy_strength = 0.0
        sell_strength = 0.0
        
        for name, (side_5m, strength_5m, weight) in signals_5m.items():
            side_15m, strength_15m = signals_15m[name]
            
            # Combina 5m (70%) + 15m (30%)
            combined_strength = (strength_5m * 0.7) + (strength_15m * 0.3)
            
            if side_5m == 'BUY':
                # Bônus se 15m confirma
                if side_15m == 'BUY':
                    combined_strength *= 1.15
                buy_strength += combined_strength * weight
                
            elif side_5m == 'SELL':
                if side_15m == 'SELL':
                    combined_strength *= 1.15
                sell_strength += combined_strength * weight
        
        # === DETERMINA SINAL FINAL ===
        details = {
            'regime': self.current_regime,
            'active_strategies': list(self.active_strategies.keys()),
            'buy_strength': buy_strength,
            'sell_strength': sell_strength,
            'signals_5m': {k: (v[0], v[1]) for k, v in signals_5m.items()},
            'signals_15m': signals_15m
        }
        
        # Threshold adaptativo baseado no regime
        min_threshold = self._get_threshold_for_regime(self.current_regime)
        
        if buy_strength > sell_strength and buy_strength > min_threshold:
            logger.info(f"✅ SINAL LONG | Força: {buy_strength:.2f}")
            return 'BUY', buy_strength, details
        
        elif sell_strength > buy_strength and sell_strength > min_threshold:
            logger.info(f"✅ SINAL SHORT | Força: {sell_strength:.2f}")
            return 'SELL', sell_strength, details
        
        return None, 0.0, details
    
    def _get_threshold_for_regime(self, regime: str) -> float:
        """Threshold mínimo varia por regime"""
        thresholds = {
            'TRENDING_UP': 0.25,      # Mais permissivo em tendência
            'TRENDING_DOWN': 0.25,
            'RANGING': 0.35,          # Mais rigoroso em lateral
            'HIGH_VOLATILITY': 0.30,  # Moderado em volatilidade
            'BREAKOUT_FORMING': 0.40  # Muito rigoroso em breakout
        }
        return thresholds.get(regime, 0.30)
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """Usa média dos SLs das estratégias ativas"""
        stop_losses = []
        
        for name in self.active_strategies.keys():
            strategy = self.all_strategies[name]
            try:
                sl = strategy.calculate_stop_loss(df, entry_price, side)
                stop_losses.append(sl)
            except Exception as e:
                logger.warning(f"Erro calculando SL em {name}: {e}")
        
        if not stop_losses:
            # Fallback
            if side == 'BUY':
                return entry_price * Decimal('0.99')
            else:
                return entry_price * Decimal('1.01')
        
        return sum(stop_losses) / len(stop_losses)
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """Usa média dos TPs das estratégias ativas"""
        take_profits = []
        
        for name in self.active_strategies.keys():
            strategy = self.all_strategies[name]
            try:
                tp = strategy.calculate_take_profit(df, entry_price, side)
                take_profits.append(tp)
            except Exception as e:
                logger.warning(f"Erro calculando TP em {name}: {e}")
        
        if not take_profits:
            # Fallback
            if side == 'BUY':
                return entry_price * Decimal('1.02')
            else:
                return entry_price * Decimal('0.98')
        
        return sum(take_profits) / len(take_profits)
    
    def get_regime_info(self) -> Dict:
        """Retorna informações do regime atual"""
        return {
            'current_regime': self.current_regime,
            'active_strategies': list(self.active_strategies.keys()),
            'summary': self.regime_detector.get_regime_summary()
        }