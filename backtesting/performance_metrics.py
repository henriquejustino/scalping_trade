import pandas as pd
from typing import Dict
import numpy as np

class PerformanceMetrics:
    @staticmethod
    def calculate_metrics(results: Dict) -> Dict:
        """Calcula métricas detalhadas"""
        
        df = pd.DataFrame(results['trades'])
        
        if len(df) == 0:
            return {}
        
        # Métricas por lado
        long_trades = df[df['side'] == 'BUY']
        short_trades = df[df['side'] == 'SELL']
        
        metrics = {
            'overall': {
                'total_trades': len(df),
                'win_rate': results['win_rate'],
                'profit_factor': results['profit_factor'],
                'sharpe_ratio': results['sharpe_ratio'],
                'max_drawdown': results['max_drawdown'],
                'total_return': results['total_return_pct']
            },
            'long': {
                'trades': len(long_trades),
                'win_rate': len(long_trades[long_trades['pnl'] > 0]) / len(long_trades) \
                           if len(long_trades) > 0 else 0,
                'avg_pnl': long_trades['pnl'].mean() if len(long_trades) > 0 else 0
            },
            'short': {
                'trades': len(short_trades),
                'win_rate': len(short_trades[short_trades['pnl'] > 0]) / len(short_trades) \
                           if len(short_trades) > 0 else 0,
                'avg_pnl': short_trades['pnl'].mean() if len(short_trades) > 0 else 0
            }
        }
        
        # Métricas por força de sinal
        for threshold_name, threshold in [
            ('very_strong', 0.8),
            ('strong', 0.6),
            ('medium', 0.4),
            ('weak', 0.0)
        ]:
            trades_filtered = df[df['signal_strength'] >= threshold]
            if len(trades_filtered) > 0:
                metrics[f'signal_{threshold_name}'] = {
                    'trades': len(trades_filtered),
                    'win_rate': len(trades_filtered[trades_filtered['pnl'] > 0]) / \
                               len(trades_filtered),
                    'avg_pnl': trades_filtered['pnl'].mean()
                }
        
        return metrics