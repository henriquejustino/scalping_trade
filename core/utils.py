from decimal import Decimal, ROUND_DOWN
from typing import Optional, Tuple
import time
from loguru import logger

def round_down(value: Decimal, step: Decimal) -> Decimal:
    """Round down to nearest step size (importante para ordem precision)"""
    if step == 0:
        return value
    return (value // step) * step

def round_price(value: Decimal, tick_size: Decimal) -> Decimal:
    """Round price to tick size"""
    if tick_size == 0:
        return value
    return (value / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size

def retry_on_failure(max_retries=3, delay=1, backoff=2):
    """Decorator para retry com backoff exponencial"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        raise
                    wait_time = delay * (backoff ** attempt)
                    logger.warning(
                        f"Tentativa {attempt + 1}/{max_retries} falhou. "
                        f"Retentando em {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)
            raise last_exception
        return wrapper
    return decorator

def calculate_percentage_change(old_value: Decimal, new_value: Decimal) -> Decimal:
    """Calcula mudança percentual"""
    if old_value == 0:
        return Decimal('0')
    return ((new_value - old_value) / old_value) * Decimal('100')

def format_price(price: Decimal, decimals: int = 2) -> str:
    """Formata preço para exibição"""
    return f"${price:,.{decimals}f}"

def format_quantity(qty: Decimal, decimals: int = 6) -> str:
    """Formata quantidade"""
    return f"{qty:.{decimals}f}"

def validate_decimal(value, min_val: Optional[Decimal] = None, max_val: Optional[Decimal] = None) -> bool:
    """Valida se valor Decimal está em range"""
    value = Decimal(str(value))
    if min_val and value < min_val:
        return False
    if max_val and value > max_val:
        return False
    return True

def seconds_to_hms(seconds: int) -> str:
    """Converte segundos para HH:MM:SS"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"