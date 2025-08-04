# app/states/admin_states.py
from aiogram.fsm.state import State, StatesGroup

class AdminSettings(StatesGroup):
    choosing_channel = State()
    waiting_for_channel = State()
    waiting_for_tags = State()
    waiting_for_negative_tags = State()
    waiting_for_interval = State()
    waiting_for_default_caption = State()
    waiting_for_custom_caption = State()
    waiting_for_restore_file = State()

class WizardStates(StatesGroup):
    waiting_for_tags = State()
    waiting_for_negative_tags = State()
    waiting_for_interval = State()
    waiting_for_default_caption = State()