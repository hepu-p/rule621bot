from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="▶️ Запустить бота"),
        BotCommand(command="settings", description="⚙️ Настройки каналов"),
        BotCommand(command="addchannel", description="➕ Добавить новый канал"),
        BotCommand(command="test_post", description="🧪 Отправить тестовый пост"),
        BotCommand(command="postwithcaption", description="📝 Пост с уникальной подписью"),
        BotCommand(command="status", description="📊 Статус активных задач"),
        BotCommand(command="backup", description="💾 Резервное копирование настроек"),
        BotCommand(command="restore", description="🔄 Восстановление настроек"),
        BotCommand(command="health_check", description="🩺 Проверка состояния бота"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())
