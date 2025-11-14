from decimal import Decimal
from typing import Dict
import os

class Dashboard:
    """Dashboard simples para terminal"""
    
    @staticmethod
    def clear_screen():
        """Limpa tela do terminal"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def display_status(
        capital: Decimal,
        positions: list,
        performance: Dict,
        alerts: list = None
    ):
        """Exibe status do bot"""
        Dashboard.clear_screen()
        
        print("=" * 80)
        print(" " * 25 + "SCALPING BOT DASHBOARD")
        print("=" * 80)
        
        # Capital
        print(f"\n💰 CAPITAL: ${capital:,.2f}")
        
        # Posições
        print(f"\n📊 POSIÇÕES ABERTAS: {len(positions)}")
        for pos in positions:
            pnl = pos.get('pnl', 0)
            pnl_symbol = "🟢" if pnl >= 0 else "🔴"
            print(f"  {pnl_symbol} {pos['symbol']} {pos['side']} | PnL: ${pnl:.2f}")
        
        # Performance
        if performance:
            print(f"\n📈 PERFORMANCE:")
            print(f"  Total Trades: {performance.get('total_trades', 0)}")
            print(f"  Win Rate: {performance.get('win_rate', 0)*100:.2f}%")
            print(f"  PnL Total: ${performance.get('total_pnl', 0):.2f}")
        
        # Alertas
        if alerts and len(alerts) > 0:
            print(f"\n🚨 ALERTAS RECENTES:")
            for alert in alerts[-3:]:
                print(f"  - {alert['type']}: {alert['message']}")
        
        print("\n" + "=" * 80)
        print("Pressione Ctrl+C para parar")
        print("=" * 80)