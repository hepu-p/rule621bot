# Rule621Bot

## Описание
Telegram-бот для автоматического постинга медиа из booru-сайтов (e621, rule34) в ваш канал. Бот обладает гибкими настройками и предназначен для администраторов каналов.

## Description
A Telegram bot for automatically posting media from booru sites (e621, rule34) to your channel. The bot has flexible settings and is intended for channel administrators.

---

## 🇷🇺 Русский

### Функционал
- **Автопостинг:** Автоматическая публикация медиа в заданный канал с настраиваемым интервалом.
- **Поддержка API:** Работа с `e621.net` и `rule34.xxx`.
- **Гибкая настройка:**
    - Выбор источника API.
    - Настройка тегов для поиска (включая логику "И"/"ИЛИ").
    - Настройка анти-тегов (исключающие теги).
    - Установка интервала постинга.
    - Выбор приоритета постов (случайный, новый, популярный и т.д.).
- **Кастомные подписи:**
    - Возможность установить шаблон подписи по умолчанию с плейсхолдерами `{{source}}` и `{{tags}}`.
    - Отправка поста с уникальной, одноразовой подписью.
- **Надежность:**
    - Проверка на дубликаты постов.
    - Отказоустойчивая загрузка и конвертация медиа (`webm` в `mp4`).
    - Подробное логирование и уведомление администраторов об ошибках.
- **Удобное управление:**
    - Меню команд для быстрого доступа к функциям.
    - Интерактивное меню настроек с кнопками.

### Зависимости
#### Python
Указаны в файле `requirements.txt`:
```
aiogram==3.4.1
aiohttp==3.9.3
aiosqlite==0.19.0
APScheduler==3.10.4
PyYAML==6.0.1
python-dotenv==1.0.1
aiofiles==23.2.1
pydantic==2.5.3
pydantic-settings==2.2.1
cachetools==5.3.3
```

#### Внешние зависимости
- **FFmpeg:** для конвертации видео.
- **aria2c:** для ускоренной загрузки файлов.

### Установка и запуск
1.  **Клонируйте репозиторий:**
    ```bash
    git clone <repository_url>
    cd rule621bot
    ```
2.  **Создайте и активируйте виртуальное окружение:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  **Установите зависимости Python:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Установите внешние зависимости:**
    *   **Debian/Ubuntu:**
        ```bash
        sudo apt update && sudo apt install ffmpeg aria2 -y
        ```
    *   **Arch Linux:**
        ```bash
        sudo pacman -S ffmpeg aria2
        ```
5.  **Настройте конфигурацию:**
    *   Создайте файл `.env` из `env_example` и вставьте в него токен вашего бота:
        ```
        BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
        ```
    *   Создайте файл `config.yaml` из `config.yaml.exaple` и добавьте ваш Telegram User ID в список `admin_ids`.
6.  **Запустите бота:**
    ```bash
    python bot.py
    ```

### Использование
- `/start` - Запустить бота и открыть меню настроек.
- `/status` - Показать текущий статус и настройки.
- `/test_post` - Отправить тестовый пост в канал.
- `/postwithcaption` - Отправить пост с уникальной подписью.

---

## 🇬🇧 English

### Features
- **Auto-posting:** Automatically publishes media to a specified channel at a configurable interval.
- **API Support:** Works with `e621.net` and `rule34.xxx`.
- **Flexible Configuration:**
    - Choose the API source.
    - Set search tags (with "AND"/"OR" logic).
    - Set negative tags (to exclude posts).
    - Define the posting interval.
    - Select post priority (random, newest, most popular, etc.).
- **Custom Captions:**
    - Ability to set a default caption template with `{{source}}` and `{{tags}}` placeholders.
    - Send a post with a unique, one-time caption.
- **Reliability:**
    - Checks for duplicate posts to avoid reposting.
    - Resilient media downloading and conversion (`webm` to `mp4`).
    - Detailed logging and error notifications for admins.
- **Convenient Management:**
    - Command menu for quick access to features.
    - Interactive settings menu with buttons.

### Dependencies
#### Python
Listed in the `requirements.txt` file:
```
aiogram==3.4.1
aiohttp==3.9.3
aiosqlite==0.19.0
APScheduler==3.10.4
PyYAML==6.0.1
python-dotenv==1.0.1
aiofiles==23.2.1
pydantic==2.5.3
pydantic-settings==2.2.1
cachetools==5.3.3
```

#### External Dependencies
- **FFmpeg:** for video conversion.
- **aria2c:** for accelerated file downloads.

### Installation and Launch
1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd rule621bot
    ```
2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Install external dependencies:**
    *   **Debian/Ubuntu:**
        ```bash
        sudo apt update && sudo apt install ffmpeg aria2 -y
        ```
    *   **Arch Linux:**
        ```bash
        sudo pacman -S ffmpeg aria2
        ```
5.  **Configure the bot:**
    *   Create a `.env` file from `env_example` and insert your bot token:
        ```
        BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
        ```
    *   Create a `config.yaml` file from `config.yaml.exaple` and add your Telegram User ID to the `admin_ids` list.
6.  **Run the bot:**
    ```bash
    python bot.py
    ```

### Usage
- `/start` - Start the bot and open the settings menu.
- `/status` - Show the current status and settings.
- `/test_post` - Send a test post to the channel.
- `/postwithcaption` - Send a post with a unique caption.
