import logging
import html
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import Update

class ErrorMiddleware(BaseMiddleware):
    def __init__(self, admin_ids: list[int]):
        self.admin_ids = admin_ids

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            logger = logging.getLogger(__name__)
            update_json = event.model_dump_json(indent=2, exclude_none=True)
            logger.exception(f"Caught exception in middleware: {e}. Update: {update_json}")

            # Notify admins about the error
            bot: Bot = data.get('bot')
            if bot:
                error_message = html.escape(str(e))
                update_details = html.escape(update_json)
                
                text = (
                    f"🚨 <b>Произошла ошибка в боте!</b>\n\n"
                    f"<b>Тип ошибки:</b>\n<pre>{html.escape(type(e).__name__)}</pre>\n\n"
                    f"<b>Сообщение об ошибке:</b>\n<pre>{error_message}</pre>\n\n"
                    f"<b>Детали обновления:</b>\n<pre>{update_details}</pre>"
                )

                for admin_id in self.admin_ids:
                    try:
                        # Split message if it's too long for Telegram
                        if len(text) > 4096:
                            # Truncate and close pre tag properly
                            truncated_text = text[:4090] + "...</pre>"
                            await bot.send_message(
                                admin_id,
                                truncated_text,
                                parse_mode='HTML'
                            )
                        else:
                            await bot.send_message(
                                admin_id,
                                text,
                                parse_mode='HTML'
                            )
                    except Exception as admin_notify_err:
                        logger.error(f"Failed to send error notification to admin {admin_id}: {admin_notify_err}")
            return None
