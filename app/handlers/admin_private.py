# app/handlers/admin_private.py
import html
import logging
import io
import os
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.admin_service import (
    get_channel_settings_service,
    update_channel_setting_service,
    add_channel_service,
    get_admin_channels_service,
    backup_settings_service,
    restore_settings_service
)
from app.keyboards.inline import channels_menu, channel_settings_menu, skip_keyboard
from app.states.admin_states import AdminSettings, WizardStates
from app.services.scheduler import posting_job, add_posting_job
from app.services.health_check_service import run_full_health_check
from app.utils.text_helpers import escape_md_v2

router = Router()
logger = logging.getLogger(__name__)

async def show_channels_menu(message: Message, admin_id: int, state: FSMContext, bot: Bot):
    try:
        channels = await get_admin_channels_service(admin_id)
        if not channels:
            await message.answer("У вас еще нет добавленных каналов. Используйте /addchannel, чтобы добавить первый.")
            return
        if len(channels) == 1:
            channel_id = channels[0]['channel_id']
            await state.update_data(channel_id=channel_id)
            settings = await get_channel_settings_service(admin_id, channel_id)
            chat = await bot.get_chat(channel_id)
            await message.answer(f"Автоматически выбран единственный канал: {chat.title}\n\nНастройки для канала:", reply_markup=channel_settings_menu(settings))
        else:
            await message.answer("Выберите канал для управления:", reply_markup=await channels_menu(channels, bot))
    except Exception as e:
        logger.error(f"Error showing channels menu for admin {admin_id}: {e}")
        await message.answer("Произошла ошибка при отображении меню каналов.")

async def start_wizard(message: Message, state: FSMContext, channel_id: int):
    await state.update_data(channel_id=channel_id)
    await state.set_state(WizardStates.waiting_for_tags)
    await message.answer("Шаг 1/4: Введите теги для поиска через запятую.", reply_markup=skip_keyboard("tags"))

@router.message(CommandStart())
async def command_start_handler(message: Message):
    await message.answer(f"""Привет, {message.from_user.full_name}!

Я бот для автоматического постинга медиа в ваши каналы. Вот что я умею:
/settings - Управление каналами
/addchannel - Добавить новый канал""")

@router.message(Command("settings"))
async def command_settings_handler(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    await show_channels_menu(message, message.from_user.id, state, bot)

@router.message(Command("addchannel"))
async def command_add_channel_handler(message: Message, state: FSMContext):
    await state.set_state(AdminSettings.waiting_for_channel)
    await message.answer("Перешлите любое сообщение из вашего канала или введите его ID.")

@router.message(Command("status"))
async def command_status_handler(message: Message, scheduler: AsyncIOScheduler):
    admin_id = message.from_user.id
    jobs = scheduler.get_jobs()
    if not jobs:
        await message.answer("Активных задач нет.")
        return

    status_text = "📊 <b>Статус активных задач:</b>\n\n"
    admin_jobs_found = False
    for job in jobs:
        if job.id.startswith(f"job_{admin_id}"):
            admin_jobs_found = True
            channel_id = html.escape(job.id.split('_')[-1])
            next_run = html.escape(job.next_run_time.strftime("%Y-%m-%d %H:%M:%S UTC") if job.next_run_time else "N/A")
            status_text += f"- <b>Канал:</b> <code>{channel_id}</code>\n"
            status_text += f"  <b>Следующий пост:</b> <code>{next_run}</code>\n\n"
    
    if not admin_jobs_found:
        await message.answer("У вас нет активных задач.")
        return

    await message.answer(status_text, parse_mode="HTML")

@router.message(Command("backup"))
async def command_backup_handler(message: Message):
    admin_id = message.from_user.id
    backup_data = await backup_settings_service(admin_id)
    if not backup_data:
        await message.answer("Нет настроек для резервного копирования.")
        return
    
    file_name = f"rule621bot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    file = BufferedInputFile(backup_data.encode('utf-8'), filename=file_name)
    await message.answer_document(file, caption="Ваш файл с резервной копией настроек.")

@router.message(Command("restore"))
async def command_restore_handler(message: Message, state: FSMContext):
    await state.set_state(AdminSettings.waiting_for_restore_file)
    await message.answer("Пожалуйста, отправьте файл с резервной копией настроек.")

@router.message(AdminSettings.waiting_for_restore_file, F.document)
async def process_restore_file(message: Message, state: FSMContext, bot: Bot):
    admin_id = message.from_user.id
    if not message.document.file_name.endswith('.json'):
        await message.answer("Пожалуйста, отправьте .json файл.")
        return
    
    file_path = None
    try:
        file = await bot.get_file(message.document.file_id)
        file_path = await bot.download_file(file.file_path)
        data = file_path.read().decode('utf-8')
        
        await restore_settings_service(admin_id, data)
        await message.answer("✅ Настройки успешно восстановлены. Перезапустите бота, чтобы применить все изменения.")
    except Exception as e:
        logger.error(f"Failed to restore settings for admin {admin_id}: {e}")
        await message.answer(f"❌ Произошла ошибка при восстановлении настроек: {e}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        await state.clear()

@router.message(Command("test_post"))
async def command_test_post_handler(message: Message, bot: Bot, state: FSMContext, scheduler: AsyncIOScheduler):
    admin_id = message.from_user.id
    data = await state.get_data()
    channel_id = data.get('channel_id')
    if not channel_id:
        await message.answer("Сначала выберите канал через /settings")
        return
    
    await message.answer(f"⏳ Выполняю тестовый поиск и отправку поста для канала {channel_id}... Пожалуйста, подождите.")
    await posting_job(bot, admin_id, channel_id, scheduler)

@router.message(Command("health_check"))
async def command_health_check_handler(message: Message, bot: Bot, scheduler: AsyncIOScheduler):
    from app.services.health_check_service import run_full_health_check
    await message.answer("⏳ Выполняется полная проверка всех систем бота... Результаты будут в логах.")
    await run_full_health_check(bot, scheduler)
    await message.answer("Проверка окончена.")

@router.message(AdminSettings.waiting_for_channel)
async def process_channel_id(message: Message, state: FSMContext, bot: Bot):
    admin_id = message.from_user.id
    channel_id = None
    if message.forward_from_chat:
        channel_id = message.forward_from_chat.id
    elif message.text and message.text.lstrip('-').isdigit():
        channel_id = int(message.text)
    
    if channel_id:
        try:
            await add_channel_service(admin_id, channel_id)
            await message.answer(f"✅ Канал {channel_id} успешно добавлен. Начнем настройку.")
            await start_wizard(message, state, channel_id)
        except Exception as e:
            logger.error(f"Error adding channel for user {admin_id}: {e}")
            await message.answer("Произошла ошибка при добавлении канала.")
    else:
        await message.answer("Не удалось определить ID канала. Пожалуйста, перешлите сообщение из канала или отправьте его ID.")

# --- WIZARD HANDLERS ---
@router.message(WizardStates.waiting_for_tags)
async def process_wizard_tags(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    data = await state.get_data()
    channel_id = data.get('channel_id')
    await update_channel_setting_service(admin_id, channel_id, "tags", message.text.lower())
    await message.answer("✅ Теги сохранены.")
    await state.set_state(WizardStates.waiting_for_negative_tags)
    await message.answer("Шаг 2/4: Введите анти-теги (нежелательные) через запятую.", reply_markup=skip_keyboard("negative_tags"))

@router.message(WizardStates.waiting_for_negative_tags)
async def process_wizard_negative_tags(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    data = await state.get_data()
    channel_id = data.get('channel_id')
    await update_channel_setting_service(admin_id, channel_id, "negative_tags", message.text.lower())
    await message.answer("✅ Анти-теги сохранены.")
    await state.set_state(WizardStates.waiting_for_interval)
    await message.answer("Шаг 3/4: Введите интервал постинга в минутах (от 5 до 1440).", reply_markup=skip_keyboard("interval"))

@router.message(WizardStates.waiting_for_interval)
async def process_wizard_interval(message: Message, state: FSMContext, bot: Bot, scheduler: AsyncIOScheduler):
    admin_id = message.from_user.id
    data = await state.get_data()
    channel_id = data.get('channel_id')
    try:
        interval = int(message.text)
        if not (5 <= interval <= 1440):
            raise ValueError("Interval must be between 5 and 1440 minutes.")
        await update_channel_setting_service(admin_id, channel_id, "post_interval_minutes", interval)
        await message.answer(f"✅ Интервал сохранен: {interval} минут.")
        await state.set_state(WizardStates.waiting_for_default_caption)
        await message.answer("Шаг 4/4: Введите шаблон для подписи к постам.", reply_markup=skip_keyboard("default_caption"))
    except (ValueError, TypeError):
        await message.answer("❌ Неверное значение. Введите число от 5 до 1440.")

@router.message(WizardStates.waiting_for_default_caption)
async def process_wizard_default_caption(message: Message, state: FSMContext, bot: Bot):
    admin_id = message.from_user.id
    data = await state.get_data()
    channel_id = data.get('channel_id')
    await update_channel_setting_service(admin_id, channel_id, "default_caption", message.text)
    await message.answer("✅ Шаблон сообщения сохранен.")
    await state.clear()
    await message.answer("🎉 Настройка завершена! Канал готов к работе.")
    settings = await get_channel_settings_service(admin_id, channel_id)
    await message.answer(f"Итоговые настройки для канала {channel_id}:", reply_markup=channel_settings_menu(settings))

# --- EDIT HANDLERS (called from settings menu) ---
@router.message(AdminSettings.waiting_for_tags)
async def process_tags_edit(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    data = await state.get_data()
    channel_id = data.get('channel_id')
    await update_channel_setting_service(admin_id, channel_id, "tags", message.text.lower())
    await message.answer(f"✅ Теги для канала {channel_id} обновлены.")
    await state.clear()
    settings = await get_channel_settings_service(admin_id, channel_id)
    await message.answer(f"Настройки для канала {channel_id}:", reply_markup=channel_settings_menu(settings))

@router.message(AdminSettings.waiting_for_negative_tags)
async def process_negative_tags_edit(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    data = await state.get_data()
    channel_id = data.get('channel_id')
    await update_channel_setting_service(admin_id, channel_id, "negative_tags", message.text.lower())
    await message.answer(f"✅ Анти-теги для канала {channel_id} обновлены.")
    await state.clear()
    settings = await get_channel_settings_service(admin_id, channel_id)
    await message.answer(f"Настройки для канала {channel_id}:", reply_markup=channel_settings_menu(settings))

@router.message(AdminSettings.waiting_for_interval)
async def process_interval_edit(message: Message, state: FSMContext, bot: Bot, scheduler: AsyncIOScheduler):
    admin_id = message.from_user.id
    data = await state.get_data()
    channel_id = data.get('channel_id')
    try:
        interval = int(message.text)
        if not (5 <= interval <= 1440):
            raise ValueError("Interval must be between 5 and 1440 minutes.")
        
        await update_channel_setting_service(admin_id, channel_id, "post_interval_minutes", interval)
        
        settings = await get_channel_settings_service(admin_id, channel_id)
        if settings and settings.get('is_active'):
            await add_posting_job(scheduler, bot, admin_id, channel_id, interval)
            
        await message.answer(f"✅ Интервал для канала {channel_id} обновлен: {interval} минут.")
        await state.clear()
        
        settings = await get_channel_settings_service(admin_id, channel_id)
        await message.answer(f"Настройки для канала {channel_id}:", reply_markup=channel_settings_menu(settings))

    except (ValueError, TypeError):
        await message.answer("❌ Неверное значение. Введите число от 5 до 1440.")

@router.message(AdminSettings.waiting_for_default_caption)
async def process_default_caption_edit(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    data = await state.get_data()
    channel_id = data.get('channel_id')
    await update_channel_setting_service(admin_id, channel_id, "default_caption", message.text)
    await message.answer(f"✅ Шаблон сообщения для канала {channel_id} обновлен.")
    await state.clear()
    settings = await get_channel_settings_service(admin_id, channel_id)
    await message.answer(f"Итоговые настройки для канала {channel_id}:", reply_markup=channel_settings_menu(settings))

@router.message(Command("postwithcaption"))
async def command_post_with_caption_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get('channel_id'):
        await message.answer("Сначала выберите канал через /settings")
        return
    await state.set_state(AdminSettings.waiting_for_custom_caption)
    await message.answer("Введите сообщение для поста. Вы можете использовать плейсхолдеры {{source}} и {{tags}}.")

@router.message(AdminSettings.waiting_for_custom_caption)
async def process_custom_caption(message: Message, state: FSMContext, bot: Bot, scheduler: AsyncIOScheduler):
    admin_id = message.from_user.id
    data = await state.get_data()
    channel_id = data.get('channel_id')
    await state.clear()
    await posting_job(bot, admin_id, channel_id, scheduler, custom_caption=message.text)
