import pandas as pd
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from loguru import logger
from strategies.indicators.rsi_strategy import RSIStrategy
from strategies.indicators.ema_crossover import EMACrossover
from strategies.indicators.bollinger_bands import BollingerBandsStrategy
from strategies.indicators.vwap_strategy import VWAPStrategy
from strategies.indicators.order_flow import OrderFlowStrategy

class ScalpingEnsemble:
    def __init__(self):
        self.strategies = {
            'rsi': RSIStrategy(),
            'ema': EMACrossover(),
            'bb': BollingerBandsStrategy(),
            'vwap': VWAPStrategy(),
            'order_flow': OrderFlowStrategy()
        }
        
        # Pesos para cada estratégia (mais balanceado)
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
        Retorna sinal consolidado de todas as estratégias
        Returns: (side, signal_strength, details)
        
        IMPORTANTE: 5m deve estar alinhado com 15m para ser levado a sério
        """
        signals_5m = {}
        signals_15m = {}
        
        # === COLETA SINAIS DO 5m ===
        for name, strategy in self.strategies.items():
            try:
                side, strength = strategy.get_entry_signal(df_5m)
                signals_5m[name] = (side, strength)
            except Exception as e:
                logger.warning(f"Erro em {name} (5m): {e}")
                signals_5m[name] = (None, 0.0)
        
        # === COLETA SINAIS DO 15m (confirmação) ===
        for name, strategy in self.strategies.items():
            try:
                side, strength = strategy.get_entry_signal(df_15m)
                signals_15m[name] = (side, strength)
            except Exception as e:
                logger.warning(f"Erro em {name} (15m): {e}")
                signals_15m[name] = (None, 0.0)
        
        # === CONSOLIDAÇÃO DE SINAIS ===
        buy_strength = 0.0
        sell_strength = 0.0
        buy_agreements = 0
        sell_agreements = 0
        
        for name, weight in self.weights.items():
            side_5m, strength_5m = signals_5m[name]
            side_15m, strength_15m = signals_15m[name]
            
            # === SCORING: Como combinar os timeframes? ===
            # Cenário 1: 5m BUY + 15m BUY = força máxima
            # Cenário 2: 5m BUY + 15m neutro/SELL = força média (pullback)
            # Cenário 3: 5m BUY + 15m SELL = força mínima (rejeição)
            
            if side_5m == 'BUY':
                if side_15m == 'BUY':
                    # Alinhamento perfeito = 1.2x de bônus
                    combined_strength = strength_5m * 1.2
                    buy_agreements += 1
                elif side_15m is None:
                    # 5m sozinho em tendência neutra = 0.9x de penalidade
                    combined_strength = strength_5m * 0.9
                else:
                    # 15m discorda (SHORT) = 0.5x penalidade severa
                    combined_strength = strength_5m * 0.5
                
                buy_strength += combined_strength * weight
            
            elif side_5m == 'SELL':
                if side_15m == 'SELL':
                    combined_strength = strength_5m * 1.2
                    sell_agreements += 1
                elif side_15m is None:
                    combined_strength = strength_5m * 0.9
                else:
                    combined_strength = strength_5m * 0.5
                
                sell_strength += combined_strength * weight
        
        # === THRESHOLD ADAPTATIVO ===
        # Com 3+ sinais alinhados: threshold = 0.25
        # Com 2 sinais: threshold = 0.35
        # Com 1 sinal: threshold = 0.50
        
        if buy_agreements >= 3:
            buy_threshold = 0.25
        elif buy_agreements >= 2:
            buy_threshold = 0.35
        else:
            buy_threshold = 0.50
        
        if sell_agreements >= 3:
            sell_threshold = 0.25
        elif sell_agreements >= 2:
            sell_threshold = 0.35
        else:
            sell_threshold = 0.50
        
        # === DETERMINA SINAL FINAL ===
        details = {
            'buy_strength': float(buy_strength),
            'sell_strength': float(sell_strength),
            'buy_agreements': buy_agreements,
            'sell_agreements': sell_agreements,
            'signals_5m': {k: (v[0], round(v[1], 3)) for k, v in signals_5m.items()},
            'signals_15m': {k: (v[0], round(v[1], 3)) for k, v in signals_15m.items()}
        }
        
        if buy_strength > sell_strength and buy_strength > buy_threshold:
            return 'BUY', min(buy_strength, 1.0), details
        
        elif sell_strength > buy_strength and sell_strength > sell_threshold:
            return 'SELL', min(sell_strength, 1.0), details
        
        return None, 0.0, details
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """Usa a mediana dos stop losses das estratégias"""
        stop_losses = []
        
        for strategy in self.strategies.values():
            try:
                sl = strategy.calculate_stop_loss(df, entry_price, side)
                stop_losses.append(float(sl))
            except Exception as e:
                logger.warning(f"Erro calculando SL: {e}")
        
        if not stop_losses:
            # Fallback: 2% de distância
            if side == 'BUY':
                return entry_price * Decimal('0.98')
            else:
                return entry_price * Decimal('1.02')
        
        # Usa mediana (mais robusto que média)
        stop_losses.sort()
        median_sl = stop_losses[len(stop_losses) // 2]
        return Decimal(str(median_sl))
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """Usa a mediana dos take profits das estratégias"""
        take_profits = []
        
        for strategy in self.strategies.values():
            try:
                tp = strategy.calculate_take_profit(df, entry_price, side)
                take_profits.append(float(tp))
            except Exception as e:
                logger.warning(f"Erro calculando TP: {e}")
        
        if not take_profits:
            # Fallback: R:R 1:1.5 (risco 2%, target 3%)
            if side == 'BUY':
                return entry_price * Decimal('1.03')
            else:
                return entry_price * Decimal('0.97')
        
        # Usa mediana
        take_profits.sort()
        median_tp = take_profits[len(take_profits) // 2]
        return Decimal(str(median_tp))