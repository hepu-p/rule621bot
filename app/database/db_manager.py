import aiosqlite
import logging
import json
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)
DB_PATH = "database.db"

async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channel_settings (
                    admin_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    api_source TEXT DEFAULT 'e621',
                    tags TEXT DEFAULT 'cat',
                    negative_tags TEXT DEFAULT '',
                    post_interval_minutes INTEGER DEFAULT 20,
                    is_active BOOLEAN DEFAULT 0,
                    tags_mode TEXT DEFAULT 'AND',
                    post_priority TEXT DEFAULT 'random',
                    default_caption TEXT,
                    PRIMARY KEY (admin_id, channel_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS posted_media (
                    post_id INTEGER,
                    api_source TEXT,
                    PRIMARY KEY (post_id, api_source)
                )
            """)
            await db.commit()
            logger.info("Database initialized successfully.")
    except aiosqlite.Error as e:
        logger.error(f"Database initialization failed: {e}")

async def add_channel(admin_id: int, channel_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO channel_settings (admin_id, channel_id) VALUES (?, ?)", (admin_id, channel_id))
            await db.commit()
            logger.info(f"Channel {channel_id} added for admin {admin_id}.")
    except aiosqlite.Error as e:
        logger.error(f"Failed to add channel {channel_id} for admin {admin_id}: {e}")

async def get_channel_settings(admin_id: int, channel_id: int) -> Optional[dict]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM channel_settings WHERE admin_id = ? AND channel_id = ?", (admin_id, channel_id))
            row = await cursor.fetchone()
            if not row:
                logger.warning(f"No settings found for admin {admin_id} and channel {channel_id}.")
                return None
            
            settings = dict(row)
            if 'tags_mode' not in settings: settings['tags_mode'] = 'AND'
            if 'post_priority' not in settings: settings['post_priority'] = 'random'
            return settings
    except aiosqlite.Error as e:
        logger.error(f"Failed to get settings for admin {admin_id} and channel {channel_id}: {e}")
        return None

async def get_admin_channels(admin_id: int) -> List[dict]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM channel_settings WHERE admin_id = ?", (admin_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except aiosqlite.Error as e:
        logger.error(f"Failed to get channels for admin {admin_id}: {e}")
        return []

ALLOWED_COLUMNS = {
    "api_source", "tags", "negative_tags", "post_interval_minutes",
    "is_active", "tags_mode", "post_priority", "default_caption"
}

async def update_channel_setting(admin_id: int, channel_id: int, key: str, value):
    if key not in ALLOWED_COLUMNS:
        logger.error(f"Attempted to update a non-whitelisted column: {key}")
        raise ValueError(f"Invalid setting key: {key}")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            query = f"UPDATE channel_settings SET {key} = ? WHERE admin_id = ? AND channel_id = ?"
            await db.execute(query, (value, admin_id, channel_id))
            await db.commit()
            logger.info(f"Setting '{key}' for admin {admin_id} and channel {channel_id} updated to '{value}'.")
    except aiosqlite.Error as e:
        logger.error(f"Failed to update setting '{key}' for admin {admin_id} and channel {channel_id}: {e}")

async def get_all_active_channels() -> List[dict]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM channel_settings WHERE is_active = 1 AND channel_id IS NOT NULL")
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                settings = dict(row)
                if 'tags_mode' not in settings: settings['tags_mode'] = 'AND'
                if 'post_priority' not in settings: settings['post_priority'] = 'random'
                results.append(settings)
            return results
    except aiosqlite.Error as e:
        logger.error(f"Failed to get all active channels: {e}")
        return []

async def delete_channel(admin_id: int, channel_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM channel_settings WHERE admin_id = ? AND channel_id = ?", (admin_id, channel_id))
            await db.commit()
            logger.info(f"Channel {channel_id} deleted for admin {admin_id}.")
    except aiosqlite.Error as e:
        logger.error(f"Failed to delete channel {channel_id} for admin {admin_id}: {e}")

async def add_posted_media(post_id: int, api_source: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO posted_media (post_id, api_source) VALUES (?, ?)", (post_id, api_source))
            await db.commit()
    except aiosqlite.Error as e:
        logger.error(f"Failed to add posted media (post_id: {post_id}, api_source: {api_source}): {e}")

async def is_media_posted(post_id: int, api_source: str) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT 1 FROM posted_media WHERE post_id = ? AND api_source = ?", (post_id, api_source))
            return await cursor.fetchone() is not None
    except aiosqlite.Error as e:
        logger.error(f"Failed to check if media is posted (post_id: {post_id}, api_source: {api_source}): {e}")
        return False

async def backup_settings(admin_id: int) -> str:
    channels = await get_admin_channels(admin_id)
    return json.dumps(channels, indent=4)

async def restore_settings(admin_id: int, data: str):
    try:
        channels = json.loads(data)
        async with aiosqlite.connect(DB_PATH) as db:
            for channel in channels:
                # Basic validation
                if not all(k in channel for k in ['channel_id', 'api_source', 'tags']):
                    logger.warning(f"Skipping invalid channel data during restore: {channel}")
                    continue
                
                channel['admin_id'] = admin_id # Ensure admin_id is correct
                
                columns = ", ".join(channel.keys())
                placeholders = ", ".join(["?" for _ in channel.keys()])
                values = list(channel.values())
                
                query = f"INSERT OR REPLACE INTO channel_settings ({columns}) VALUES ({placeholders})"
                await db.execute(query, values)
            await db.commit()
            logger.info(f"Successfully restored settings for admin {admin_id}.")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error during restore for admin {admin_id}: {e}")
        raise ValueError("Invalid JSON format.")
    except aiosqlite.Error as e:
        logger.error(f"Database error during restore for admin {admin_id}: {e}")
        raise