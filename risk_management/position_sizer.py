from decimal import Decimal
from typing import Optional, Dict, Tuple
from loguru import logger
from config.settings import settings
from core.utils import round_down

class PositionSizerV2:
    """Dimensionador de posição robusto e adaptativo"""
    
    def __init__(self):
        self.settings = settings
        self.trade_history = []
    
    def calculate_dynamic_position_size(
        self,
        capital: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        symbol_filters: dict,
        signal_strength: float,
        volume_ratio: float = 1.0,
        regime: str = "RANGING"
    ) -> Optional[Decimal]:
        """
        Calcula tamanho da posição com múltiplos fatores:
        - Risco dinâmico baseado em força de sinal
        - Ajuste de risco por volume (não rejeição!)
        - Limite por regime de mercado
        - Validações rigorosas
        
        ✅ CORRIGIDO: Conversão segura de tipos
        """
        
        try:
            # === 1. CONVERSÃO SEGURA DE TIPOS ===
            capital = Decimal(str(capital)) if not isinstance(capital, Decimal) else capital
            entry_price = Decimal(str(entry_price)) if not isinstance(entry_price, Decimal) else entry_price
            stop_loss_price = Decimal(str(stop_loss_price)) if not isinstance(stop_loss_price, Decimal) else stop_loss_price
            signal_strength = float(signal_strength)
            volume_ratio = float(volume_ratio)
            
            # === 2. VALIDAÇÃO BÁSICA ===
            if capital <= Decimal('0') or entry_price <= Decimal('0') or stop_loss_price == entry_price:
                logger.error(f"Parâmetros inválidos: capital={capital}, entry={entry_price}, sl={stop_loss_price}")
                return None
            
            # === 3. RISCO DINÂMICO POR FORÇA DE SINAL ===
            risk_multiplier = self._get_risk_multiplier(signal_strength, volume_ratio, regime)
            
            # Multiplica risco base por multiplicador
            base_risk = Decimal(str(float(settings.BASE_RISK_PER_TRADE)))
            dynamic_risk = base_risk * risk_multiplier
            
            # Limita ao máximo e mínimo
            max_risk = Decimal(str(float(settings.MAX_RISK_PER_TRADE)))
            min_risk = Decimal(str(float(settings.MIN_RISK_PER_TRADE)))
            
            dynamic_risk = min(dynamic_risk, max_risk)
            dynamic_risk = max(dynamic_risk, min_risk)
            
            logger.debug(
                f"Risco dinâmico: {float(dynamic_risk)*100:.2f}% "
                f"(força={signal_strength:.2f}, vol={volume_ratio:.2f}, regime={regime})"
            )
            
            # === 4. CALCULA POSIÇÃO ===
            stop_loss_distance = abs(entry_price - stop_loss_price)
            
            # Risco em dólares
            risk_amount = capital * dynamic_risk
            
            # Quantidade = Risco em $ / Distância do SL em $
            position_size_usd = risk_amount / stop_loss_distance
            quantity = position_size_usd / entry_price
            
            # === 5. ARREDONDA PARA STEP SIZE ===
            step_size = Decimal(str(symbol_filters.get('stepSize', Decimal('0.001'))))
            quantity = round_down(quantity, step_size)
            
            min_qty = Decimal(str(symbol_filters.get('minQty', Decimal('0.001'))))
            if quantity < min_qty:
                logger.debug(
                    f"Quantidade {quantity} abaixo do mínimo {min_qty}"
                )
                return None
            
            # === 6. VALIDA NOTIONAL ===
            min_notional = Decimal(str(symbol_filters.get('minNotional', Decimal('5.0'))))
            notional = quantity * entry_price
            if notional < min_notional:
                logger.debug(
                    f"Notional {notional} abaixo do mínimo {min_notional}"
                )
                return None
            
            # === 7. LIMITES DE POSIÇÃO ===
            min_pos = Decimal(str(settings.MIN_POSITION_SIZE_USD))
            max_pos = Decimal(str(settings.MAX_POSITION_SIZE_USD))
            
            position_value = quantity * entry_price
            
            if position_value < min_pos:
                logger.debug(
                    f"Valor ${float(position_value):.2f} abaixo do mínimo ${float(min_pos):.2f}"
                )
                return None
            
            if position_value > max_pos:
                max_quantity = max_pos / entry_price
                quantity = round_down(max_quantity, step_size)
                logger.info(f"Posição ajustada ao máximo: {quantity}")
            
            # === 8. LOG ===
            logger.info(
                f"✅ Posição calculada:\n"
                f"   Quantidade: {quantity:.6f}\n"
                f"   Valor: ${float(position_value):.2f}\n"
                f"   Risco: {float(dynamic_risk)*100:.2f}%\n"
                f"   Volume Ratio: {volume_ratio:.2f}x"
            )
            
            return quantity
        
        except Exception as e:
            logger.error(f"❌ Erro ao calcular posição: {e}", exc_info=True)
            return None
    
    def _get_risk_multiplier(
        self,
        signal_strength: float,
        volume_ratio: float,
        regime: str
    ) -> Decimal:
        """
        ✅ CORRIGIDO: Calcula multiplicador de risco dinâmico
        Baseado em 3 fatores: força de sinal, volume, regime
        Retorna sempre Decimal
        """
        
        try:
            base_multiplier = Decimal('1.0')
            
            # === AJUSTE POR FORÇA DE SINAL ===
            signal_strength = float(signal_strength)
            
            if signal_strength >= 0.8:
                base_multiplier = base_multiplier * Decimal('1.5')
                logger.debug(f"Bônus sinal MUITO FORTE: x1.5")
            elif signal_strength >= 0.6:
                base_multiplier = base_multiplier * Decimal('1.25')
                logger.debug(f"Bônus sinal FORTE: x1.25")
            elif signal_strength >= 0.4:
                base_multiplier = base_multiplier * Decimal('1.0')
            else:
                base_multiplier = base_multiplier * Decimal('0.75')
                logger.debug(f"Penalidade sinal FRACO: x0.75")
            
            # === AJUSTE POR VOLUME ===
            volume_ratio = float(volume_ratio)
            
            if volume_ratio >= 1.5:
                base_multiplier = base_multiplier * Decimal('1.15')
                logger.debug(f"Bônus volume alto: x1.15")
            elif volume_ratio >= 1.2:
                base_multiplier = base_multiplier * Decimal('1.1')
            elif volume_ratio >= 0.8:
                base_multiplier = base_multiplier * Decimal('1.0')
            elif volume_ratio >= 0.5:
                base_multiplier = base_multiplier * Decimal('0.8')
                logger.debug(f"Penalidade volume baixo: x0.8")
            else:
                base_multiplier = base_multiplier * Decimal('0.6')
                logger.debug(f"Penalidade volume muito baixo: x0.6")
            
            # === AJUSTE POR REGIME ===
            if regime in ["TRENDING_UP", "TRENDING_DOWN"]:
                base_multiplier = base_multiplier * Decimal('1.1')
                logger.debug(f"Bônus em tendência: x1.1")
            elif regime == "HIGH_VOLATILITY":
                base_multiplier = base_multiplier * Decimal('0.8')
                logger.debug(f"Penalidade alta volatilidade: x0.8")
            elif regime == "BREAKOUT_FORMING":
                base_multiplier = base_multiplier * Decimal('0.7')
                logger.debug(f"Penalidade breakout forming: x0.7")
            
            return base_multiplier
        
        except Exception as e:
            logger.error(f"Erro ao calcular multiplicador: {e}")
            return Decimal('1.0')
    
    def validate_position_size(
        self,
        quantity: Decimal,
        entry_price: Decimal,
        symbol_filters: dict
    ) -> Tuple[bool, str]:
        """Valida se posição está dentro de limites"""
        
        try:
            quantity = Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity
            entry_price = Decimal(str(entry_price)) if not isinstance(entry_price, Decimal) else entry_price
            
            min_qty = Decimal(str(symbol_filters.get('minQty', Decimal('0.001'))))
            if quantity < min_qty:
                return False, f"Quantidade {quantity} < mínimo {min_qty}"
            
            min_notional = Decimal(str(symbol_filters.get('minNotional', Decimal('5.0'))))
            notional = quantity * entry_price
            if notional < min_notional:
                return False, f"Notional {notional} < mínimo {min_notional}"
            
            min_pos = Decimal(str(settings.MIN_POSITION_SIZE_USD))
            max_pos = Decimal(str(settings.MAX_POSITION_SIZE_USD))
            position_value = quantity * entry_price
            
            if position_value < min_pos:
                return False, f"Valor ${float(position_value)} < mínimo ${float(min_pos)}"
            
            if position_value > max_pos:
                return False, f"Valor ${float(position_value)} > máximo ${float(max_pos)}"
            
            return True, "OK"
        
        except Exception as e:
            logger.error(f"Erro ao validar: {e}")
            return False, str(e)
    
    def calculate_kelly_position_size(
        self,
        capital: Decimal,
        win_rate: float,
        avg_win: Decimal,
        avg_loss: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal
    ) -> Optional[Decimal]:
        """
        Calcula posição usando Critério de Kelly
        Kelly % = (win_rate * avg_win - loss_rate * avg_loss) / avg_win
        """
        
        try:
            if win_rate <= 0 or win_rate >= 1:
                return None
            
            loss_rate = 1 - win_rate
            
            avg_win = Decimal(str(avg_win)) if not isinstance(avg_win, Decimal) else avg_win
            avg_loss = Decimal(str(avg_loss)) if not isinstance(avg_loss, Decimal) else avg_loss
            
            avg_win_abs = abs(avg_win)
            avg_loss_abs = abs(avg_loss)
            
            if avg_loss_abs == Decimal('0'):
                return None
            
            wl_ratio = avg_win_abs / avg_loss_abs
            
            kelly_pct = (Decimal(str(win_rate)) * wl_ratio - Decimal(str(loss_rate))) / wl_ratio
            
            kelly_pct = min(kelly_pct, Decimal('0.25'))
            kelly_pct = max(kelly_pct, Decimal('0.01'))
            
            sl_distance = abs(entry_price - stop_loss)
            quantity = (kelly_pct * capital) / (entry_price * sl_distance)
            
            logger.info(
                f"Kelly Position: {kelly_pct:.4f} Kelly = "
                f"{quantity:.6f} lots (w.rate={win_rate:.2%})"
            )
            
            return quantity
        
        except Exception as e:
            logger.error(f"Erro ao calcular Kelly: {e}")
            return None
    
    def calculate_volatility_adjusted_size(
        self,
        quantity: Decimal,
        atr: Decimal,
        atr_historical_avg: Decimal
    ) -> Decimal:
        """
        Ajusta posição por volatilidade
        High volatility = menor posição
        Low volatility = maior posição
        """
        
        try:
            quantity = Decimal(str(quantity)) if not isinstance(quantity, Decimal) else quantity
            atr = Decimal(str(atr)) if not isinstance(atr, Decimal) else atr
            atr_historical_avg = Decimal(str(atr_historical_avg)) if not isinstance(atr_historical_avg, Decimal) else atr_historical_avg
            
            if atr_historical_avg == Decimal('0'):
                return quantity
            
            volatility_ratio = atr / atr_historical_avg
            
            if volatility_ratio > Decimal('2.0'):
                adjusted = quantity * Decimal('0.6')
                logger.info(f"Posição reduzida por volatilidade: {volatility_ratio:.2f}x")
            elif volatility_ratio > Decimal('1.5'):
                adjusted = quantity * Decimal('0.8')
            elif volatility_ratio < Decimal('0.5'):
                adjusted = quantity * Decimal('1.2')
            else:
                adjusted = quantity
            
            return adjusted
        
        except Exception as e:
            logger.error(f"Erro ao ajustar por volatilidade: {e}")
            return quantity