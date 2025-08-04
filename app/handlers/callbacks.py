# app/handlers/callbacks.py
import html
import logging
from contextlib import suppress
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.keyboards.inline import (
    channels_menu,
    channel_settings_menu,
    api_choice_menu,
    posting_settings_menu,
    priority_choice_menu,
    confirm_delete_menu,
    skip_keyboard
)
from app.services.admin_service import get_channel_settings_service, update_channel_setting_service, get_admin_channels_service, delete_channel_service
from app.states.admin_states import AdminSettings, WizardStates
from app.services.scheduler import add_posting_job, remove_posting_job
from app.keyboards.callback_data import (
    ChannelCallback,
    SettingsCallback,
    ApiCallback,
    PriorityCallback,
    TagsModeCallback,
    MenuCallback,
    WizardCallback
)

router = Router()
logger = logging.getLogger(__name__)

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None, **kwargs):
    """Safely edits a message or sends a new one if editing fails."""
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(text, reply_markup=reply_markup, **kwargs)
        return
    try:
        await callback.message.answer(text, reply_markup=reply_markup, **kwargs)
    except Exception as e:
        logger.error(f"Failed to send new message after edit failed: {e}")


@router.callback_query(MenuCallback.filter(F.action == "add_channel"))
async def add_channel_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminSettings.waiting_for_channel)
    await safe_edit_message(callback, "Перешлите любое сообщение из вашего канала или введите его ID.")

@router.callback_query(ChannelCallback.filter(F.action == "select"))
async def select_channel_handler(callback: CallbackQuery, callback_data: ChannelCallback, state: FSMContext):
    await callback.answer()
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    await state.update_data(channel_id=channel_id)
    settings = await get_channel_settings_service(admin_id, channel_id)
    await safe_edit_message(callback, f"Настройки для канала {channel_id}:", reply_markup=channel_settings_menu(settings))

@router.callback_query(ChannelCallback.filter(F.action == "delete"))
async def delete_channel_handler(callback: CallbackQuery, callback_data: ChannelCallback, state: FSMContext):
    await callback.answer()
    channel_id = callback_data.channel_id
    await state.update_data(channel_id=channel_id)
    await safe_edit_message(callback, f"Вы уверены, что хотите удалить канал {channel_id}?", reply_markup=confirm_delete_menu(channel_id))

@router.callback_query(ChannelCallback.filter(F.action == "confirm_delete"))
async def confirm_delete_handler(callback: CallbackQuery, callback_data: ChannelCallback, state: FSMContext, bot: Bot, scheduler: AsyncIOScheduler):
    await callback.answer()
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    
    await delete_channel_service(admin_id, channel_id)
    await remove_posting_job(scheduler, admin_id, channel_id)
    
    await safe_edit_message(callback, f"Канал {channel_id} успешно удален.")
    
    await state.clear()
    channels = await get_admin_channels_service(admin_id)
    await callback.message.answer("Выберите канал для управления:", reply_markup=await channels_menu(channels, bot))

@router.callback_query(SettingsCallback.filter(F.action.in_(["start", "stop"])))
async def toggle_status_handler(callback: CallbackQuery, callback_data: SettingsCallback, scheduler: AsyncIOScheduler, bot: Bot):
    await callback.answer()
    admin_id = callback.from_user.id
    action = callback_data.action
    channel_id = callback_data.channel_id
    logger.info(f"User {admin_id} toggling status to {action} for channel {channel_id}")
    try:
        if action == "start":
            await update_channel_setting_service(admin_id, channel_id, "is_active", True)
            settings = await get_channel_settings_service(admin_id, channel_id)
            await add_posting_job(scheduler, bot, admin_id, channel_id, settings['post_interval_minutes'])
        else: # action == "stop"
            await update_channel_setting_service(admin_id, channel_id, "is_active", False)
            await remove_posting_job(scheduler, admin_id, channel_id)
        
        settings = await get_channel_settings_service(admin_id, channel_id)
        await safe_edit_message(callback, f"Настройки для канала {channel_id}:", reply_markup=channel_settings_menu(settings))
    except Exception as e:
        logger.error(f"Error toggling status for user {admin_id}: {e}")

@router.callback_query(SettingsCallback.filter(F.action == "open_posting_settings"))
async def open_posting_settings_handler(callback: CallbackQuery, callback_data: SettingsCallback, state: FSMContext):
    await callback.answer()
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    await state.update_data(channel_id=channel_id)
    settings = await get_channel_settings_service(admin_id, channel_id)
    await safe_edit_message(callback, "⚙️ Настройки постинга:", reply_markup=posting_settings_menu(settings))

@router.callback_query(SettingsCallback.filter(F.action == "set_tags"))
async def set_tags_handler(callback: CallbackQuery, callback_data: SettingsCallback, state: FSMContext):
    await callback.answer()
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    await state.update_data(channel_id=channel_id)
    settings = await get_channel_settings_service(admin_id, channel_id)
    current_tags = settings.get('tags', 'Не заданы')
    await state.set_state(AdminSettings.waiting_for_tags)
    await safe_edit_message(callback, f"Текущие теги: <code>{html.escape(current_tags)}</code>\n\nВведите новые теги через запятую.", parse_mode='HTML')

@router.callback_query(SettingsCallback.filter(F.action == "set_negative_tags"))
async def set_negative_tags_handler(callback: CallbackQuery, callback_data: SettingsCallback, state: FSMContext):
    await callback.answer()
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    await state.update_data(channel_id=channel_id)
    settings = await get_channel_settings_service(admin_id, channel_id)
    current_negative_tags = settings.get('negative_tags', 'Не заданы')
    await state.set_state(AdminSettings.waiting_for_negative_tags)
    await safe_edit_message(callback, f"Текущие анти-теги: <code>{html.escape(current_negative_tags)}</code>\n\nВведите новые анти-теги через запятую.", parse_mode='HTML')

@router.callback_query(SettingsCallback.filter(F.action == "set_api"))
async def set_api_handler(callback: CallbackQuery, callback_data: SettingsCallback, state: FSMContext):
    await callback.answer()
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    await state.update_data(channel_id=channel_id)
    settings = await get_channel_settings_service(admin_id, channel_id)
    await safe_edit_message(callback, "Выберите источник API:", reply_markup=api_choice_menu(settings['api_source'], channel_id))

@router.callback_query(ApiCallback.filter())
async def api_choice_handler(callback: CallbackQuery, callback_data: ApiCallback, state: FSMContext):
    await callback.answer()
    api_source = callback_data.api_source
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    await update_channel_setting_service(admin_id, channel_id, "api_source", api_source)
    settings = await get_channel_settings_service(admin_id, channel_id)
    await safe_edit_message(callback, f"Настройки для канала {channel_id}:", reply_markup=channel_settings_menu(settings))

@router.callback_query(SettingsCallback.filter(F.action == "set_interval"))
async def set_interval_handler(callback: CallbackQuery, callback_data: SettingsCallback, state: FSMContext):
    await callback.answer()
    channel_id = callback_data.channel_id
    await state.update_data(channel_id=channel_id)
    await state.set_state(AdminSettings.waiting_for_interval)
    await safe_edit_message(callback, "Введите интервал постинга в минутах (от 5 до 1440).")

@router.callback_query(SettingsCallback.filter(F.action == "set_default_caption"))
async def set_default_caption_handler(callback: CallbackQuery, callback_data: SettingsCallback, state: FSMContext):
    await callback.answer()
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    await state.update_data(channel_id=channel_id)
    settings = await get_channel_settings_service(admin_id, channel_id)
    current_caption = settings.get('default_caption') or 'Не задан'
    await state.set_state(AdminSettings.waiting_for_default_caption)
    await safe_edit_message(callback, f"Текущий шаблон: <code>{html.escape(current_caption)}</code>\n\nВведите новый шаблон. Вы можете использовать плейсхолдеры {{{{source}}}} и {{{{tags}}}}.", parse_mode='HTML')

@router.callback_query(MenuCallback.filter(F.action == "back_to_channels"))
async def back_to_channels_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    admin_id = callback.from_user.id
    await state.clear()
    channels = await get_admin_channels_service(admin_id)
    await safe_edit_message(callback, "Выберите канал для управления:", reply_markup=await channels_menu(channels, bot))

@router.callback_query(TagsModeCallback.filter())
async def switch_tags_mode_handler(callback: CallbackQuery, callback_data: TagsModeCallback, state: FSMContext):
    await callback.answer()
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    settings = await get_channel_settings_service(admin_id, channel_id)
    current_mode = settings.get('tags_mode', 'AND')
    new_mode = 'OR' if current_mode == 'AND' else 'AND'
    await update_channel_setting_service(admin_id, channel_id, "tags_mode", new_mode)
    settings = await get_channel_settings_service(admin_id, channel_id)
    await safe_edit_message(callback, "⚙️ Настройки постинга:", reply_markup=posting_settings_menu(settings))

@router.callback_query(SettingsCallback.filter(F.action == "open_priority_menu"))
async def open_priority_menu_handler(callback: CallbackQuery, callback_data: SettingsCallback, state: FSMContext):
    await callback.answer()
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    await state.update_data(channel_id=channel_id)
    settings = await get_channel_settings_service(admin_id, channel_id)
    await safe_edit_message(callback, "Выберите приоритет постов:", reply_markup=priority_choice_menu(settings['post_priority'], channel_id))

@router.callback_query(PriorityCallback.filter())
async def set_priority_handler(callback: CallbackQuery, callback_data: PriorityCallback, state: FSMContext):
    await callback.answer()
    priority = callback_data.priority
    channel_id = callback_data.channel_id
    admin_id = callback.from_user.id
    await update_channel_setting_service(admin_id, channel_id, "post_priority", priority)
    settings = await get_channel_settings_service(admin_id, channel_id)
    await safe_edit_message(callback, "Выберите приоритет постов:", reply_markup=priority_choice_menu(settings['post_priority'], channel_id))

@router.callback_query(WizardCallback.filter(F.action == "skip"))
async def skip_step_handler(callback: CallbackQuery, callback_data: WizardCallback, state: FSMContext, bot: Bot):
    await callback.answer()
    step = callback_data.step
    data = await state.get_data()
    channel_id = data.get('channel_id')
    admin_id = callback.from_user.id

    if step == "tags":
        await state.set_state(WizardStates.waiting_for_negative_tags)
        await safe_edit_message(callback, "Шаг 2/4: Введите анти-теги (нежелательные) через запятую.", reply_markup=skip_keyboard("negative_tags"))
    elif step == "negative_tags":
        await state.set_state(WizardStates.waiting_for_interval)
        await safe_edit_message(callback, "Шаг 3/4: Введите интервал постинга в минутах (от 5 до 1440).", reply_markup=skip_keyboard("interval"))
    elif step == "interval":
        await state.set_state(WizardStates.waiting_for_default_caption)
        await safe_edit_message(callback, "Шаг 4/4: Введите шаблон для подписи к постам.", reply_markup=skip_keyboard("default_caption"))
    elif step == "default_caption":
        await safe_edit_message(callback, "🎉 Настройка завершена! Канал готов к работе.")
        settings = await get_channel_settings_service(admin_id, channel_id)
        await callback.message.answer(f"Итоговые настройки для канала {channel_id}:", reply_markup=channel_settings_menu(settings))
        await state.clear()