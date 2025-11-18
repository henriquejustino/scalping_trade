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
        
        logger.info(f"🎯 Regime detectado: {regime}")
        logger.debug(f"   Métricas: {metrics}")
        
        return regime
    
    def _calculate_regime_metrics(self, df_5m: pd.DataFrame, df_15m: pd.DataFrame) -> Dict:
        """Calcula métricas para classificação"""
        
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
        volatility_increasing = (atr_5m.iloc[-1] > atr_5m.iloc[-5])
        
        # === LATERALIZAÇÃO (15m) ===
        # ADX para medir força de tendência
        adx = ta.trend.ADXIndicator(
            df_15m['high'], df_15m['low'], df_15m['close'], window=14
        ).adx()
        
        adx_value = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 25
        
        # Bollinger Band Width (quanto menor, mais lateral)
        bb = ta.volatility.BollingerBands(df_15m['close'], window=20, window_dev=2)
        bb_width = (bb.bollinger_hband().iloc[-1] - bb.bollinger_lband().iloc[-1]) / bb.bollinger_mavg().iloc[-1]
        
        # === FORMAÇÃO DE BREAKOUT ===
        # Range contraction (squeeze)
        recent_highs = df_15m['high'].tail(20)
        recent_lows = df_15m['low'].tail(20)
        range_contraction = (recent_highs.max() - recent_lows.min()) / df_15m['close'].iloc[-1]
        
        # Volume profile
        volume_ma = df_5m['volume'].rolling(window=20).mean()
        volume_increasing = (df_5m['volume'].iloc[-5:] > volume_ma.iloc[-5:]).sum() >= 3
        
        return {
            'trend_strength': float(trend_strength),
            'trend_consistent': float(trend_consistent),
            'volatility_pct': float(volatility_pct),
            'volatility_increasing': volatility_increasing,
            'adx': float(adx_value),
            'bb_width': float(bb_width),
            'range_contraction': float(range_contraction),
            'volume_increasing': volume_increasing
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
        
        # === FORMAÇÃO DE BREAKOUT ===
        if (metrics['range_contraction'] < 0.03 and 
            metrics['bb_width'] < 0.03 and 
            metrics['volume_increasing']):
            return 'BREAKOUT_FORMING'
        
        # === LATERAL (padrão) ===
        if metrics['adx'] < 20 or metrics['bb_width'] < 0.04:
            return 'RANGING'
        
        # === TRENDING FRACO (pode ser pullback) ===
        if abs(metrics['trend_strength']) > 0.01 and metrics['adx'] > 15:
            return 'TRENDING_UP' if metrics['trend_strength'] > 0 else 'TRENDING_DOWN'
        
        # Default
        return 'RANGING'
    
    def get_regime_summary(self) -> Dict:
        """Retorna resumo dos regimes detectados"""
        if not self.regime_history:
            return {}
        
        recent = self.regime_history[-10:]  # Últimos 10
        regime_counts = {}
        
        for entry in recent:
            regime = entry['regime']
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        return {
            'current': self.regime_history[-1]['regime'],
            'recent_distribution': regime_counts,
            'stability': max(regime_counts.values()) / len(recent)  # 0-1, quanto maior mais estável
        }