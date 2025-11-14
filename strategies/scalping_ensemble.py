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
        
        # Pesos para cada estratégia
        self.weights = {
            'rsi': 0.20,
            'ema': 0.25,
            'bb': 0.20,
            'vwap': 0.20,
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
        """
        signals_5m = {}
        signals_15m = {}
        
        # Coleta sinais do timeframe 5m
        for name, strategy in self.strategies.items():
            try:
                side, strength = strategy.get_entry_signal(df_5m)
                signals_5m[name] = (side, strength)
            except Exception as e:
                logger.warning(f"Erro em {name} (5m): {e}")
                signals_5m[name] = (None, 0.0)
        
        # Coleta sinais do timeframe 15m (confirma tendência)
        for name, strategy in self.strategies.items():
            try:
                side, strength = strategy.get_entry_signal(df_15m)
                signals_15m[name] = (side, strength)
            except Exception as e:
                logger.warning(f"Erro em {name} (15m): {e}")
                signals_15m[name] = (None, 0.0)
        
        # Calcula força ponderada dos sinais
        buy_strength = 0.0
        sell_strength = 0.0
        
        for name, weight in self.weights.items():
            side_5m, strength_5m = signals_5m[name]
            side_15m, strength_15m = signals_15m[name]
            
            # Timeframe 5m tem peso principal (70%)
            # Timeframe 15m confirma (30%)
            combined_strength = (strength_5m * 0.7) + (strength_15m * 0.3)
            
            if side_5m == 'BUY' and side_15m in ['BUY', None]:
                buy_strength += combined_strength * weight
            elif side_5m == 'SELL' and side_15m in ['SELL', None]:
                sell_strength += combined_strength * weight
        
        # Determina sinal final
        details = {
            'buy_strength': buy_strength,
            'sell_strength': sell_strength,
            'signals_5m': signals_5m,
            'signals_15m': signals_15m
        }
        
        # Threshold mínimo
        min_threshold = 0.3
        
        if buy_strength > sell_strength and buy_strength > min_threshold:
            # Confirma se 15m está alinhado
            aligned_15m = sum(
                1 for s, _ in signals_15m.values() if s == 'BUY'
            ) >= 2
            
            if aligned_15m:
                buy_strength = min(buy_strength * 1.15, 1.0)
            
            return 'BUY', buy_strength, details
        
        elif sell_strength > buy_strength and sell_strength > min_threshold:
            aligned_15m = sum(
                1 for s, _ in signals_15m.values() if s == 'SELL'
            ) >= 2
            
            if aligned_15m:
                sell_strength = min(sell_strength * 1.15, 1.0)
            
            return 'SELL', sell_strength, details
        
        return None, 0.0, details
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """Usa média dos stop loss de todas as estratégias"""
        stop_losses = []
        
        for strategy in self.strategies.values():
            try:
                sl = strategy.calculate_stop_loss(df, entry_price, side)
                stop_losses.append(sl)
            except Exception as e:
                logger.warning(f"Erro calculando SL: {e}")
        
        if not stop_losses:
            # Fallback: 1% do preço de entrada
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
        """Usa média dos take profit de todas as estratégias"""
        take_profits = []
        
        for strategy in self.strategies.values():
            try:
                tp = strategy.calculate_take_profit(df, entry_price, side)
                take_profits.append(tp)
            except Exception as e:
                logger.warning(f"Erro calculando TP: {e}")
        
        if not take_profits:
            # Fallback: 2% do preço de entrada
            if side == 'BUY':
                return entry_price * Decimal('1.02')
            else:
                return entry_price * Decimal('0.98')
        
        return sum(take_profits) / len(take_profits)

