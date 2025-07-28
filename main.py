import telebot
import requests
import threading
import logging
import os
from functools import lru_cache
import time
import signal
import sys
from telebot import types
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
bot_token = os.getenv('BOT_TOKEN')
chat_id = os.getenv('CHAT_ID')
API_TIMEOUT = 60  # Увеличено время ожидания

# Разрешенные пользователи из .env
allowed_user_ids_str = os.getenv('ALLOWED_USER_IDS', '')
ALLOWED_USER_IDS = {int(uid.strip()) for uid in allowed_user_ids_str.split(',') if uid.strip()}

# API URLs из .env
api_urls_str = os.getenv('API_URLS', '')
api_urls = [url.strip() for url in api_urls_str.split(',') if url.strip()]

# Приватные данные кошельков из .env
MAIN_WALLET_ADDRESS = os.getenv('MAIN_WALLET_ADDRESS', '')
MAIN_WALLET_NAME = os.getenv('MAIN_WALLET_NAME', '🟢 Основной кошелек 🟢')

# Настройка retry стратегии для requests
session = requests.Session()
retry = Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

# Инициализация бота с увеличенным таймаутом
bot = telebot.TeleBot(bot_token, threaded=True, num_threads=4)

# Проверка обязательных переменных окружения
if not bot_token:
    logger.error("BOT_TOKEN не найден в .env файле")
    sys.exit(1)

if not chat_id:
    logger.error("CHAT_ID не найден в .env файле")
    sys.exit(1)

if not ALLOWED_USER_IDS:
    logger.error("ALLOWED_USER_IDS не найден в .env файле")
    sys.exit(1)

if not api_urls:
    logger.error("API_URLS не найден в .env файле")
    sys.exit(1)

if not MAIN_WALLET_ADDRESS:
    logger.error("MAIN_WALLET_ADDRESS не найден в .env файле")
    sys.exit(1)

logger.info(f"Бот настроен для пользователей: {ALLOWED_USER_IDS}")
logger.info(f"API URLs загружено: {len(api_urls)}")

# Функция для преобразования времени в секунды до следующего указанного времени по МСК

def get_seconds_until_next_update(hour, minute):
    msk_timezone = pytz.timezone('Europe/Moscow')
    now = datetime.now(msk_timezone)
    next_update = now.replace(
        hour=hour, minute=minute, second=0, microsecond=0)
    if now > next_update:
        next_update += timedelta(days=1)
    delta = next_update - now
    return int(delta.total_seconds())


UPDATE_INTERVAL = get_seconds_until_next_update(12, 20)


def get_cached_api_data(url, timeout=30):
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None

# Форматирование чисел

def format_number(number, is_decimal=False):
    try:
        if is_decimal:
            # Для десятичных чисел (Unclaimed TRX)
            return "{:,.2f}".format(float(number)/1e6).rstrip('0').rstrip('.') if '.' in "{:,.2f}".format(float(number)/1e6) else "{:,.2f}".format(float(number)/1e6)
        else:
            # Для целых чисел (Energy, Bandwidth)
            return "{:,.0f}".format(float(number)).replace(",", " ")
    except (ValueError, TypeError):
        return str(number)


# Получение курса USD/RUB

def get_usd_to_rub_rate():
    try:
        url = 'http://www.floatrates.com/daily/usd.json'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            rate = data['rub']['rate']
            return float("{:.2f}".format(rate))  # Округляет до 2х знаков
        return None
    except Exception as e:
        logger.error(f"Error getting USD/RUB rate: {e}")
        return None


# Получение курса криптовалют

def get_crypto_price(symbol):
    try:
        if symbol.upper() == 'TRX':
            symbol = 'TRX'

        url = f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT'
        data = get_cached_api_data(url)
        if data and 'price' in data:
            price = float(data['price'])
            return price
        return None
    except Exception as e:
        logger.error(f"Error getting {symbol} price: {e}")
        return None


# Отправка сообщений

def send_message(chat_id, message, parse_mode=None, reply_markup=None):
    try:
        bot.send_message(chat_id, message,
                         parse_mode=parse_mode,
                         reply_markup=reply_markup,
                         timeout=API_TIMEOUT)
    except Exception as e:
        logger.error(f"Error sending message: {e}")


# Получение данных кошелька

def get_wallet_data(api_url):
    try:
        data = get_cached_api_data(api_url)
        if not data:
            return None

        address = data.get('address', 'Unknown')
        bandwidth_data = data.get('bandwidth', {})
        with_price_tokens = data.get('withPriceTokens', [{}])
        reward_num = data.get('rewardNum', 0)  # Получаем unclaimed TRX
        # Получаем замороженные TRX в sun
        frozen_data = data.get('totalFrozenV2', 0)
        trx_amount = with_price_tokens[0].get(
            'amount', 0) if with_price_tokens else 0  # Free TRX в sun

        # Конвертируем frozen_data из sun в TRX (делим на 1,000,000)
        frozen_trx = float(frozen_data) / 1e6
        all_trx = round(float(trx_amount) + frozen_trx +
                        float(reward_num) / 1e6, 2)

        # Форматируем уже конвертированное значение
        frozen_trx_formatted = format_number(frozen_trx)

        # Расчет bandwidth
        net_remaining = bandwidth_data.get('netRemaining', 0)
        free_net_remaining = bandwidth_data.get('freeNetRemaining', 0)
        total_bandwidth = net_remaining + free_net_remaining
        net_limit = bandwidth_data.get('netLimit', 0)
        freeNetLimit = bandwidth_data.get('freeNetLimit', 0)
        free_bandwidth = net_limit + freeNetLimit

        # Получение TRX amount (уже в sun)
        trx_amount = with_price_tokens[0].get(
            'amount', 0) if with_price_tokens else 0

        # Получаем курс TRX
        trx_price = get_crypto_price('TRX')
        total_usd_value = 0
        if trx_price:
            # Суммируем все TRX (свободные + замороженные) и переводим в доллары
            total_trx = (float(trx_amount) + float(frozen_data)) / 1e6
            total_usd_value = total_trx * trx_price
            total_usd_value = "{:,.0f}".format(
                total_usd_value).replace(",", " ")

        return {
            'address': address,
            'energy_remaining': bandwidth_data.get('energyRemaining', 0),
            'energy_limit': bandwidth_data.get('energyLimit', 0),
            'total_bandwidth': total_bandwidth,
            'free_bandwidth': free_bandwidth,
            'trx_amount': trx_amount,
            'reward_num': reward_num,
            'frozen_trx': frozen_trx_formatted,
            'total_usd_value': total_usd_value,
            'all_trx': all_trx

        }
    except Exception as e:
        logger.error(f"Error processing wallet data: {e}")
        return None


# Создание постоянной клавиатуры (ReplyKeyboardMarkup)

def create_reply_keyboard():
    markup = types.ReplyKeyboardMarkup(
        row_width=2,
        resize_keyboard=True,
        one_time_keyboard=False  # Клавиатура будет постоянной
    )
    markup.add(
        types.KeyboardButton("BTC"),
        types.KeyboardButton("USD"),
        types.KeyboardButton("TRX"),
        types.KeyboardButton("Баланс"),
        types.KeyboardButton("Стата за месяц")
    )
    return markup


# Отправка данных о кошельках

def send_wallet_data(chat_id):
    message = ""
    for api_url in api_urls:
        wallet = get_wallet_data(api_url)
        if wallet:
            address = wallet['address']
            is_main = address == MAIN_WALLET_ADDRESS

            message += (
                f"{MAIN_WALLET_NAME if is_main else '🟡 Адрес кошелька 🟡'}\n\n"
                # f"{address}\n\n"
                f"💰 {wallet['total_usd_value']} $\n"
                f"🔻 ALL TRX   - {wallet['all_trx']}\n\n"
                # f"❄️ Staked TRX   - {wallet['frozen_trx']}\n\n"
                f"⚡️ Energy         -  {format_number(wallet['energy_remaining'])} / {format_number(wallet['energy_limit'])}\n"
                f"🔋 Bandwidth  -  {format_number(wallet['total_bandwidth'])} / {format_number(wallet['free_bandwidth'])}\n\n"
                f"🆓 Voting TRX   - {format_number(wallet['reward_num'], is_decimal=True)}\n"
                f"♦️ Free TRX      -  {format_number(wallet['trx_amount'])}\n\n"
            )
            save_daily_trx_stat(wallet['all_trx'])

    if message:
        send_message(chat_id, message, reply_markup=create_reply_keyboard())


# Таймер для автоматической проверки
timer_started = False


def start_timer(chat_id):
    global timer_started
    if timer_started:
        logger.info("⏳ Таймер уже запущен, повторный запуск игнорируется.")
        return
    timer_started = True

    def run():
        try:
            send_wallet_data(chat_id)
            if datetime.now(pytz.timezone('Europe/Moscow')).day == 1:
                earnings = get_last_month_earnings()
                if earnings is not None:
                    earnings_str = escape_markdown(f"{earnings:.2f}")
                    send_message(chat_id, f"За прошлый месяц заработано: *{earnings_str}* TRX 🔻", parse_mode="MarkdownV2")
        finally:
            interval = get_seconds_until_next_update(12, 20)
            logger.info(f"⏱ Следующий запуск через {interval} секунд")
            threading.Timer(interval, run).start()

    run()


# Обработчики команд

@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id not in ALLOWED_USER_IDS:
        bot.reply_to(message, "⛔ Извините, у вас нет доступа к этому боту.")
        return

    bot.send_message(
        message.chat.id,
        "Начинаю каждый день отправлять статистику в 12:20 МСК",
        reply_markup=create_reply_keyboard()
    )
    start_timer(message.chat.id)


@bot.message_handler(commands=['check'])
def check_wallets(message):
    if message.from_user.id not in ALLOWED_USER_IDS:
        return
    send_wallet_data(message.chat.id)


# Обработчик текстовых сообщений

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    if message.from_user.id not in ALLOWED_USER_IDS:
        return

    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        logger.error(f"Error deleting message: {e}")

    if message.text == 'BTC':
        price = get_crypto_price('BTC')
        if price:
            bot.send_message(message.chat.id,
                             f"💰 Курс BTC/USDT: {price} 💲",
                             reply_markup=create_reply_keyboard())
    elif message.text == 'USD':
        rate = get_usd_to_rub_rate()
        if rate:
            bot.send_message(message.chat.id,
                             f"💰 Курс USD к RUB: {rate} ₽",
                             reply_markup=create_reply_keyboard())
    elif message.text == 'TRX':
        price = get_crypto_price('TRX')
        if price:
            bot.send_message(message.chat.id,
                             f"💰 Курс TRX/USDT: {price} 💲",
                             reply_markup=create_reply_keyboard())
        else:
            bot.send_message(message.chat.id,
                             "⚠️ Не удалось получить курс TRX",
                             reply_markup=create_reply_keyboard())
    elif message.text == 'Баланс':
        send_wallet_data(message.chat.id)
    elif message.text == 'Стата за месяц':
        earnings = get_monthly_earnings()
        if earnings is not None:
            earnings_str = escape_markdown(f"{earnings:.2f}")
            bot.send_message(message.chat.id,
                             f"Заработано за этот месяц: *{earnings_str}* TRX 🔻",
                             parse_mode="MarkdownV2",
                             reply_markup=create_reply_keyboard())
        else:
            bot.send_message(message.chat.id,
                             "Нет данных для расчёта",
                             reply_markup=create_reply_keyboard())


def run_bot():
    while True:
        try:
            logger.info("Starting bot polling...")
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            time.sleep(10)  # Пауза перед повторной попыткой


def shutdown_handler(signum, frame):
    logger.info("Shutting down bot...")
    bot.stop_polling()
    sys.exit(0)


def save_daily_trx_stat(all_trx):
    today = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%Y-%m-%d')
    stats_file = 'trx_stats.json'
    try:
        if os.path.exists(stats_file):
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        else:
            stats = {}
        stats[today] = all_trx
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving daily trx stat: {e}")


def get_monthly_earnings():
    stats_file = 'trx_stats.json'
    try:
        if not os.path.exists(stats_file):
            return None
        with open(stats_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        now = datetime.now(pytz.timezone('Europe/Moscow'))
        year = now.year
        month = now.month

        # Даты текущего месяца
        month_dates = [d for d in stats.keys() if d.startswith(f"{year:04d}-{month:02d}-")]
        if not month_dates:
            return None
        last_date = max(month_dates)
        last_value = stats.get(last_date)

        # Найти последнюю дату прошлого месяца
        if month == 1:
            prev_year = year - 1
            prev_month = 12
        else:
            prev_year = year
            prev_month = month - 1
        prev_month_dates = [d for d in stats.keys() if d.startswith(f"{prev_year:04d}-{prev_month:02d}-")]
        if not prev_month_dates:
            return None
        prev_last_date = max(prev_month_dates)
        prev_last_value = stats.get(prev_last_date)

        if last_value is not None and prev_last_value is not None:
            return float(last_value) - float(prev_last_value)
        return None
    except Exception as e:
        logger.error(f"Error getting monthly earnings: {e}")
        return None


def get_last_month_earnings():
    stats_file = 'trx_stats.json'
    try:
        if not os.path.exists(stats_file):
            return None
        with open(stats_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        now = datetime.now(pytz.timezone('Europe/Moscow'))
        first_day_this_month = now.replace(day=1)
        last_month = first_day_this_month - timedelta(days=1)
        year = last_month.year
        month = last_month.month

        # Собираем все даты прошлого месяца
        month_dates = [d for d in stats.keys() if d.startswith(f"{year:04d}-{month:02d}-")]
        if not month_dates:
            return None
        # Берём минимальную (раннюю) и максимальную (позднюю) дату месяца
        first_date = min(month_dates)
        last_date = max(month_dates)
        first_value = stats.get(first_date)
        last_value = stats.get(last_date)
        if first_value is not None and last_value is not None:
            return float(last_value) - float(first_value)
        return None
    except Exception as e:
        logger.error(f"Error getting last month earnings: {e}")
        return None


def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(['\\' + c if c in escape_chars else c for c in str(text)])


if __name__ == '__main__':
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("Starting bot...")

    run_bot()
