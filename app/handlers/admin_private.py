# app/handlers/admin_private.py
import html
import logging
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database.db_manager import get_admin_settings, update_setting, add_admin_if_not_exists
from app.keyboards.inline import main_menu
from app.states.admin_states import AdminSettings
from app.services.scheduler import posting_job

router = Router()

async def show_main_menu_message(message: Message, admin_id: int):
    settings = await get_admin_settings(admin_id)
    await message.answer("⚙️ Меню настроек:", reply_markup=main_menu(settings))

@router.message(CommandStart())
async def command_start_handler(message: Message, admin_ids: list):
    if message.from_user.id not in admin_ids:
        await message.answer("У вас нет доступа к этому боту.")
        return
    
    await add_admin_if_not_exists(message.from_user.id)
    await message.answer(f"Привет, {message.from_user.full_name}!\n"
                         "Это бот для автоматического постинга медиа в канал. Начнем настройку.")
    await show_main_menu_message(message, message.from_user.id)

@router.message(Command("status"))
async def command_status_handler(message: Message, scheduler: AsyncIOScheduler):
    admin_id = message.from_user.id
    settings = await get_admin_settings(admin_id)
    
    if not settings:
        await message.answer("Ваши настройки не найдены. Начните с /start")
        return

    status_text = f"<b>Статус для {message.from_user.full_name}</b>\n\n"
    status_text += f"<b>Канал:</b> <code>{settings['channel_id'] or 'Не задан'}</code>\n"
    status_text += f"<b>API:</b> {settings['api_source']}\n"
    status_text += f"<b>Интервал:</b> {settings['post_interval_minutes']} мин.\n"
    
    job_id = f"job_{admin_id}"
    job = scheduler.get_job(job_id)
    
    if settings['is_active'] and job:
        status_text += "<b>Автопостинг:</b> ✅ Включен\n"
        next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        status_text += f"<b>Следующий пост:</b> {next_run}\n"
    else:
        status_text += "<b>Автопостинг:</b> ❌ Выключен\n"

    await message.answer(status_text, parse_mode='HTML')

@router.message(Command("test_post"))
async def command_test_post_handler(message: Message, bot: Bot):
    admin_id = message.from_user.id
    settings = await get_admin_settings(admin_id)

    if not settings or not settings['channel_id']:
        await message.answer("❌ Не могу выполнить тестовый постинг. Сначала настройте бота и укажите ID канала через /start.")
        return

    await message.answer("⏳ Выполняю тестовый поиск и отправку поста... Пожалуйста, подождите.")
    try:
        await posting_job(bot, settings)
    except Exception as e:
        await message.answer(f"❌ Во время тестового постинга произошла ошибка: {e}")

@router.message(AdminSettings.waiting_for_channel)
async def process_channel_id(message: Message, state: FSMContext):
    channel_id = None
    if message.forward_from_chat:
        channel_id = message.forward_from_chat.id
    elif message.text and message.text.lstrip('-').isdigit():
        channel_id = int(message.text)
    
    if channel_id:
        await update_setting(message.from_user.id, "channel_id", channel_id)
        await message.answer(f"✅ Канал {channel_id} успешно установлен.")
        await state.clear()
        settings = await get_admin_settings(message.from_user.id)
        await message.answer("⚙️ Меню настроек:", reply_markup=main_menu(settings))
    else:
        await message.answer("Не удалось определить ID канала. Пожалуйста, перешлите сообщение из канала или отправьте его ID.")

@router.message(AdminSettings.waiting_for_tags)
async def process_tags(message: Message, state: FSMContext):
    logging.info(f"HANDLER: Entered process_tags for user {message.from_user.id}. Text: '{message.text}'")
    await update_setting(message.from_user.id, "tags", message.text.lower())
    escaped_input = html.escape(message.text)
    await message.answer(f"✅ Теги обновлены: <code>{escaped_input}</code>", parse_mode='HTML')
    await state.clear()
    settings = await get_admin_settings(message.from_user.id)
    await message.answer("⚙️ Меню настроек:", reply_markup=main_menu(settings))

@router.message(AdminSettings.waiting_for_negative_tags)
async def process_negative_tags(message: Message, state: FSMContext):
    logging.info(f"HANDLER: Entered process_negative_tags for user {message.from_user.id}. Text: '{message.text}'")
    await update_setting(message.from_user.id, "negative_tags", message.text.lower())
    escaped_input = html.escape(message.text)
    await message.answer(f"✅ Анти-теги обновлены: <code>{escaped_input}</code>", parse_mode='HTML')
    await state.clear()
    settings = await get_admin_settings(message.from_user.id)
    await message.answer("⚙️ Меню настроек:", reply_markup=main_menu(settings))

@router.message(AdminSettings.waiting_for_interval)
async def process_interval(message: Message, state: FSMContext):
    try:
        interval = int(message.text)
        if not (5 <= interval <= 1440):
            raise ValueError
        await update_setting(message.from_user.id, "post_interval_minutes", interval)
        await message.answer(f"✅ Интервал обновлен: {interval} минут.")
        await state.clear()
        settings = await get_admin_settings(message.from_user.id)
        await message.answer("⚙️ Меню настроек:", reply_markup=main_menu(settings))
    except (ValueError, TypeError):
        await message.answer("❌ Неверное значение. Введите число от 5 до 1440.")
