import requests
import pandas as pd
import numpy as np
import talib
import time
from datetime import datetime
import warnings
import json
warnings.filterwarnings('ignore')

# ============= НАСТРОЙКИ TELEGRAM =============
TELEGRAM_TOKEN = "7771648854:AAG1MUCXvuzlOmAjATjAg7wnNNmm7W7g-4I"
TELEGRAM_CHAT_ID = "1728685821"

# ============= НАСТРОЙКИ СТРАТЕГИИ =============
LEADING_INDICATOR = "B-Xtrender"
CONFIRMATION_INDICATORS = {
    "Range Filter": True,
    "Waddah Attar Explosion": True
}

# ============= ВСЕ ВАШИ МОНЕТЫ =============
SYMBOLS = [
    # Основные (проверенные)
    "BTC-USDT",      # Bitcoin
    "ETH-USDT",      # Ethereum
    "BNB-USDT",      # Binance Coin
    
    # Ваши монеты
    "RIVER-USDT",    # RIVER
    "AXS-USDT",      # Axie Infinity
    "DUSK-USDT",     # Dusk Network
    
    # Альтернативные форматы (на случай проблем)
    "BTCUSDT",
    "ETHUSDT", 
    "BNBUSDT",
    "RIVERUSDT",
    "AXSUSDT",
    "DUSKUSDT"
]

# Рабочие пары (будут определены автоматически)
WORKING_SYMBOLS = []

TIMEFRAME = "5m"    # 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
CHECK_INTERVAL = 300   # Проверка каждые 30 секунд

# ============= API ФУНКЦИИ =============
def test_symbol(symbol):
    """Тестирует, доступен ли символ на биржах"""
    print(f"\n🔍 Тестируем {symbol}...")
    
    # Пробуем разные форматы
    symbol_formats = [
        symbol,                     # Как есть
        symbol.replace("-", ""),    # Без дефиса
        symbol.replace("-USDT", "USDT") if "-USDT" in symbol else symbol,
    ]
    
    for sym_format in symbol_formats:
        # Пробуем BingX
        bingx_data = try_bingx_api(sym_format, "15m", 2)
        if bingx_data is not None:
            price = bingx_data['close'].iloc[-1] if len(bingx_data) > 0 else 0
            print(f"  ✅ BingX: {sym_format} - цена: {price:.4f}")
            return sym_format, "BingX"
        
        # Пробуем Binance
        binance_data = try_binance_api(sym_format, "15m", 2)
        if binance_data is not None:
            price = binance_data['close'].iloc[-1] if len(binance_data) > 0 else 0
            print(f"  ✅ Binance: {sym_format} - цена: {price:.4f}")
            return sym_format, "Binance"
    
    print(f"  ❌ Не доступен на биржах")
    return None, None

def try_bingx_api(symbol, interval, limit=2):
    """Пробует получить данные с BingX"""
    endpoints = [
        "https://open-api.bingx.com/openApi/swap/v2/quote/klines",
        "https://open-api.bingx.com/openApi/swap/v3/quote/klines",
        "https://open-api.bingx.com/openApi/spot/v1/market/kline",
        "https://open-api.bingx.com/openApi/spot/v2/market/kline",
    ]
    
    for url in endpoints:
        try:
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and data['data']:
                    return parse_candle_data(data['data'])
        except:
            continue
    
    return None

def try_binance_api(symbol, interval, limit=2):
    """Пробует получить данные с Binance"""
    try:
        # Убираем дефис для Binance
        binance_symbol = symbol.replace("-", "")
        
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": binance_symbol,
            "interval": interval,
            "limit": limit
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return parse_candle_data(data)
    except:
        pass
    
    return None

def parse_candle_data(candles):
    """Парсит данные свечей в DataFrame"""
    try:
        if not candles or len(candles) == 0:
            return None
        
        # Определяем формат данных
        first_item = candles[0]
        
        if isinstance(first_item, list) and len(first_item) >= 6:
            # Формат: [timestamp, open, high, low, close, volume, ...]
            df = pd.DataFrame(candles, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume'
            ][:len(first_item)])
        
        elif isinstance(first_item, dict):
            # Формат словаря
            df = pd.DataFrame(candles)
            
            # Маппинг колонок
            column_map = {}
            for col in df.columns:
                col_lower = col.lower()
                if 'open' in col_lower and 'time' not in col_lower:
                    column_map[col] = 'open'
                elif 'high' in col_lower:
                    column_map[col] = 'high'
                elif 'low' in col_lower:
                    column_map[col] = 'low'
                elif 'close' in col_lower:
                    column_map[col] = 'close'
                elif 'volume' in col_lower:
                    column_map[col] = 'volume'
                elif 'time' in col_lower or 'timestamp' in col_lower:
                    column_map[col] = 'timestamp'
            
            df = df.rename(columns=column_map)
        
        else:
            return None
        
        # Конвертация типов
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Удаляем пустые строки
        df = df.dropna()
        
        if len(df) == 0:
            return None
        
        return df
        
    except Exception as e:
        print(f"  ⚠️ Ошибка парсинга: {str(e)[:50]}")
        return None

def get_market_data(symbol_info):
    """Получает данные для символа"""
    symbol, exchange = symbol_info
    
    try:
        if exchange == "BingX":
            data = try_bingx_api(symbol, TIMEFRAME, 100)
        else:  # Binance
            data = try_binance_api(symbol, TIMEFRAME, 100)
        
        if data is not None and len(data) >= 30:
            return data
        else:
            return None
            
    except Exception as e:
        print(f"  ⚠️ Ошибка получения данных для {symbol}: {str(e)[:50]}")
        return None

# ============= ИНДИКАТОРЫ =============
def calculate_rsi(close_prices, period=14):
    """Расчет RSI"""
    delta = close_prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_b_xtrender(df):
    """B-Xtrender индикатор"""
    try:
        if len(df) < 50:
            return False, False
        
        close = df['close']
        
        # Параметры
        fast_period = 5
        slow_period = 20
        rsi_period = 14
        
        # EMA
        ema_fast = talib.EMA(close, fast_period)
        ema_slow = talib.EMA(close, slow_period)
        
        # Разница EMAs
        ema_diff = ema_fast - ema_slow
        
        # RSI от разницы EMAs
        rsi_ema = calculate_rsi(ema_diff, rsi_period)
        
        # RSI от цены
        rsi_price = calculate_rsi(close, rsi_period)
        
        # Текущие значения
        rsi_ema_curr = rsi_ema.iloc[-1] if not pd.isna(rsi_ema.iloc[-1]) else 50
        rsi_ema_prev = rsi_ema.iloc[-2] if not pd.isna(rsi_ema.iloc[-2]) else 50
        rsi_price_curr = rsi_price.iloc[-1] if not pd.isna(rsi_price.iloc[-1]) else 50
        
        # EMA направления
        ema_fast_curr = ema_fast.iloc[-1] if not pd.isna(ema_fast.iloc[-1]) else 0
        ema_slow_curr = ema_slow.iloc[-1] if not pd.isna(ema_slow.iloc[-1]) else 0
        ema_fast_dir = ema_fast_curr > ema_fast.iloc[-2] if len(ema_fast) > 1 else False
        
        # Сигналы
        long_signal = (
            rsi_ema_curr > 50 and              # RSI EMA > 50
            rsi_ema_curr > rsi_ema_prev and    # RSI EMA растет
            rsi_price_curr > 50 and            # RSI цены > 50
            ema_fast_curr > ema_slow_curr and  # Быстрая EMA > медленной
            ema_fast_dir                       # Быстрая EMA растет
        )
        
        short_signal = (
            rsi_ema_curr < 50 and              # RSI EMA < 50
            rsi_ema_curr < rsi_ema_prev and    # RSI EMA падает
            rsi_price_curr < 50 and            # RSI цены < 50
            ema_fast_curr < ema_slow_curr and  # Быстрая EMA < медленной
            not ema_fast_dir                   # Быстрая EMA падает
        )
        
        return bool(long_signal), bool(short_signal)
        
    except Exception as e:
        print(f"  ⚠️ Ошибка B-Xtrender: {str(e)[:50]}")
        return False, False

def calculate_range_filter(df):
    """Range Filter индикатор"""
    try:
        if len(df) < 30:
            return False, False
        
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Параметры
        period = 20
        multiplier = 2.0
        
        # ATR для волатильности
        atr = talib.ATR(high, low, close, period)
        
        # Скользящая средняя
        sma = talib.SMA(close, period)
        
        # Текущие значения
        current_close = close.iloc[-1]
        current_atr = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0
        current_sma = sma.iloc[-1] if not pd.isna(sma.iloc[-1]) else 0
        
        # Верхняя и нижняя границы
        upper_band = current_sma + (current_atr * multiplier)
        lower_band = current_sma - (current_atr * multiplier)
        
        # Сигналы
        long_signal = current_close > upper_band
        short_signal = current_close < lower_band
        
        return bool(long_signal), bool(short_signal)
        
    except Exception as e:
        print(f"  ⚠️ Ошибка Range Filter: {str(e)[:50]}")
        return False, False

def calculate_waddah_attar(df):
    """Waddah Attar Explosion индикатор"""
    try:
        if len(df) < 50:
            return False, False
        
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Параметры
        fast_period = 20
        slow_period = 40
        bb_period = 20
        bb_std = 2.0
        sensitivity = 150
        
        # MACD
        macd, signal, hist = talib.MACD(close, 
                                       fastperiod=fast_period,
                                       slowperiod=slow_period,
                                       signalperiod=9)
        
        # Разница MACD
        macd_diff = macd - macd.shift(1)
        macd_trend = macd_diff * sensitivity
        
        # Bollinger Bands
        bb_middle = talib.SMA(close, bb_period)
        bb_stddev = talib.STDDEV(close, bb_period)
        bb_upper = bb_middle + (bb_stddev * bb_std)
        bb_lower = bb_middle - (bb_stddev * bb_std)
        bb_width = bb_upper - bb_lower
        
        # Deadzone (ATR)
        deadzone = talib.ATR(high, low, close, 100) * 3.7
        
        # Текущие значения
        macd_trend_curr = macd_trend.iloc[-1] if not pd.isna(macd_trend.iloc[-1]) else 0
        bb_width_curr = bb_width.iloc[-1] if not pd.isna(bb_width.iloc[-1]) else 0
        deadzone_curr = deadzone.iloc[-1] if not pd.isna(deadzone.iloc[-1]) else 0
        
        # Сигналы
        long_signal = (
            macd_trend_curr > 0 and                    # Тренд вверх
            abs(macd_trend_curr) > bb_width_curr and   # Сила > ширина BB
            bb_width_curr > deadzone_curr and          # Ширина > deadzone
            abs(macd_trend_curr) > deadzone_curr       # Сила > deadzone
        )
        
        short_signal = (
            macd_trend_curr < 0 and                    # Тренд вниз
            abs(macd_trend_curr) > bb_width_curr and   # Сила > ширина BB
            bb_width_curr > deadzone_curr and          # Ширина > deadzone
            abs(macd_trend_curr) > deadzone_curr       # Сила > deadzone
        )
        
        return bool(long_signal), bool(short_signal)
        
    except Exception as e:
        print(f"  ⚠️ Ошибка Waddah Attar: {str(e)[:50]}")
        return False, False

# ============= TELEGRAM ФУНКЦИИ =============
def send_telegram_message(message):
    """Отправка сообщения в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True
        else:
            print(f"  ❌ Telegram ошибка: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Ошибка отправки Telegram: {str(e)[:50]}")
        return False

# ============= МОНИТОРИНГ ПАРЫ =============
def monitor_symbol(symbol_info):
    """Мониторинг одной пары"""
    symbol, exchange = symbol_info
    
    try:
        print(f"\n📊 {symbol} ({exchange})...")
        
        # Получаем данные
        df = get_market_data((symbol, exchange))
        
        if df is None or len(df) < 30:
            print(f"  ❌ Нет данных")
            return None, None, None
        
        # Рассчитываем индикаторы
        bx_long, bx_short = calculate_b_xtrender(df)
        rf_long, rf_short = calculate_range_filter(df)
        wae_long, wae_short = calculate_waddah_attar(df)
        
        # Текущая цена
        current_price = df['close'].iloc[-1]
        price_change = ((current_price / df['close'].iloc[-2]) - 1) * 100
        
        # Логи
        print(f"  💰 Цена: {current_price:.4f} ({price_change:+.2f}%)")
        print(f"  🔷 B-Xtrender: {'LONG' if bx_long else 'short' if bx_short else '—'}")
        print(f"  🔶 Range Filter: {'LONG' if rf_long else 'SHORT' if rf_short else '—'}")
        print(f"  🎯 Waddah Attar: {'LONG' if wae_long else 'SHORT' if wae_short else '—'}")
        
        # Формируем финальные сигналы
        long_signal = bx_long
        short_signal = bx_short
        
        if CONFIRMATION_INDICATORS["Range Filter"]:
            long_signal = long_signal and rf_long
            short_signal = short_signal and rf_short
        
        if CONFIRMATION_INDICATORS["Waddah Attar Explosion"]:
            long_signal = long_signal and wae_long
            short_signal = short_signal and wae_short
        
        if long_signal:
            print(f"  ✅ СИГНАЛ: LONG!")
        elif short_signal:
            print(f"  ✅ СИГНАЛ: SHORTS!")
        else:
            print(f"  ⏸️  Нет сигнала")
        
        return long_signal, short_signal, current_price
        
    except Exception as e:
        print(f"  ⚠️ Ошибка: {str(e)[:100]}")
        return None, None, None

# ============= ИНИЦИАЛИЗАЦИЯ =============
def initialize_symbols():
    """Определяет рабочие пары"""
    print("\n" + "="*70)
    print("🔍 ПОИСК РАБОЧИХ ПАР НА БИРЖАХ")
    print("="*70)
    
    working_pairs = []
    
    # Уникальные пары (без дубликатов)
    unique_symbols = []
    for symbol in SYMBOLS:
        base_symbol = symbol.replace("-USDT", "").replace("USDT", "")
        if base_symbol not in [s[0].replace("-USDT", "").replace("USDT", "") for s in working_pairs]:
            unique_symbols.append(symbol)
    
    for symbol in unique_symbols[:8]:  # Проверяем до 8 уникальных пар
        found_symbol, exchange = test_symbol(symbol)
        if found_symbol and exchange:
            working_pairs.append((found_symbol, exchange))
            print(f"  ✅ Добавлена: {found_symbol} с {exchange}")
    
    print(f"\n📋 Найдено рабочих пар: {len(working_pairs)}")
    
    if len(working_pairs) == 0:
        print("❌ Не найдено ни одной рабочей пары!")
        print("   Проверьте интернет-соединение и доступность бирж")
        return None
    
    return working_pairs

# ============= ГЛАВНЫЙ ЦИКЛ =============
def main_monitoring_loop(working_symbols):
    """Главный цикл мониторинга"""
    print("\n" + "="*70)
    print("🚀 ЗАПУСК МОНИТОРИНГА ТОРГОВЫХ СИГНАЛОВ")
    print("="*70)
    
    # Информация о парах
    print("\n📊 МОНИТОРИМ ПАРЫ:")
    for symbol, exchange in working_symbols:
        display_name = symbol.replace("-USDT", "").replace("USDT", "")
        print(f"   • {display_name:8} на {exchange}")
    
    print(f"\n🎯 СТРАТЕГИЯ: {LEADING_INDICATOR}")
    print(f"✅ ПОДТВЕРЖДЕНИЯ: {', '.join([k for k, v in CONFIRMATION_INDICATORS.items() if v])}")
    print(f"⏰ ТАЙМФРЕЙМ: {TIMEFRAME}")
    print(f"🔁 ИНТЕРВАЛ: {CHECK_INTERVAL} сек")
    print("="*70)
    
    # Тестовое сообщение
    pairs_list = ", ".join([s[0].replace("-USDT", "").replace("USDT", "") for s in working_symbols])
    test_msg = (
        f"<b>🤖 Торговый бот запущен!</b>\n\n"
        f"<i>Пары ({len(working_symbols)}):</i> {pairs_list}\n"
        f"<i>Стратегия:</i> {LEADING_INDICATOR}\n"
        f"<i>Таймфрейм:</i> {TIMEFRAME}\n"
        f"<i>Время:</i> {datetime.now().strftime('%H:%M:%S')}"
    )
    send_telegram_message(test_msg)
    
    # Хранилище сигналов
    previous_signals = {symbol: {'long': False, 'shorts': False} for symbol, _ in working_symbols}
    stats = {'checks': 0, 'signals_sent': 0, 'start_time': datetime.now()}
    
    print("\n🎯 НАЧАЛО МОНИТОРИНГА...")
    print("   (Нажмите Ctrl+C для остановки)")
    
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            stats['checks'] += 1
            
            print(f"\n⏳ [{current_time}] Проверка #{stats['checks']}")
            print("-" * 60)
            
            for symbol_info in working_symbols:
                symbol, exchange = symbol_info
                long_signal, short_signal, price = monitor_symbol(symbol_info)
                
                if long_signal is None:
                    continue
                
                display_name = symbol.replace("-USDT", "").replace("USDT", "")
                
                # Обработка LONG сигнала
                if long_signal and not previous_signals[symbol]['long']:
                    message = (
                        f"<b>🚨 LONG СИГНАЛ</b>\n\n"
                        f"<b>Пара:</b> {display_name}\n"
                        f"<b>Биржа:</b> {exchange}\n"
                        f"<b>Цена:</b> {price:.4f}\n"
                        f"<b>Таймфрейм:</b> {TIMEFRAME}\n"
                        f"<b>Время:</b> {current_time}\n\n"
                        f"<i>Стратегия: {LEADING_INDICATOR}</i>\n"
                        f"<i>Подтверждения: ✅</i>"
                    )
                    
                    if send_telegram_message(message):
                        print(f"  📨 Отправлен LONG для {display_name}")
                        previous_signals[symbol]['long'] = True
                        previous_signals[symbol]['shorts'] = False
                        stats['signals_sent'] += 1
                
                # Обработка SHORT сигнала
                elif short_signal and not previous_signals[symbol]['shorts']:
                    message = (
                        f"<b>🚨 SHORTS СИГНАЛ</b>\n\n"
                        f"<b>Пара:</b> {display_name}\n"
                        f"<b>Биржа:</b> {exchange}\n"
                        f"<b>Цена:</b> {price:.4f}\n"
                        f"<b>Таймфрейм:</b> {TIMEFRAME}\n"
                        f"<b>Время:</b> {current_time}\n\n"
                        f"<i>Стратегия: {LEADING_INDICATOR}</i>\n"
                        f"<i>Подтверждения: ✅</i>"
                    )
                    
                    if send_telegram_message(message):
                        print(f"  📨 Отправлен SHORTS для {display_name}")
                        previous_signals[symbol]['shorts'] = True
                        previous_signals[symbol]['long'] = False
                        stats['signals_sent'] += 1
                
                # Сброс флагов
                if not long_signal:
                    previous_signals[symbol]['long'] = False
                if not short_signal:
                    previous_signals[symbol]['shorts'] = False
            
            # Статистика
            elapsed_time = datetime.now() - stats['start_time']
            hours = elapsed_time.seconds // 3600
            minutes = (elapsed_time.seconds % 3600) // 60
            
            print("-" * 60)
            print(f"📊 Статистика:")
            print(f"   • Проверок: {stats['checks']}")
            print(f"   • Сигналов: {stats['signals_sent']}")
            print(f"   • Время работы: {hours:02d}:{minutes:02d}")
            
            # Прогресс-бар ожидания
            print(f"\n⏳ Следующая проверка через {CHECK_INTERVAL} сек...")
            for i in range(CHECK_INTERVAL):
                if i % 10 == 0:
                    progress = "█" * (i // 10) + "░" * ((CHECK_INTERVAL - i) // 10)
                    print(f"   [{progress}] {CHECK_INTERVAL - i:3d} сек", end="\r")
                time.sleep(1)
            print()
            
        except KeyboardInterrupt:
            print("\n\n" + "="*70)
            print("🛑 МОНИТОРИНГ ОСТАНОВЛЕН ПОЛЬЗОВАТЕЛЕМ")
            print("="*70)
            
            # Финальная статистика
            elapsed_time = datetime.now() - stats['start_time']
            hours = elapsed_time.seconds // 3600
            minutes = (elapsed_time.seconds % 3600) // 60
            
            end_msg = (
                f"<b>🛑 Бот остановлен</b>\n\n"
                f"<i>Итоговая статистика:</i>\n"
                f"• Пар мониторилось: {len(working_symbols)}\n"
                f"• Проверок выполнено: {stats['checks']}\n"
                f"• Сигналов отправлено: {stats['signals_sent']}\n"
                f"• Время работы: {hours:02d}:{minutes:02d}\n\n"
                f"<i>Время остановки: {datetime.now().strftime('%H:%M:%S')}</i>"
            )
            send_telegram_message(end_msg)
            
            print(f"\n📈 ИТОГОВАЯ СТАТИСТИКА:")
            print(f"   • Пар мониторилось: {len(working_symbols)}")
            print(f"   • Проверок выполнено: {stats['checks']}")
            print(f"   • Сигналов отправлено: {stats['signals_sent']}")
            print(f"   • Время работы: {hours:02d}:{minutes:02d}")
            print("\n👋 До новых сигналов!")
            break
            
        except Exception as e:
            print(f"\n⚠️ Критическая ошибка в главном цикле: {str(e)[:100]}")
            
            error_msg = (
                f"<b>⚠️ Ошибка в работе бота</b>\n\n"
                f"<i>Ошибка:</i> {str(e)[:100]}\n"
                f"<i>Время:</i> {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"<i>Бот перезапустится через 60 секунд...</i>"
            )
            send_telegram_message(error_msg)
            
            print("   Перезапуск через 60 секунд...")
            time.sleep(60)

# ============= ОСНОВНАЯ ФУНКЦИЯ =============
def main():
    """Основная функция"""
    print("\n" + "="*70)
    print("🤖 ТОРГОВЫЙ БОТ ДЛЯ МОНИТОРИНГА КРИПТОВАЛЮТ")
    print("="*70)
    print(f"👤 Telegram ID: {TELEGRAM_CHAT_ID}")
    print(f"📅 Дата: {datetime.now().strftime('%Y-%m-%d')}")
    print("="*70)
    
    # Проверка зависимостей
    print("\n🔧 ПРОВЕРКА ЗАВИСИМОСТЕЙ...")
    
    try:
        import requests
        print("   ✅ requests установлен")
    except:
        print("   ❌ requests не установлен")
        print("   💡 Установите: pip install requests")
        return
    
    try:
        import pandas
        print("   ✅ pandas установлен")
    except:
        print("   ❌ pandas не установлен")
        print("   💡 Установите: pip install pandas")
        return
    
    try:
        import talib
        print("   ✅ TA-Lib установлен")
    except:
        print("   ❌ TA-Lib не установлен")
        print("   💡 Установите альтернативу: pip install ta")
        # Используем альтернативу
        try:
            import ta
            talib = ta
            print("   ✅ Используется ta (альтернатива TA-Lib)")
        except:
            print("   ❌ Нет библиотек для технического анализа")
            print("   💡 Установите: pip install ta")
            return
    
    # Проверка Telegram
    print("\n📱 ПРОВЕРКА TELEGRAM...")
    if send_telegram_message("<b>🔧 Проверка связи...</b>\n\n<i>Бот запускается...</i>"):
        print("   ✅ Telegram подключен")
    else:
        print("   ❌ Не удалось подключиться к Telegram")
        print("   💡 Проверьте токен и Chat ID")
        return
    
    # Инициализация пар
    working_symbols = initialize_symbols()
    
    if working_symbols is None or len(working_symbols) == 0:
        print("\n❌ Не удалось найти рабочие пары")
        print("   Проверьте список символов или попробуйте позже")
        return
    
    print("\n" + "="*70)
    print("🎯 ВСЕ СИСТЕМЫ ГОТОВЫ К РАБОТЕ!")
    print("="*70)
    
    input("\nНажмите Enter для запуска мониторинга (Ctrl+C для выхода)...\n")
    
    try:
        main_monitoring_loop(working_symbols)
    except Exception as e:
        print(f"\n💥 Фатальная ошибка: {e}")
        print("   Перезапустите скрипт")

# ============= ЗАПУСК =============
if __name__ == "__main__":
    main()
