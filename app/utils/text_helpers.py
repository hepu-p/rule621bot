# app/utils/text_helpers.py
import re

def escape_md_v2(text: str) -> str:
    """
    Экранирует специальные символы для Telegram MarkdownV2.
    """
    escape_chars = r"[_*```math```()~`>#+-=|{}.!]"
    return re.sub(f'({escape_chars})', r'\\\1', text)
                  
