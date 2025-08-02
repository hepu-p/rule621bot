# app/handlers/callbacks.py
import html
import logging
from contextlib import suppress
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from app.keyboards.inline import (main_menu, api_choice_menu, back_to_main_menu, 
                                  posting_settings_menu, priority_choice_menu)
from app.database.db_manager import get_admin_settings, update_setting
from app.states.admin_states import AdminSettings

router = Router()

async def show_main_menu(message: Message, admin_id: int):
    settings = await get_admin_settings(admin_id)
    with suppress(TelegramBadRequest):
        await message.edit_text("⚙️ Главное меню настроек:", reply_markup=main_menu(settings))

@router.callback_query(F.data.startswith("status_toggle_"))
async def toggle_posting(callback: CallbackQuery, bot: Bot):
    action = callback.data.removeprefix("status_toggle_")
    is_active = 1 if action == "start" else 0
    settings = await get_admin_settings(callback.from_user.id)
    if not settings.get('channel_id') and is_active:
        await callback.answer("Сначала нужно указать ID канала!", show_alert=True)
        return
    await update_setting(callback.from_user.id, "is_active", is_active)
    status = "включена" if is_active else "остановлена"
    await callback.answer(f"Автоматическая отправка {status}.")
    await show_main_menu(callback.message, callback.from_user.id)

@router.callback_query(F.data == "refresh_menu")
async def refresh_menu_callback(callback: CallbackQuery):
    await show_main_menu(callback.message, callback.from_user.id)
    await callback.answer("Меню обновлено.")
    
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu(callback.message, callback.from_user.id)

@router.callback_query(F.data == "open_posting_settings")
async def open_posting_settings(callback: CallbackQuery):
    settings = await get_admin_settings(callback.from_user.id)
    await callback.message.edit_text("⚙️ Настройки логики постинга:", reply_markup=posting_settings_menu(settings))

@router.callback_query(F.data == "switch_tags_mode")
async def switch_tags_mode(callback: CallbackQuery):
    settings = await get_admin_settings(callback.from_user.id)
    new_mode = 'OR' if settings.get('tags_mode', 'AND') == 'AND' else 'AND'
    await update_setting(callback.from_user.id, "tags_mode", new_mode)
    mode_text = "ИЛИ (любой из тегов)" if new_mode == 'OR' else "И (все теги вместе)"
    await callback.answer(f"Логика тегов изменена на: {mode_text}")
    new_settings = await get_admin_settings(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=posting_settings_menu(new_settings))

@router.callback_query(F.data == "open_priority_menu")
async def open_priority_menu(callback: CallbackQuery):
    settings = await get_admin_settings(callback.from_user.id)
    await callback.message.edit_text("Выберите приоритет для поиска постов:", reply_markup=priority_choice_menu(settings.get('post_priority', 'random')))

@router.callback_query(F.data.startswith("set_priority_"))
async def set_priority(callback: CallbackQuery):
    priority = callback.data.removeprefix("set_priority_")
    await update_setting(callback.from_user.id, "post_priority", priority)
    await callback.answer("Приоритет изменен!")
    settings = await get_admin_settings(callback.from_user.id)
    await callback.message.edit_text("Выберите приоритет для поиска постов:", reply_markup=priority_choice_menu(settings.get('post_priority')))

@router.callback_query(F.data == "set_channel")
async def ask_for_channel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSettings.waiting_for_channel)
    await callback.message.edit_text(
        "Перешлите сюда любое сообщение из вашего канала (или напишите его ID).\n"
        "Не забудьте добавить бота в канал как администратора с правом отправки сообщений!",
        reply_markup=back_to_main_menu()
    )

@router.callback_query(F.data == "set_api")
async def ask_for_api(callback: CallbackQuery):
    settings = await get_admin_settings(callback.from_user.id)
    await callback.message.edit_text("Выберите источник API:", reply_markup=api_choice_menu(settings['api_source']))

@router.callback_query(F.data.startswith("api_choice_"))
async def set_api(callback: CallbackQuery):
    api = callback.data.removeprefix("api_choice_")
    await update_setting(callback.from_user.id, "api_source", api)
    await callback.answer(f"API изменено на {api}")
    await show_main_menu(callback.message, callback.from_user.id)

@router.callback_query(F.data == "set_tags")
async def ask_for_tags(callback: CallbackQuery, state: FSMContext):
    logging.info(f"HANDLER: Entered ask_for_tags for user {callback.from_user.id}.")
    await state.set_state(AdminSettings.waiting_for_tags)
    logging.info(f"HANDLER: State for user {callback.from_user.id} set to {await state.get_state()}.")
    settings = await get_admin_settings(callback.from_user.id)
    escaped_tags = html.escape(settings['tags'])
    await callback.message.edit_text(
        f"Текущие теги: <code>{escaped_tags}</code>\n\n"
        "Отправьте новые теги через запятую (например: cat, cute, solo)",
        parse_mode='HTML',
        reply_markup=back_to_main_menu()
    )

@router.callback_query(F.data == "set_negative_tags")
async def ask_for_neg_tags(callback: CallbackQuery, state: FSMContext):
    logging.info(f"HANDLER: Entered ask_for_neg_tags for user {callback.from_user.id}.")
    await state.set_state(AdminSettings.waiting_for_negative_tags)
    logging.info(f"HANDLER: State for user {callback.from_user.id} set to {await state.get_state()}.")
    settings = await get_admin_settings(callback.from_user.id)
    escaped_neg_tags = html.escape(settings['negative_tags'] or 'нет')
    await callback.message.edit_text(
        f"Текущие анти-теги: <code>{escaped_neg_tags}</code>\n\n"
        "Отправьте анти-теги через запятую (например: futanari, human)",
        parse_mode='HTML',
        reply_markup=back_to_main_menu()
    )

@router.callback_query(F.data == "set_interval")
async def ask_for_interval(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSettings.waiting_for_interval)
    settings = await get_admin_settings(callback.from_user.id)
    await callback.message.edit_text(
        f"Текущий интервал: {settings['post_interval_minutes']} минут.\n\n"
        "Отправьте новый интервал (в минутах, число от 5 до 1440).",
        reply_markup=back_to_main_menu()
    )
