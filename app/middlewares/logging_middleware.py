# app/middlewares/logging_middleware.py
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get('event_from_user')
        user_id = user.id if user else "N/A"

        log_message = f"Update from user {user_id}"

        if isinstance(event, Message):
            log_message += f" | Message: '{event.text}'"
        elif isinstance(event, CallbackQuery):
            log_message += f" | CallbackQuery: '{event.data}'"

        state: FSMContext = data.get('state')
        if state:
            current_state = await state.get_state()
            log_message += f" | FSM State: {current_state}"

        logger.info(log_message)

        try:
            return await handler(event, data)
        except Exception as e:
            logger.exception(f"Error during handling update from user {user_id}: {e}")
            raise
