# app/database/db_manager.py
import aiosqlite
from typing import Optional, List

DB_PATH = "database.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_settings (
                admin_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                api_source TEXT DEFAULT 'e621',
                tags TEXT DEFAULT 'cat',
                negative_tags TEXT DEFAULT '',
                post_interval_minutes INTEGER DEFAULT 20,
                is_active BOOLEAN DEFAULT 0,
                tags_mode TEXT DEFAULT 'AND',
                post_priority TEXT DEFAULT 'random'
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

async def add_admin_if_not_exists(admin_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT admin_id FROM admin_settings WHERE admin_id = ?", (admin_id,))
        if await cursor.fetchone() is None:
            await db.execute("INSERT INTO admin_settings (admin_id) VALUES (?)", (admin_id,))
            await db.commit()

async def get_admin_settings(admin_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM admin_settings WHERE admin_id = ?", (admin_id,))
        except aiosqlite.OperationalError:
            await init_db()
            cursor = await db.execute("SELECT * FROM admin_settings WHERE admin_id = ?", (admin_id,))
        
        row = await cursor.fetchone()
        if not row: return None
        
        settings = dict(row)
        if 'tags_mode' not in settings: settings['tags_mode'] = 'AND'
        if 'post_priority' not in settings: settings['post_priority'] = 'random'
        return settings

async def update_setting(admin_id: int, key: str, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE admin_settings SET {key} = ? WHERE admin_id = ?", (value, admin_id))
        await db.commit()

async def get_all_active_admins() -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute("SELECT * FROM admin_settings WHERE is_active = 1 AND channel_id IS NOT NULL")
        except aiosqlite.OperationalError:
            await init_db()
            cursor = await db.execute("SELECT * FROM admin_settings WHERE is_active = 1 AND channel_id IS NOT NULL")
        
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            settings = dict(row)
            if 'tags_mode' not in settings: settings['tags_mode'] = 'AND'
            if 'post_priority' not in settings: settings['post_priority'] = 'random'
            results.append(settings)
        return results

async def add_posted_media(post_id: int, api_source: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO posted_media (post_id, api_source) VALUES (?, ?)", (post_id, api_source))
        await db.commit()

async def is_media_posted(post_id: int, api_source: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM posted_media WHERE post_id = ? AND api_source = ?", (post_id, api_source))
        return await cursor.fetchone() is not None
