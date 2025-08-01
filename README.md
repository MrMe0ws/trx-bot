<img width="403" height="259" alt="image" src="https://github.com/user-attachments/assets/3109d5d7-3fef-4b2c-b1e1-b75a3a936b1e" />

# TRX Bot 🤖

Telegram бот для мониторинга TRX кошельков и отслеживания заработка.

## 📋 Функционал

### 🔍 Мониторинг кошельков

- Отслеживание баланса TRX кошельков
- Мониторинг Energy и Bandwidth
- Конвертация в USD
- Автоматическая отправка статистики каждый день в 12:20 МСК

### 📊 Статистика заработка

- **Кнопка "Стата за месяц"** — показывает заработок за текущий месяц
- **Автоматическая рассылка** — 1-го числа каждого месяца отправляет статистику за прошлый месяц
- **Ежедневное сохранение** — записывает значение ALL TRX в `trx_stats.json`

### 💱 Курсы валют

- Курс BTC/USDT
- Курс TRX/USDT
- Курс USD/RUB

## 🚀 Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd trx-bot
```

### 2. Установка зависимостей

```bash
pip install pyTelegramBotAPI python-dotenv requests pytz
```

### 3. Создание .env файла

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot Token
BOT_TOKEN=your_bot_token_here

# Chat ID для отправки сообщений
CHAT_ID=your_chat_tg_id_here
CHAT_ID = 11111111

# Разрешённые пользователи (через запятую)
ALLOWED_USER_IDS=your_user_tg_id_here
ALLOWED_USER_IDS = 1111111

# Кошелёк
MAIN_WALLET_ADDRESS = 'TJMeCcNqBhmpf81YKUP7hogzL6FJznV1QH'
MAIN_WALLET_NAME = '🟢 Кошелек FJznV1QH 🟢'

# API URLs для кошельков (через запятую)
API_URLS=https://apilist.tronscanapi.com/api/accountv2?address=YOUR_WALLET_ADDRESS
# API URLs
API_URLS = [ 'https://apilist.tronscanapi.com/api/accountv2?address=TJMeCcNqBhmpf81YKUP7hogzL6FJznV1QH',
    # 'https://apilist.tronscanapi.com/api/accountv2?address=TVoCL7N1CUXLnXCxrss19SeJNz7JRMZnBL'
]
```

### 4. Настройка бота

1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Получите токен и добавьте в `BOT_TOKEN`
3. Получите ваш Chat ID и добавьте в `CHAT_ID`
4. Добавьте ваш User ID в `ALLOWED_USER_IDS`
5. Добавьте API URLs ваших кошельков в `API_URLS`

## 🏃‍♂️ Запуск

### Windows

```cmd
py main.py
```

### Linux/Mac

```bash
python3 main.py
```

## 📁 Структура файлов

```
trx-bot/
├── main.py              # Основной файл бота
├── .env                 # Конфигурация (не в репозитории)
├── trx_stats.json       # История ALL TRX (создаётся автоматически)
├── .gitignore          # Исключения для Git
└── README.md           # Этот файл
```

## 🎯 Использование

### Команды бота

- `/start` — запуск бота и начало ежедневной рассылки

### Кнопки

- **BTC** — курс BTC/USDT
- **USD** — курс USD/RUB
- **TRX** — курс TRX/USDT
- **Баланс** — статистика кошельков
- **Стата за месяц** — заработок за текущий месяц

### Автоматические функции

- **Ежедневно в 12:20 МСК** — отправка статистики кошельков
- **1-го числа месяца** — отправка статистики за прошлый месяц
- **Ежедневное сохранение** — запись ALL TRX в `trx_stats.json`

## 📊 Формат данных

### trx_stats.json

```json
{
  "2024-07-01": 1000.0,
  "2024-07-02": 1030.0,
  "2024-07-03": 1075.0
}
```

### Расчёт заработка

- **За месяц** = (максимальное значение текущего месяца) - (максимальное значение прошлого месяца)
- **1-го числа** показывает реальную прибыль с начала месяца

## 🔧 Конфигурация

### Настройка времени

В файле `main.py` можно изменить время отправки:

```python
UPDATE_INTERVAL = get_seconds_until_next_update(12, 20)  # 12:20 МСК
```

## 🛠️ Технические детали

### Зависимости

- `pyTelegramBotAPI` — Telegram Bot API
- `python-dotenv` — загрузка переменных окружения
- `requests` — HTTP запросы
- `pytz` — работа с часовыми поясами

### Безопасность

- Все приватные данные в `.env` файле
- `.env` исключён из Git через `.gitignore`
- Проверка обязательных переменных при запуске

### Логирование

- Подробные логи в консоли
- Обработка ошибок API
- Retry стратегия для запросов
