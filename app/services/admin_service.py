# app/services/admin_service.py
from app.database.db_manager import (
    get_channel_settings,
    update_channel_setting,
    add_channel,
    get_admin_channels,
    delete_channel as db_delete_channel,
    backup_settings,
    restore_settings
)
from typing import Optional, List, Dict

async def get_channel_settings_service(admin_id: int, channel_id: int) -> Optional[Dict]:
    return await get_channel_settings(admin_id, channel_id)

async def update_channel_setting_service(admin_id: int, channel_id: int, key: str, value):
    await update_channel_setting(admin_id, channel_id, key, value)

async def add_channel_service(admin_id: int, channel_id: int):
    await add_channel(admin_id, channel_id)

async def get_admin_channels_service(admin_id: int) -> List[Dict]:
    return await get_admin_channels(admin_id)

async def delete_channel_service(admin_id: int, channel_id: int):
    await db_delete_channel(admin_id, channel_id)

async def backup_settings_service(admin_id: int) -> str:
    return await backup_settings(admin_id)

async def restore_settings_service(admin_id: int, data: str):
    await restore_settings(admin_id, data)