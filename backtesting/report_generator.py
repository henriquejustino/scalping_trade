from typing import Dict
import json
from datetime import datetime
from loguru import logger

class ReportGenerator:
    """Gera relatórios detalhados de backtest"""
    
    @staticmethod
    def generate_html_report(results: Dict, output_file: str = None):
        """Gera relatório HTML"""
        
        if output_file is None:
            output_file = f"data/backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        .metric {{ display: inline-block; margin: 10px; padding: 15px; background: #ecf0f1; border-radius: 5px; }}
        .metric-label {{ font-size: 12px; color: #7f8c8d; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .positive {{ color: #27ae60; }}
        .negative {{ color: #e74c3c; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #3498db; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Backtest Report</h1>
        
        <div class="metric">
            <div class="metric-label">Total Return</div>
            <div class="metric-value {'positive' if results['total_return_pct'] > 0 else 'negative'}">
                {results['total_return_pct']:.2f}%
            </div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Win Rate</div>
            <div class="metric-value">
                {results['win_rate']*100:.2f}%
            </div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Sharpe Ratio</div>
            <div class="metric-value">
                {results['sharpe_ratio']:.2f}
            </div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Max Drawdown</div>
            <div class="metric-value negative">
                {results['max_drawdown']*100:.2f}%
            </div>
        </div>
        
        <div class="metric">
            <div class="metric-label">Profit Factor</div>
            <div class="metric-value">
                {results['profit_factor']:.2f}
            </div>
        </div>
        
        <h2>📈 Performance Summary</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Trades</td>
                <td>{results['total_trades']}</td>
            </tr>
            <tr>
                <td>Winning Trades</td>
                <td>{results['winning_trades']}</td>
            </tr>
            <tr>
                <td>Losing Trades</td>
                <td>{results['losing_trades']}</td>
            </tr>
            <tr>
                <td>Initial Capital</td>
                <td>${results['initial_capital']:.2f}</td>
            </tr>
            <tr>
                <td>Final Capital</td>
                <td>${results['final_capital']:.2f}</td>
            </tr>
            <tr>
                <td>Total PnL</td>
                <td class="{'positive' if results['total_pnl'] > 0 else 'negative'}">${results['total_pnl']:.2f}</td>
            </tr>
            <tr>
                <td>Average Win</td>
                <td class="positive">${results['avg_win']:.2f}</td>
            </tr>
            <tr>
                <td>Average Loss</td>
                <td class="negative">${results['avg_loss']:.2f}</td>
            </tr>
        </table>
        
        <h2>📋 Recent Trades</h2>
        <table>
            <tr>
                <th>Entry Time</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Entry Price</th>
                <th>Exit Price</th>
                <th>PnL</th>
                <th>PnL %</th>
            </tr>
"""
        
        for trade in results['trades'][-20:]:
            pnl_class = 'positive' if trade['pnl'] > 0 else 'negative'
            html += f"""
            <tr>
                <td>{trade['entry_time']}</td>
                <td>{trade['symbol']}</td>
                <td>{trade['side']}</td>
                <td>${trade['entry_price']:.2f}</td>
                <td>${trade['exit_price']:.2f}</td>
                <td class="{pnl_class}">${trade['pnl']:.2f}</td>
                <td class="{pnl_class}">{trade['pnl_pct']:.2f}%</td>
            </tr>
"""
        
        html += """
        </table>
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w') as f:
            f.write(html)
        
        logger.info(f"Relatório HTML gerado: {output_file}")
    
    @staticmethod
    def generate_csv_trades(results: Dict, output_file: str = None):
        """Exporta trades para CSV"""
        import pandas as pd
        
        if output_file is None:
            output_file = f"data/trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        df = pd.DataFrame(results['trades'])
        df.to_csv(output_file, index=False)
        
        logger.info(f"Trades exportados para: {output_file}")