# app/keyboards/inline.py
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton

# Словарь для красивого отображения приоритетов
PRIORITY_TEXT = {
    'random': '🎲 Случайный',
    'newest': '✨ Новые (приоритет)',
    'oldest': '⏳ Старые (приоритет)',
    'most_popular': '🔥 Популярные (приоритет)',
    'least_popular': '👀 Непопулярные (приоритет)'
}

def main_menu(settings: dict):
    """Главное меню настроек."""
    builder = InlineKeyboardBuilder()
    status = "✅ Включен" if settings['is_active'] else "❌ Выключен"
    action_callback = "stop" if settings['is_active'] else "start"
    
    if settings.get('channel_id'):
        builder.row(InlineKeyboardButton(text=f"Статус: {status}", callback_data=f"status_toggle_{action_callback}"))
    
    # Кнопка, ведущая в подменю настроек постинга
    builder.row(InlineKeyboardButton(text="⚙️ Настройки Постинга", callback_data="open_posting_settings"))
    
    builder.row(
        InlineKeyboardButton(text="🏷️ Теги", callback_data="set_tags"),
        InlineKeyboardButton(text="🚫 Анти-теги", callback_data="set_negative_tags")
    )
    builder.row(
        InlineKeyboardButton(text=f"📢 Канал: {settings['channel_id'] or 'Не задан'}", callback_data="set_channel"),
        InlineKeyboardButton(text=f"🌐 API: {settings['api_source']}", callback_data="set_api")
    )
    builder.row(InlineKeyboardButton(text=f"⏳ Интервал: {settings['post_interval_minutes']} мин.", callback_data="set_interval"))
    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_menu"))
    return builder.as_markup()

def posting_settings_menu(settings: dict):
    """Меню настроек логики постинга."""
    builder = InlineKeyboardBuilder()
    tags_mode = settings.get('tags_mode', 'AND')
    priority_mode = settings.get('post_priority', 'random')
    
    tags_mode_text = "Логика тегов: ИЛИ (OR)" if tags_mode == 'OR' else "Логика тегов: И (AND)"
    priority_text = f"Приоритет: {PRIORITY_TEXT.get(priority_mode)}"
    
    builder.row(InlineKeyboardButton(text=tags_mode_text, callback_data="switch_tags_mode"))
    builder.row(InlineKeyboardButton(text=priority_text, callback_data="open_priority_menu"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
    return builder.as_markup()

def priority_choice_menu(current_priority: str):
    """Меню выбора приоритета поста."""
    builder = InlineKeyboardBuilder()
    for priority_key, priority_value in PRIORITY_TEXT.items():
        text = f"✅ {priority_value}" if priority_key == current_priority else priority_value
        builder.add(InlineKeyboardButton(text=text, callback_data=f"set_priority_{priority_key}"))
    
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Назад в настройки", callback_data="open_posting_settings"))
    return builder.as_markup()

def api_choice_menu(current_api: str):
    builder = InlineKeyboardBuilder()
    apis = ['e621', 'rule34']
    for api in apis:
        text = f"✅ {api}" if api == current_api else api
        builder.add(InlineKeyboardButton(text=text, callback_data=f"api_choice_{api}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
    return builder.as_markup()

def back_to_main_menu():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
    return builder.as_markup()
