# app/keyboards/callback_data.py
from aiogram.filters.callback_data import CallbackData
from typing import Optional

class ChannelCallback(CallbackData, prefix="channel"):
    action: str  # e.g., select, delete, confirm_delete
    channel_id: int

class SettingsCallback(CallbackData, prefix="settings"):
    action: str  # e.g., toggle_status, set_tags, open_posting_settings
    channel_id: int

class ApiCallback(CallbackData, prefix="api"):
    api_source: str
    channel_id: int

class PriorityCallback(CallbackData, prefix="priority"):
    priority: str
    channel_id: int

class TagsModeCallback(CallbackData, prefix="tags_mode"):
    channel_id: int

class MenuCallback(CallbackData, prefix="menu"):
    action: str # e.g., add_channel, back_to_channels
    channel_id: Optional[int] = None

class WizardCallback(CallbackData, prefix="wizard"):
    action: str # e.g., skip
    step: str