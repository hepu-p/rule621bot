# bot.py
import asyncio
import logging
import os
import yaml
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import db_manager
from app.handlers import admin_private, callbacks
from app.services.scheduler import posting_job
from app.database.db_manager import get_all_active_admins
from app.middlewares.logging_middleware import LoggingMiddleware

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config(path: str = "config.yaml"):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

async def on_startup(bot: Bot, admin_ids: list):
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, "✅ Бот успешно запущен и готов к работе!")
        except Exception as e:
            logging.error(f"Failed to send startup message to admin {admin_id}: {e}")

async def main():
    load_dotenv()
    config = load_config()
    admin_ids = config['admin_ids']

    bot = Bot(token=os.getenv("BOT_TOKEN"))
    
    scheduler = AsyncIOScheduler(timezone="UTC")
    dp = Dispatcher()
    
    dp['admin_ids'] = admin_ids
    dp['scheduler'] = scheduler
    
    await db_manager.init_db()

    dp.update.middleware(LoggingMiddleware())

    dp.include_router(admin_private.router)
    dp.include_router(callbacks.router)

    active_admins = await get_all_active_admins()
    for admin_settings in active_admins:
        if admin_settings['admin_id'] in admin_ids:
            scheduler.add_job(
                posting_job, "interval", minutes=admin_settings['post_interval_minutes'],
                args=[bot, admin_settings], id=f"job_{admin_settings['admin_id']}"
            )
            logging.info(f"Scheduled job for admin {admin_settings['admin_id']} every {admin_settings['post_interval_minutes']} minutes.")

    scheduler.start()
    await on_startup(bot, admin_ids)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
