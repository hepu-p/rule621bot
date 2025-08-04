# app/services/scheduler.py
import asyncio
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, Optional

import aiohttp
import aiofiles
from aiogram import Bot
from aiogram.types import FSInputFile, URLInputFile
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramAPIError, TelegramEntityTooLarge, TelegramNetworkError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.api_client import get_api_client, HEADERS
from app.database.db_manager import is_media_posted, add_posted_media, get_channel_settings, update_channel_setting

logger = logging.getLogger(__name__)
TEMP_DIR = Path("temp_media")


async def cleanup_temp_media():
    if not TEMP_DIR.exists():
        TEMP_DIR.mkdir(exist_ok=True)
        return
    for item in TEMP_DIR.iterdir():
        try:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            logger.error(f"Failed to remove temp item {item}: {e}")


async def check_dependencies():
    """Проверяет наличие ffmpeg и aria2c в системе."""
    try:
        ffmpeg_check = await asyncio.create_subprocess_exec("ffmpeg", "-version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await ffmpeg_check.communicate()
        if ffmpeg_check.returncode != 0:
            logger.critical("FFMPEG is not installed or not in PATH. Please install it (`sudo apt install ffmpeg`). WEBM conversion will fail.")
    except FileNotFoundError:
        logger.critical("FFMPEG is not installed or not in PATH. Please install it (`sudo apt install ffmpeg`). WEBM conversion will fail.")

    try:
        aria2c_check = await asyncio.create_subprocess_exec("aria2c", "--version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await aria2c_check.communicate()
        if aria2c_check.returncode != 0:
            logger.critical("aria2c is not installed or not in PATH. Please install it (`sudo apt install aria2`). Downloads will be slower.")
    except FileNotFoundError:
        logger.critical("aria2c is not installed or not in PATH. Please install it (`sudo apt install aria2`). Downloads will be slower.")

async def add_posting_job(scheduler, bot: Bot, admin_id: int, channel_id: int, interval_minutes: int):
    job_id = f"job_{admin_id}_{channel_id}"
    if scheduler.get_job(job_id):
        scheduler.reschedule_job(job_id, trigger="interval", minutes=interval_minutes)
        logger.info(f"Rescheduled job for admin {admin_id} and channel {channel_id} to every {interval_minutes} minutes.")
    else:
        scheduler.add_job(
            posting_job, "interval", minutes=interval_minutes,
            args=[bot, admin_id, channel_id, scheduler], id=job_id
        )
        logger.info(f"Scheduled job for admin {admin_id} and channel {channel_id} every {interval_minutes} minutes.")

async def remove_posting_job(scheduler, admin_id: int, channel_id: int):
    job_id = f"job_{admin_id}_{channel_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"Removed job for admin {admin_id} and channel {channel_id}.")

async def convert_webm_to_playable(original_path: Path, converted_path: Path) -> bool:
    logger.info(f"Attempting to convert {original_path}...")
    command = [
        'ffmpeg', '-i', str(original_path),
        '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p',
        '-crf', '23', '-preset', 'ultrafast', # Changed to ultrafast for less CPU usage
        '-y', '-loglevel', 'error', str(converted_path)
    ]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(f"FFMPEG failed for {original_path}. Stderr: {stderr.decode()}")
        return False
    logger.info(f"Successfully converted {original_path} to {converted_path}.")
    return True

async def download_file(url: str, filepath: Path) -> bool:
    user_agent = HEADERS.get("User-Agent", "Mozilla/5.0")
    if shutil.which("aria2c"):
        process = await asyncio.create_subprocess_exec(
            'aria2c', '--dir=' + str(filepath.parent), '--out=' + filepath.name,
            '--max-connection-per-server=16', '--split=16', '--min-split-size=1M',
            f'--user-agent={user_agent}', '--quiet=true', '--show-console-readout=false',
            '--summary-interval=0', '--log-level=error', url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode == 0:
            logger.info(f"Successfully downloaded with aria2c to {filepath}.")
            return True
        logger.error(f"aria2c failed to download {url}. Stderr: {stderr.decode().strip()}")
    
    logger.info(f"Falling back to aiohttp for {url}")
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                async with aiofiles.open(filepath, 'wb') as f:
                    await f.write(await response.read())
                logger.info(f"Successfully downloaded with aiohttp to {filepath}.")
                return True
    except aiohttp.ClientError as e:
        logger.error(f"aiohttp download failed for {url}: {e}")
        return False

async def send_media_by_url(bot: Bot, chat_id: int, media_info: Dict, kwargs: Dict) -> bool:
    url, ext, post_id = media_info['url'], media_info['ext'], media_info['id']
    send_method = None
    
    if ext in ['jpg', 'jpeg', 'png']:
        send_method, kwargs['photo'] = bot.send_photo, URLInputFile(url, filename=f"{post_id}.{ext}")
    elif ext == 'gif':
        send_method, kwargs['animation'] = bot.send_animation, URLInputFile(url, filename=f"{post_id}.{ext}")
    elif ext == 'mp4':
        send_method, kwargs['video'] = bot.send_video, URLInputFile(url, filename=f"{post_id}.{ext}")
    
    if send_method:
        await send_method(chat_id=chat_id, **kwargs)
        return True
    return False

async def send_media_by_file(bot: Bot, chat_id: int, admin_id: int, media_info: Dict, kwargs: Dict) -> bool:
    url, ext, source, post_id = media_info['url'], media_info['ext'], media_info['source'], media_info['id']
    random_suffix = uuid.uuid4().hex[:8]
    original_filepath = TEMP_DIR / f"{post_id}_{random_suffix}_orig.{ext}"
    converted_filepath = TEMP_DIR / f"{post_id}_{random_suffix}_conv.mp4"
    send_method = None

    try:
        if not await download_file(url, original_filepath):
            await bot.send_message(admin_id, f"❌ Не удалось скачать файл для поста {source}.")
            return False

        if ext in ['jpg', 'jpeg', 'png']:
            send_method, kwargs['photo'] = bot.send_photo, FSInputFile(original_filepath)
        elif ext == 'gif':
            send_method, kwargs['animation'] = bot.send_animation, FSInputFile(original_filepath)
        elif ext == 'mp4':
            send_method, kwargs['video'] = bot.send_video, FSInputFile(original_filepath)
        elif ext == 'webm':
            if not await convert_webm_to_playable(original_filepath, converted_filepath):
                await bot.send_message(admin_id, f"⚠️ Не удалось конвертировать WEBM для поста {source}. Отправляю как документ.")
                await bot.send_document(chat_id, document=FSInputFile(original_filepath), caption=kwargs.get('caption'), parse_mode='HTML')
                return True
            send_method, kwargs['video'] = bot.send_video, FSInputFile(converted_filepath)
        
        if send_method:
            await send_method(chat_id=chat_id, **kwargs)
            return True
        return False
    finally:
        for p in [original_filepath, converted_filepath]:
            if p.exists():
                try:
                    os.remove(p)
                except OSError as e:
                    logger.error(f"Error removing temp file {p}: {e}")

async def send_media(bot: Bot, chat_id: int, admin_id: int, media_info: Dict, scheduler: AsyncIOScheduler, custom_caption: Optional[str] = None, default_caption: Optional[str] = None) -> bool:
    source = media_info['source']
    caption = custom_caption or default_caption or f'<a href="{source}">Источник</a>'
    caption = caption.replace("{{source}}", f'<a href="{source}">Источник</a>').replace("{{tags}}", ", ".join(media_info.get('tags', [])))
    send_kwargs = {'caption': caption, 'parse_mode': 'HTML', 'request_timeout': 300}

    try:
        # First, try sending by URL
        if media_info['ext'] not in ['webm']:
            logger.info(f"Attempting to send post {media_info['id']} by URL.")
            try:
                if await send_media_by_url(bot, chat_id, media_info, send_kwargs.copy()):
                    # Send notification to admin
                    admin_kwargs = {**send_kwargs.copy(), 'caption': f"✅ Отправлено в канал {chat_id}.\n{caption}"}
                    await send_media_by_url(bot, admin_id, media_info, admin_kwargs)
                    return True
            except (TelegramNetworkError, TelegramBadRequest, TelegramAPIError) as e:
                if isinstance(e, TelegramNetworkError) or "wrong file identifier/http url specified" in str(e) or "failed to get HTTP URL content" in str(e):
                    logger.warning(f"Failed to send post {media_info['id']} by URL: {e}. Falling back to file download.")
                    await bot.send_message(admin_id, f"⚠️ Не удалось отправить пост {source} по URL. Пробую скачать и отправить вручную.")
                else:
                    raise # Re-raise other Telegram API errors

        # Fallback to sending by file if URL fails or for webm
        logger.info(f"Sending post {media_info['id']} by file download.")
        if await send_media_by_file(bot, chat_id, admin_id, media_info, send_kwargs.copy()):
            # Send notification to admin
            admin_kwargs = {**send_kwargs.copy(), 'caption': f"✅ Отправлено в канал {chat_id}.\n{caption}"}
            await send_media_by_file(bot, admin_id, admin_id, media_info, admin_kwargs)
            return True
        return False

    except TelegramForbiddenError:
        logger.error(f"Bot is not an admin in channel {chat_id} or was kicked. Disabling posting.")
        await update_channel_setting(admin_id, chat_id, "is_active", False)
        await remove_posting_job(scheduler, admin_id, chat_id)
        await bot.send_message(admin_id, f"❌ Ошибка: Бот не является администратором в канале {chat_id} или был кикнут. Автопостинг для этого канала остановлен.")
        return False
    except TelegramEntityTooLarge:
        logger.warning(f"Media file for post {source} is too large for Telegram. Skipping.")
        await bot.send_message(admin_id, f"❌ Файл для поста {source} слишком большой для Telegram. Пропускаю.")
        return True # Mark as posted to avoid retrying
    except Exception as e:
        logger.exception(f"An unexpected error occurred while sending media for post {source} to {chat_id}: {e}")
        await bot.send_message(admin_id, f"❌ Непредвиденная ошибка при обработке поста {source}: {e}")
        return False

async def posting_job(bot: Bot, admin_id: int, channel_id: int, scheduler: AsyncIOScheduler, custom_caption: Optional[str] = None):
    logger.info(f"Starting posting job for admin {admin_id} and channel {channel_id}")
    channel_settings = await get_channel_settings(admin_id, channel_id)
    if not channel_settings or (not custom_caption and (not channel_settings.get('is_active') or not channel_settings.get('channel_id'))):
        logger.warning(f"Posting job for admin {admin_id} and channel {channel_id} skipped due to inactive status or missing settings.")
        return

    default_caption = channel_settings.get('default_caption')

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            api_client = get_api_client(channel_settings['api_source'], session)
            
            for attempt in range(15):
                logger.info(f"Attempt {attempt + 1}/15 to find new content for admin {admin_id} and channel {channel_id}")
                post = await api_client.get_post(
                    tags=channel_settings['tags'],
                    negative_tags=channel_settings['negative_tags'],
                    tags_mode=channel_settings.get('tags_mode', 'AND'),
                    post_priority=channel_settings.get('post_priority', 'random')
                )

                if not post:
                    await asyncio.sleep(2)
                    continue

                if not await is_media_posted(post['id'], channel_settings['api_source']):
                    logger.info(f"Found new post {post['id']} for admin {admin_id} and channel {channel_id}")
                    if await send_media(bot, channel_id, admin_id, post, scheduler, custom_caption=custom_caption, default_caption=default_caption):
                        await add_posted_media(post['id'], channel_settings['api_source'])
                        logger.info(f"Successfully posted media {post['id']} for admin {admin_id} and channel {channel_id}.")
                        return
                    else:
                        logger.warning(f"Failed to send media for post {post['id']}. Trying next post.")
                else:
                    logger.info(f"Post {post['id']} has already been posted. Skipping.")
                
                await asyncio.sleep(1)

        logger.warning(f"Failed to find new content for admin_id={admin_id} and channel_id={channel_id} after 15 attempts.")
        await bot.send_message(admin_id, f"⚠️ Не удалось найти новый контент для постинга в канал {channel_id} после 15 попыток.")

    except Exception as e:
        logger.exception(f"A critical error occurred in the posting job for admin {admin_id} and channel {channel_id}: {e}")
        await bot.send_message(admin_id, f"❌ Произошла критическая ошибка в задаче постинга для канала {channel_id}: {e}")
