from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from typing import List, Dict
from aiogram import Bot
from app.keyboards.callback_data import (
    ChannelCallback,
    SettingsCallback,
    ApiCallback,
    PriorityCallback,
    TagsModeCallback,
    MenuCallback,
    WizardCallback
)

PRIORITY_TEXT = {
    'random': '🎲 Случайный',
    'newest': '✨ Новые (приоритет)',
    'oldest': '⏳ Старые (приоритет)',
    'most_popular': '🔥 Популярные (приоритет)',
    'least_popular': '👀 Непопулярные (приоритет)'
}

async def channels_menu(channels: List[Dict], bot: Bot):
    builder = InlineKeyboardBuilder()
    for channel in channels:
        try:
            chat = await bot.get_chat(channel['channel_id'])
            title = chat.title or f"ID: {channel['channel_id']}"
        except Exception:
            title = f"ID: {channel['channel_id']}"
        builder.row(InlineKeyboardButton(
            text=f"📢 {title}", 
            callback_data=ChannelCallback(action="select", channel_id=channel['channel_id']).pack()
        ))
    builder.row(InlineKeyboardButton(
        text="➕ Добавить канал", 
        callback_data=MenuCallback(action="add_channel").pack()
    ))
    return builder.as_markup()

def channel_settings_menu(settings: dict):
    builder = InlineKeyboardBuilder()
    channel_id = settings['channel_id']
    status = "✅ Включен" if settings['is_active'] else "❌ Выключен"
    action_callback = "stop" if settings['is_active'] else "start"
    
    builder.row(InlineKeyboardButton(
        text=f"Статус: {status}", 
        callback_data=SettingsCallback(action=action_callback, channel_id=channel_id).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="⚙️ Настройки Постинга", 
        callback_data=SettingsCallback(action="open_posting_settings", channel_id=channel_id).pack()
    ))
    builder.row(
        InlineKeyboardButton(text="🏷️ Теги", callback_data=SettingsCallback(action="set_tags", channel_id=channel_id).pack()),
        InlineKeyboardButton(text="🚫 Анти-теги", callback_data=SettingsCallback(action="set_negative_tags", channel_id=channel_id).pack())
    )
    builder.row(
        InlineKeyboardButton(text=f"🌐 API: {settings['api_source']}", callback_data=SettingsCallback(action="set_api", channel_id=channel_id).pack()),
        InlineKeyboardButton(text=f"⏳ Интервал: {settings['post_interval_minutes']} мин.", callback_data=SettingsCallback(action="set_interval", channel_id=channel_id).pack())
    )
    builder.row(InlineKeyboardButton(
        text="📝 Шаблон сообщения", 
        callback_data=SettingsCallback(action="set_default_caption", channel_id=channel_id).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="🗑️ Удалить канал", 
        callback_data=ChannelCallback(action="delete", channel_id=channel_id).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="⬅️ К списку каналов", 
        callback_data=MenuCallback(action="back_to_channels").pack()
    ))
    return builder.as_markup()

def posting_settings_menu(settings: dict):
    builder = InlineKeyboardBuilder()
    channel_id = settings['channel_id']
    tags_mode = settings.get('tags_mode', 'AND')
    priority_mode = settings.get('post_priority', 'random')
    
    tags_mode_text = "Логика тегов: ИЛИ (OR)" if tags_mode == 'OR' else "Логика тегов: И (AND)"
    priority_text = f"Приоритет: {PRIORITY_TEXT.get(priority_mode)}"
    
    builder.row(InlineKeyboardButton(
        text=tags_mode_text, 
        callback_data=TagsModeCallback(channel_id=channel_id).pack()
    ))
    builder.row(InlineKeyboardButton(
        text=priority_text, 
        callback_data=SettingsCallback(action="open_priority_menu", channel_id=channel_id).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад", 
        callback_data=ChannelCallback(action="select", channel_id=channel_id).pack()
    ))
    return builder.as_markup()

def priority_choice_menu(current_priority: str, channel_id: int):
    builder = InlineKeyboardBuilder()
    for priority_key, priority_value in PRIORITY_TEXT.items():
        text = f"✅ {priority_value}" if priority_key == current_priority else priority_value
        builder.add(InlineKeyboardButton(
            text=text, 
            callback_data=PriorityCallback(priority=priority_key, channel_id=channel_id).pack()
        ))
    
    builder.adjust(2)
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад в настройки", 
        callback_data=SettingsCallback(action="open_posting_settings", channel_id=channel_id).pack()
    ))
    return builder.as_markup()

def api_choice_menu(current_api: str, channel_id: int):
    builder = InlineKeyboardBuilder()
    apis = ['e621', 'rule34']
    for api in apis:
        text = f"✅ {api}" if api == current_api else api
        builder.add(InlineKeyboardButton(
            text=text, 
            callback_data=ApiCallback(api_source=api, channel_id=channel_id).pack()
        ))
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад", 
        callback_data=ChannelCallback(action="select", channel_id=channel_id).pack()
    ))
    return builder.as_markup()

def confirm_delete_menu(channel_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, удалить", 
            callback_data=ChannelCallback(action="confirm_delete", channel_id=channel_id).pack()
        ),
        InlineKeyboardButton(
            text="❌ Нет, отмена", 
            callback_data=ChannelCallback(action="select", channel_id=channel_id).pack()
        )
    )
    return builder.as_markup()

def back_to_main_menu(channel_id: int):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад", 
        callback_data=ChannelCallback(action="select", channel_id=channel_id).pack()
    ))
    return builder.as_markup()

def skip_keyboard(step: str):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="Пропустить",
        callback_data=WizardCallback(action="skip", step=step).pack()
    ))
    return builder.as_markup()