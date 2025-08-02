# app/middlewares/logging_middleware.py
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.fsm.context import FSMContext

class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Получаем FSMContext, если он есть
        state: FSMContext = data.get('state')
        
        # Получаем информацию о пользователе
        user = data.get('event_from_user')
        user_id = user.id if user else "N/A"

        # Логируем тип события и текущее состояние FSM
        if state:
            current_state = await state.get_state()
            logging.info(
                f"MIDDLEWARE: New event of type '{type(event).__name__}' from user {user_id}. "
                f"Current FSM state: {current_state}"
            )
        else:
            logging.info(
                f"MIDDLEWARE: New event of type '{type(event).__name__}' from user {user_id}. "
                f"No FSM state in context."
            )
        
        # Передаем управление дальше по цепочке
        return await handler(event, data)
