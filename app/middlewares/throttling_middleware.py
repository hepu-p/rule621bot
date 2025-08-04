import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message
from cachetools import TTLCache

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, ttl: float = 0.5):
        self.cache = TTLCache(maxsize=10_000, ttl=ttl)

    async def __call__(
        self, 
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        
        chat_id = event.chat.id
        
        if chat_id in self.cache:
            logger.warning(f"Throttling user {chat_id}. Event ignored.")
            return
        
        self.cache[chat_id] = None
        return await handler(event, data)