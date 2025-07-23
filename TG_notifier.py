from telegram import InputFile
from telegram.ext import ContextTypes
import io

__all__ = ["send_text", "send_photo"]

async def send_text(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, parse_mode: str = None, reply_markup=None):
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=reply_markup
    )

async def send_photo(context: ContextTypes.DEFAULT_TYPE, chat_id: int, image_buffer: io.BytesIO, caption: str = None, parse_mode: str = None):
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=InputFile(image_buffer, filename="chart.png"),
        caption=caption,
        parse_mode=parse_mode
    )
