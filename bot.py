import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
import coloredlogs

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config_reader import config, admin_config
from app.database.db_manager import init_db, get_all_active_channels
from app.handlers import admin_private, callbacks
from app.middlewares.logging_middleware import LoggingMiddleware
from app.middlewares.error_middleware import ErrorMiddleware
from app.middlewares.throttling_middleware import ThrottlingMiddleware
from app.services.scheduler import posting_job, check_dependencies, cleanup_temp_media
from app.utils.commands import set_commands


def setup_logging():
    # Create logs directory if it doesn't exist
    import os
    if not os.path.exists('logs'):
        os.makedirs('logs')

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)'
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Configure file handler
    file_handler = RotatingFileHandler('logs/bot.log', maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)

    # Configure stream handler for console
    coloredlogs.install(level='INFO', fmt=log_format, logger=root_logger, stream=sys.stdout)

    logging.info("Logging setup complete.")


async def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone="UTC")
    if not admin_config.admin_ids:
        logging.warning("No admin IDs configured. Scheduler will not be started.")
        return scheduler

    active_channels = await get_all_active_channels()
    for channel_settings in active_channels:
        if channel_settings['admin_id'] in admin_config.admin_ids:
            scheduler.add_job(
                posting_job, "interval", minutes=channel_settings['post_interval_minutes'],
                args=[bot, channel_settings['admin_id'], channel_settings['channel_id'], scheduler], 
                id=f"job_{channel_settings['admin_id']}_{channel_settings['channel_id']}"
            )
            logging.info(f"Scheduled job for admin {channel_settings['admin_id']} and channel {channel_settings['channel_id']} every {channel_settings['post_interval_minutes']} minutes.")
    return scheduler


def setup_dispatcher(scheduler: AsyncIOScheduler):
    dp = Dispatcher(storage=MemoryStorage())
    dp['admin_ids'] = admin_config.admin_ids
    dp['scheduler'] = scheduler

    # Middlewares
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(ErrorMiddleware(admin_ids=admin_config.admin_ids))
    dp.message.middleware(ThrottlingMiddleware())

    # Routers
    dp.include_router(admin_private.router)
    dp.include_router(callbacks.router)
    return dp


async def on_startup(bot: Bot):
    await cleanup_temp_media()
    await set_commands(bot)
    await check_dependencies()
    if not admin_config.admin_ids:
        logging.warning("No admin IDs configured. Startup message will not be sent.")
        return

    for admin_id in admin_config.admin_ids:
        try:
            await bot.send_message(admin_id, "✅ Бот успешно запущен и готов к работе!")
        except Exception as e:
            logging.error(f"Failed to send startup message to admin {admin_id}: {e}")


async def main():
    setup_logging()
    await init_db()

    if not config or not config.bot_token:
        logging.critical("Bot token is not configured. Please check your .env file.")
        return

    bot = Bot(token=config.bot_token.get_secret_value())
    scheduler = await setup_scheduler(bot)
    dp = setup_dispatcher(scheduler)

    try:
        scheduler.start()
        await on_startup(bot)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
