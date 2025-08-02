# app/services/scheduler.py
import asyncio
import logging
import os
from pathlib import Path
from typing import Dict

import aiofiles
import aiohttp
from aiogram import Bot
from aiogram.types import FSInputFile, URLInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.services.api_client import get_api_client
from app.database.db_manager import is_media_posted, add_posted_media

TEMP_DIR = Path("temp_media")
TEMP_DIR.mkdir(exist_ok=True)

async def convert_webm_to_playable(original_path: Path, converted_path: Path) -> bool:
    logging.info(f"Converting {original_path} to {converted_path}...")
    process = await asyncio.create_subprocess_exec(
        'ffmpeg', '-i', str(original_path), '-c:v', 'libvpx-vp9', '-c:a', 'libopus',
        '-crf', '32', '-b:v', '1500k', '-y', '-loglevel', 'error', str(converted_path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        logging.error(f"FFMPEG failed for {original_path}. Error: {stderr.decode()}")
        return False
    logging.info(f"Successfully converted {original_path}.")
    return True

async def send_media(bot: Bot, chat_id: int, admin_id: int, media_info: Dict):
    url, ext, source, post_id = media_info['url'], media_info['ext'], media_info['source'], media_info['id']
    caption = f'<a href="{source}">Источник</a>'
    kwargs = {'caption': caption, 'parse_mode': 'HTML'}
    original_filepath = TEMP_DIR / f"{post_id}_orig.{ext}"
    converted_filepath = TEMP_DIR / f"{post_id}_conv.webm"

    try:
        if ext == 'webm':
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200: raise Exception(f"Failed to download file: status {resp.status}")
                    async with aiofiles.open(original_filepath, 'wb') as f: await f.write(await resp.read())
            
            if not await convert_webm_to_playable(original_filepath, converted_filepath):
                await bot.send_document(chat_id, document=FSInputFile(original_filepath), caption=f"⚠️ Не удалось конвертировать WEBM. {caption}", parse_mode='HTML')
                await bot.send_document(admin_id, document=FSInputFile(original_filepath), caption=f"⚠️ Не удалось конвертировать WEBM. {caption}", parse_mode='HTML')
                return

            send_method, kwargs['video'] = bot.send_video, FSInputFile(converted_filepath)
        else:
            input_file = URLInputFile(url, filename=f"{post_id}.{ext}")
            if ext in ['jpg', 'jpeg', 'png']: send_method, kwargs['photo'] = bot.send_photo, input_file
            elif ext == 'gif': send_method, kwargs['animation'] = bot.send_animation, input_file
            elif ext == 'mp4': send_method, kwargs['video'] = bot.send_video, input_file
            else: logging.warning(f"Unsupported file type: {ext} for post {source}"); return
        
        await send_method(chat_id=chat_id, **kwargs)
        kwargs_for_admin = kwargs.copy()
        kwargs_for_admin['caption'] = f"✅ Отправлено в канал {chat_id}.\n{caption}"
        await send_method(chat_id=admin_id, **kwargs_for_admin)
    except Exception as e:
        await bot.send_message(admin_id, f"❌ Ошибка при обработке поста {source}: {e}")
    finally:
        if original_filepath.exists(): os.remove(original_filepath)
        if converted_filepath.exists(): os.remove(converted_filepath)

async def posting_job(bot: Bot, admin_settings: dict):
    """Задача, выполняемая планировщиком. Стала НАМНОГО проще."""
    admin_id, channel_id = admin_settings['admin_id'], admin_settings['channel_id']
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
        api_client = get_api_client(admin_settings['api_source'], session)
        
        # Пытаемся найти новый пост несколько раз
        for _ in range(10):
            post = await api_client.get_post(
                tags=admin_settings['tags'],
                negative_tags=admin_settings['negative_tags'],
                tags_mode=admin_settings.get('tags_mode', 'AND'),
                post_priority=admin_settings.get('post_priority', 'random')
            )

            if post and not await is_media_posted(post['id'], admin_settings['api_source']):
                await send_media(bot, channel_id, admin_id, post)
                await add_posted_media(post['id'], admin_settings['api_source'])
                return # Успех, выходим
            
            await asyncio.sleep(1) # Ждем перед следующей попыткой

    await bot.send_message(admin_id, "⚠️ Не удалось найти новый контент за 10 попыток. Возможно, все посты по вашим тегам уже были отправлены.")
