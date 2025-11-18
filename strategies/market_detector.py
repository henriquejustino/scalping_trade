import pandas as pd
import numpy as np
import ta
from typing import Dict, Tuple
from loguru import logger

class MarketRegimeDetector:
    """Detecta o tipo de mercado automaticamente"""
    
    def __init__(self):
        self.regime_history = []
    
    def detect_regime(self, df_5m: pd.DataFrame, df_15m: pd.DataFrame) -> str:
        """
        Detecta regime do mercado:
        - TRENDING_UP: Tendência de alta forte
        - TRENDING_DOWN: Tendência de baixa forte
        - RANGING: Mercado lateral
        - HIGH_VOLATILITY: Alta volatilidade
        - BREAKOUT_FORMING: Formação de breakout
        """
        
        # Calcula indicadores necessários
        metrics = self._calculate_regime_metrics(df_5m, df_15m)
        
        # Classifica o regime
        regime = self._classify_regime(metrics)
        
        self.regime_history.append({
            'regime': regime,
            'metrics': metrics
        })
        
        logger.debug(f"Regime: {regime} | ADX: {metrics['adx']:.1f} | Volatility: {metrics['volatility_pct']:.2f}%")
        
        return regime
    
    def _calculate_regime_metrics(self, df_5m: pd.DataFrame, df_15m: pd.DataFrame) -> Dict:
        """Calcula métricas para classificação"""
        
        try:
            # === TENDÊNCIA (15m) ===
            ema_20_15m = ta.trend.EMAIndicator(df_15m['close'], window=20).ema_indicator()
            ema_50_15m = ta.trend.EMAIndicator(df_15m['close'], window=50).ema_indicator()
            
            trend_strength = (ema_20_15m.iloc[-1] - ema_50_15m.iloc[-1]) / ema_50_15m.iloc[-1]
            trend_consistent = (ema_20_15m.tail(10) > ema_50_15m.tail(10)).sum() / 10
            
            # === VOLATILIDADE (5m) ===
            atr_5m = ta.volatility.AverageTrueRange(
                df_5m['high'], df_5m['low'], df_5m['close'], window=14
            ).average_true_range()
            
            volatility_pct = (atr_5m.iloc[-1] / df_5m['close'].iloc[-1]) * 100
            volatility_increasing = (atr_5m.iloc[-1] > atr_5m.iloc[-5]) if len(atr_5m) > 5 else False
            
            # === ADX (Force de tendência) ===
            adx = ta.trend.ADXIndicator(
                df_15m['high'], df_15m['low'], df_15m['close'], window=14
            ).adx()
            
            adx_value = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 25
            
            # === BOLLINGER BAND WIDTH (squeeze) ===
            bb = ta.volatility.BollingerBands(df_15m['close'], window=20, window_dev=2)
            bb_width = (bb.bollinger_hband().iloc[-1] - bb.bollinger_lband().iloc[-1]) / bb.bollinger_mavg().iloc[-1]
            bb_width_ma = bb.bollinger_wband().rolling(window=20).mean().iloc[-1]
            
            # === RSI (Extremos) ===
            rsi = ta.momentum.RSIIndicator(df_15m['close'], window=14).rsi()
            rsi_value = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
            
            # === VOLUME ===
            volume_ma = df_5m['volume'].rolling(window=20).mean()
            volume_increasing = (df_5m['volume'].iloc[-5:] > volume_ma.iloc[-5:]).sum() >= 3
            
            return {
                'trend_strength': float(trend_strength),
                'trend_consistent': float(trend_consistent),
                'volatility_pct': float(volatility_pct),
                'volatility_increasing': bool(volatility_increasing),
                'adx': float(adx_value),
                'bb_width': float(bb_width),
                'bb_width_ma': float(bb_width_ma),
                'rsi': float(rsi_value),
                'volume_increasing': bool(volume_increasing)
            }
        except Exception as e:
            logger.warning(f"Erro ao calcular métricas de regime: {e}")
            return {
                'trend_strength': 0,
                'trend_consistent': 0.5,
                'volatility_pct': 1.0,
                'volatility_increasing': False,
                'adx': 25,
                'bb_width': 0.04,
                'bb_width_ma': 0.04,
                'rsi': 50,
                'volume_increasing': False
            }
    
    def _classify_regime(self, metrics: Dict) -> str:
        """Classifica o regime baseado nas métricas"""
        
        # === ALTA VOLATILIDADE ===
        if metrics['volatility_pct'] > 1.5 and metrics['volatility_increasing']:
            return 'HIGH_VOLATILITY'
        
        # === TENDÊNCIA DE ALTA FORTE ===
        if (metrics['trend_strength'] > 0.03 and 
            metrics['trend_consistent'] > 0.7 and 
            metrics['adx'] > 25):
            return 'TRENDING_UP'
        
        # === TENDÊNCIA DE BAIXA FORTE ===
        if (metrics['trend_strength'] < -0.03 and 
            metrics['trend_consistent'] < 0.3 and 
            metrics['adx'] > 25):
            return 'TRENDING_DOWN'
        
        # === FORMAÇÃO DE BREAKOUT (squeeze) ===
        if (metrics['bb_width'] < (metrics['bb_width_ma'] * 0.5) and 
            metrics['volume_increasing']):
            return 'BREAKOUT_FORMING'
        
        # === LATERAL (padrão) ===
        return 'RANGING'
    
    def get_regime_info(self) -> Dict:
        """Retorna informações do regime atual"""
        if not self.regime_history:
            return {'current_regime': 'RANGING', 'confidence': 0.5}
        
        recent = self.regime_history[-10:]
        regimes = [r['regime'] for r in recent]
        current = regimes[-1]
        
        # Calcula confiança (consistência do regime)
        consistency = regimes.count(current) / len(regimes)
        
        return {
            'current_regime': current,
            'consistency': float(consistency),
            'recent_regimes': regimes
        }
    
    def is_tradeable_regime(self, regime: str) -> bool:
        """Define se o regime é adequado para trade"""
        # Não trade em mercados muito voláteis ou em formação de breakout
        return regime in ['TRENDING_UP', 'TRENDING_DOWN', 'RANGING']