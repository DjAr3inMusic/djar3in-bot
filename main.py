import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

WELCOME_TEXT = (
    "🎧 به ربات رسمی DJ Ar3in خوش اومدی!\n\n"
    "🎵 برای جستجوی آهنگ، اسم آهنگ یا خواننده رو برام بفرست.\n"
    "🎤 برای رزرو و بوکینگ دی‌جی، از /booking استفاده کن.\n"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT)


async def booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎤 برای رزرو، لطفاً اطلاعات زیر رو برام بفرست:\n"
        "- تاریخ مراسم\n- محل برگزاری\n- نوع مراسم\n- شماره تماس"
    )


def search_itunes(query: str, limit: int = 5):
    url = "https://itunes.apple.com/search"
    params = {"term": query, "media": "music", "limit": limit}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except Exception as e:
        logger.error(f"iTunes search error: {e}")
        return []


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        return

    await update.message.reply_text(f"🔍 در حال جستجوی «{query}»...")

    results = search_itunes(query)
    if not results:
        await update.message.reply_text(
            "متأسفانه چیزی پیدا نکردم 😔 لطفاً اسم دقیق‌تری امتحان کن."
        )
        return

    for track in results:
        song_name = track.get("trackName", "نامشخص")
        artist = track.get("artistName", "نامشخص")
        preview_url = track.get("previewUrl")
        artwork = track.get("artworkUrl100")
        itunes_link = track.get("trackViewUrl")

        caption = f"🎵 {song_name}\n🎤 {artist}"

        buttons = []
        if itunes_link:
            buttons.append([InlineKeyboardButton("🔗 لینک رسمی", url=itunes_link)])
        markup = InlineKeyboardMarkup(buttons) if buttons else None

        if artwork:
            await update.message.reply_photo(photo=artwork, caption=caption, reply_markup=markup)
        else:
            await update.message.reply_text(caption, reply_markup=markup)

        if preview_url:
            try:
                await update.message.reply_audio(audio=preview_url, title=song_name, performer=artist)
            except Exception as e:
                logger.error(f"Error sending preview: {e}")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set!")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("booking", booking))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
