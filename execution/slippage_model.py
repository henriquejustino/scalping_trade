"""
Slippage Model - Modelo Realista de Slippage
Problema: Usar slippage fixo 0.5% não reflete realidade
Solução: Slippage dinâmico baseado em:
- Liquidez (volume)
- Hora do dia (spread varia)
- Volatilidade (mais vol = spread maior)
- Regime de mercado
"""
from decimal import Decimal
from typing import Dict, Optional
from loguru import logger
from datetime import datetime

class SlippageModel:
    """Modelo profissional de slippage dinâmico"""
    
    def __init__(self):
        # Base spreads por horário (aplicável para cripto - são estimativas)
        self.hourly_spreads = self._initialize_hourly_spreads()
        
        # Cache de histórico de slippage real
        self.slippage_history = []
    
    def _initialize_hourly_spreads(self) -> Dict[int, Decimal]:
        """
        Spreads variam por hora do dia
        Cripto: menor durante picos de liquidez (horas de NY e London)
        """
        return {
            0: Decimal('0.008'),   # 00:00 - UTC (lower liquidity)
            1: Decimal('0.008'),
            2: Decimal('0.008'),
            3: Decimal('0.007'),
            4: Decimal('0.007'),
            5: Decimal('0.007'),
            6: Decimal('0.006'),   # 06:00 - Asian hours begin
            7: Decimal('0.006'),
            8: Decimal('0.005'),   # London open
            9: Decimal('0.004'),
            10: Decimal('0.003'),  # Peak - London + Asia overlap
            11: Decimal('0.003'),
            12: Decimal('0.003'),
            13: Decimal('0.004'),  # NY open
            14: Decimal('0.003'),
            15: Decimal('0.003'),
            16: Decimal('0.003'),  # Peak - NY + London overlap
            17: Decimal('0.004'),
            18: Decimal('0.004'),
            19: Decimal('0.005'),
            20: Decimal('0.005'),
            21: Decimal('0.006'),  # London close
            22: Decimal('0.007'),
            23: Decimal('0.008'),
        }
    
    def apply_entry_slippage(
        self,
        price: Decimal,
        side: str,
        volume_ratio = 1.0,
        regime: str = "RANGING",
        timestamp: Optional[datetime] = None
    ) -> Decimal:
        """
        Aplica slippage realista na entrada
        side='BUY': preço sobe (você paga mais)
        side='SELL': preço cai (você recebe menos)
        """
        
        try:
            price = Decimal(str(price)) if not isinstance(price, Decimal) else price
            volume_ratio = float(volume_ratio)
            
            slippage_pct = self._calculate_slippage(volume_ratio, regime, timestamp)
            
            if side == 'BUY':
                # Você paga mais na entrada
                slipped_price = price * (Decimal('1') + slippage_pct)
            else:
                # Você recebe menos na entrada de SHORT
                slipped_price = price * (Decimal('1') - slippage_pct)
            
            self._record_slippage(slippage_pct, side, "ENTRY")
            
            logger.debug(
                f"Entry slippage ({side}): {float(slippage_pct)*100:.3f}% | "
                f"${price:.2f} -> ${slipped_price:.2f}"
            )
            
            return slipped_price
        
        except Exception as e:
            logger.error(f"Erro ao aplicar entry slippage: {e}")
            return price
    
    def apply_exit_slippage(
        self,
        price: Decimal,
        side: str,
        volume_ratio = 1.0,
        regime: str = "RANGING",
        timestamp: Optional[datetime] = None
    ) -> Decimal:
        """
        Aplica slippage na saída
        side='BUY': você sai vendendo (recebe menos)
        side='SELL': você sai comprando (paga mais)
        """
        
        try:
            price = Decimal(str(price)) if not isinstance(price, Decimal) else price
            volume_ratio = float(volume_ratio)
            
            slippage_pct = self._calculate_slippage(volume_ratio, regime, timestamp)
            
            if side == 'BUY':
                # Você recebe menos ao vender
                slipped_price = price * (Decimal('1') - slippage_pct)
            else:
                # Você paga mais ao comprar para cobrir
                slipped_price = price * (Decimal('1') + slippage_pct)
            
            self._record_slippage(slippage_pct, side, "EXIT")
            
            logger.debug(
                f"Exit slippage ({side}): {float(slippage_pct)*100:.3f}% | "
                f"${price:.2f} -> ${slipped_price:.2f}"
            )
            
            return slipped_price
        
        except Exception as e:
            logger.error(f"Erro ao aplicar exit slippage: {e}")
            return price
    
    def _calculate_slippage(
        self,
        volume_ratio: float,
        regime: str,
        timestamp: Optional[datetime] = None
    ) -> Decimal:
        """
        ✅ NOVO: Calcula slippage com múltiplos fatores
        """
        
        # === 1. BASE SPREAD ===
        base_spread = self._get_hourly_spread(timestamp)
        
        # === 2. AJUSTE POR VOLUME ===
        volume_multiplier = self._get_volume_multiplier(volume_ratio)
        
        # === 3. AJUSTE POR REGIME ===
        regime_multiplier = self._get_regime_multiplier(regime)
        
        # === COMBINA FATORES ===
        slippage = base_spread * volume_multiplier * regime_multiplier
        
        # Limites razoáveis
        slippage = max(slippage, Decimal('0.001'))  # Mínimo 0.1%
        slippage = min(slippage, Decimal('0.05'))   # Máximo 5%
        
        return slippage
    
    def _get_hourly_spread(self, timestamp: Optional[datetime] = None) -> Decimal:
        """Retorna spread base por hora do dia"""
        
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        hour = timestamp.hour
        return self.hourly_spreads.get(hour, Decimal('0.005'))
    
    def _get_volume_multiplier(self, volume_ratio: float) -> Decimal:
        """
        Multiplica spread por liquidez
        Volume alto (>1.5x) = spread menor
        Volume baixo (<0.5x) = spread maior
        """
        
        if volume_ratio >= 2.0:
            return Decimal('0.7')  # Muito alta liquidez
        elif volume_ratio >= 1.5:
            return Decimal('0.8')  # Alta liquidez
        elif volume_ratio >= 1.2:
            return Decimal('0.9')  # OK
        elif volume_ratio >= 0.8:
            return Decimal('1.0')  # Normal
        elif volume_ratio >= 0.5:
            return Decimal('1.3')  # Baixa
        else:
            return Decimal('1.8')  # Muito baixa
    
    def _get_regime_multiplier(self, regime: str) -> Decimal:
        """
        Spread varia por regime de mercado
        Breakout = spread maior (incerteza)
        Trending = spread normal (momentum)
        Ranging = spread menor (padrão)
        """
        
        multipliers = {
            'TRENDING_UP': Decimal('1.0'),
            'TRENDING_DOWN': Decimal('1.0'),
            'RANGING': Decimal('0.9'),
            'HIGH_VOLATILITY': Decimal('1.5'),
            'BREAKOUT_FORMING': Decimal('1.4')
        }
        
        return multipliers.get(regime, Decimal('1.0'))
    
    def _record_slippage(self, slippage_pct: Decimal, side: str, type_: str):
        """Registra slippage para análise posterior"""
        self.slippage_history.append({
            'timestamp': datetime.utcnow(),
            'slippage_pct': float(slippage_pct),
            'side': side,
            'type': type_
        })
    
    def get_average_slippage(self, period: int = 100) -> Dict:
        """
        Retorna slippage médio dos últimos N trades
        Útil para validar se modelo está calibrado
        """
        
        if not self.slippage_history:
            return {'avg': 0, 'count': 0}
        
        recent = self.slippage_history[-period:]
        avg = sum(t['slippage_pct'] for t in recent) / len(recent)
        
        buy_avg = sum(
            t['slippage_pct'] for t in recent if t['side'] == 'BUY'
        ) / len([t for t in recent if t['side'] == 'BUY']) if any(t['side'] == 'BUY' for t in recent) else 0
        
        sell_avg = sum(
            t['slippage_pct'] for t in recent if t['side'] == 'SELL'
        ) / len([t for t in recent if t['side'] == 'SELL']) if any(t['side'] == 'SELL' for t in recent) else 0
        
        return {
            'average_pct': float(avg),
            'buy_avg_pct': float(buy_avg),
            'sell_avg_pct': float(sell_avg),
            'entry_count': len([t for t in recent if t['type'] == 'ENTRY']),
            'exit_count': len([t for t in recent if t['type'] == 'EXIT']),
            'total_count': len(recent)
        }
    
    def calibrate_from_real_data(self, real_slippages: list):
        """
        ✅ NOVO: Calibra modelo com dados reais de slippage
        Permite ajustar modelo conforme aprende sobre mercado real
        """
        
        if not real_slippages:
            return
        
        avg_real_slippage = sum(real_slippages) / len(real_slippages)
        
        logger.info(
            f"Calibrando model de slippage com dados reais: "
            f"avg={avg_real_slippage:.4f} ({len(real_slippages)} amostras)"
        )
        
        # Ajusta spreads horárias se necessário
        # TODO: Implementar lógica de ajuste adaptativo
    
    def validate_slippage_assumption(self, expected_pct: Decimal, actual_pct: Decimal) -> bool:
        """
        Valida se slippage real está próximo do esperado
        Se desviar muito, indica modelo descalibrado
        """
        
        deviation = abs(actual_pct - expected_pct) / expected_pct if expected_pct > 0 else 0
        
        if deviation > Decimal('0.5'):  # 50% desvio
            logger.warning(
                f"Slippage deviation: expected {expected_pct:.4f}, "
                f"actual {actual_pct:.4f} ({float(deviation)*100:.1f}%)"
            )
            return False
        
        return True