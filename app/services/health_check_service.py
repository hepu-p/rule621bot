# app/services/health_check_service.py
import asyncio
import logging
import os
from pathlib import Path
import aiohttp
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database.db_manager import (
    get_all_active_channels,
    add_channel,
    get_channel_settings,
    update_channel_setting,
    delete_channel,
    restore_settings,
    backup_settings
)
from app.services.api_client import E621Client, Rule34Client, HEADERS
from app.services.scheduler import check_dependencies

logger = logging.getLogger(__name__)
TEMP_DIR = Path("temp_media")
TEST_ADMIN_ID = -1 # Специальный ID для тестовых данных
TEST_CHANNEL_ID = -1337 # Специальный ID для тестового канала

async def run_full_health_check(bot: Bot, scheduler: AsyncIOScheduler):
    """
    Запускает комплексную проверку состояния бота в тихом режиме, логируя все шаги.
    """
    logger.info("--- Starting Full Health Check ---")

    # --- Stage 1: System Checks ---
    logger.info("--- Stage 1: System Checks ---")
    
    # 1.1. Database Check
    try:
        await get_all_active_channels()
        logger.info("Health Check: Database connection successful.")
    except Exception as e:
        logger.error(f"Health Check FAIL: Database connection: {e}")

    # 1.2. API Connectivity Check
    async with aiohttp.ClientSession(headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as session:
        try:
            e621_client = E621Client(session)
            await e621_client.get_post("cat", "", "AND", "random")
            logger.info("Health Check: E621 API connection successful.")
        except Exception as e:
            logger.error(f"Health Check FAIL: E621 API connection: {e}")

        try:
            rule34_client = Rule34Client(session)
            await rule34_client.get_post("cat", "", "AND", "random")
            logger.info("Health Check: Rule34 API connection successful.")
        except Exception as e:
            logger.error(f"Health Check FAIL: Rule34 API connection: {e}")

    # 1.3. Dependencies Check
    try:
        await check_dependencies()
        logger.info("Health Check: External dependencies check executed (see logs for details).")
    except Exception as e:
        logger.error(f"Health Check FAIL: External dependencies check: {e}")

    # 1.4. Scheduler Status
    try:
        logger.info(f"Health Check: Scheduler is {'running' if scheduler.running else 'stopped'} with {len(scheduler.get_jobs())} jobs.")
    except Exception as e:
        logger.error(f"Health Check FAIL: Scheduler status check: {e}")

    # 1.5. Filesystem Permissions
    try:
        test_file = TEMP_DIR / "health_check.tmp"
        test_file.touch()
        test_file.unlink()
        logger.info("Health Check: Filesystem permissions in temp_media are OK.")
    except Exception as e:
        logger.error(f"Health Check FAIL: Filesystem permissions: {e}")

    # --- Stage 2: Functional Workflow Simulation ---
    logger.info("--- Stage 2: Functional Workflow Simulation ---")
    backup_data = None
    try:
        # 2.1. Add Channel
        logger.info("Health Check: Testing channel creation...")
        await add_channel(TEST_ADMIN_ID, TEST_CHANNEL_ID)
        settings = await get_channel_settings(TEST_ADMIN_ID, TEST_CHANNEL_ID)
        if not (settings and settings['channel_id'] == TEST_CHANNEL_ID):
            raise ValueError("Channel was not created in the DB.")
        logger.info("Health Check: Channel creation successful.")

        # 2.2. Update Settings
        logger.info("Health Check: Testing settings update...")
        test_settings = {
            "api_source": "rule34", "tags": "test_tag", "negative_tags": "bad_tag",
            "post_interval_minutes": 60, "is_active": True, "tags_mode": "OR",
            "post_priority": "newest", "default_caption": "Test caption"
        }
        for key, value in test_settings.items():
            await update_channel_setting(TEST_ADMIN_ID, TEST_CHANNEL_ID, key, value)
            new_settings = await get_channel_settings(TEST_ADMIN_ID, TEST_CHANNEL_ID)
            db_value = bool(new_settings[key]) if isinstance(value, bool) else new_settings[key]
            if db_value != value:
                raise ValueError(f"Failed to update setting '{key}'. Expected: {value}, Got: {db_value}")
        logger.info("Health Check: Settings update successful.")

        # 2.3. Backup
        logger.info("Health Check: Testing backup...")
        backup_data = await backup_settings(TEST_ADMIN_ID)
        if not (backup_data and str(TEST_CHANNEL_ID) in backup_data):
            raise ValueError("Backup creation failed or test channel not in backup.")
        logger.info("Health Check: Backup successful.")

        # 2.4. Deletion
        logger.info("Health Check: Testing channel deletion...")
        await delete_channel(TEST_ADMIN_ID, TEST_CHANNEL_ID)
        if await get_channel_settings(TEST_ADMIN_ID, TEST_CHANNEL_ID):
            raise ValueError("Channel was not deleted from the DB.")
        logger.info("Health Check: Channel deletion successful.")

        # 2.5. Restore
        logger.info("Health Check: Testing restore from backup...")
        await restore_settings(TEST_ADMIN_ID, backup_data)
        restored_settings = await get_channel_settings(TEST_ADMIN_ID, TEST_CHANNEL_ID)
        if not (restored_settings and restored_settings['tags'] == "test_tag"):
            raise ValueError("Channel was not restored from backup.")
        logger.info("Health Check: Restore from backup successful.")

    except Exception as e:
        logger.error(f"Health Check FAIL: Functional test failed at step: {e}")
    finally:
        # 2.6. Cleanup
        logger.info("Health Check: Cleaning up test data...")
        await delete_channel(TEST_ADMIN_ID, TEST_CHANNEL_ID)
        logger.info("Health Check: Test data cleaned up.")

    logger.info("--- Full Health Check Finished ---")