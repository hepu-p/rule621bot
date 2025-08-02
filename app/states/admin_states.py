# app/states/admin_states.py
from aiogram.fsm.state import State, StatesGroup

class AdminSettings(StatesGroup):
    waiting_for_channel = State()
    waiting_for_tags = State()
    waiting_for_negative_tags = State()
    waiting_for_interval = State()
