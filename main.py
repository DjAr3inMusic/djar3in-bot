import os
import re
import logging
import requests
import yt_dlp
import imageio_ffmpeg

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
AUDD_API_TOKEN = os.environ.get("AUDD_API_TOKEN")

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

INSTAGRAM_REGEX = re.compile(r"(https?://(?:www\.)?instagram\.com/\S+)")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "سلام! به ربات DJ Ar3in Music خوش اومدی 🎧\n\n"
        "- اسم آهنگ بفرست تا برات پیدا کنم\n"
        "- لینک ریلز اینستاگرام بفرست تا صدا و اسم آهنگش رو بگیرم"
    )
    await update.message.reply_text(text)


def search_itunes(song_name: str):
    url = "https://itunes.apple.com/search"
    params = {"term": song_name, "media": "music", "limit": 5}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", [])


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()

    instagram_match = INSTAGRAM_REGEX.search(message_text)
    if instagram_match:
        await handle_instagram_link(update, context, instagram_match.group(1))
        return

    await search_and_reply(update, context, message_text)


async def search_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, song_name: str):
    await update.message.reply_text("در حال جستجو... 🔍")
    try:
        results = search_itunes(song_name)
    except Exception as e:
        logger.error(f"iTunes search error: {e}")
        await update.message.reply_text("خطا در جستجو، دوباره امتحان کن.")
        return

    if not results:
        await update.message.reply_text("چیزی پیدا نشد 😕")
        return

    for track in results:
        title = track.get("trackName", "نامشخص")
        artist = track.get("artistName", "نامشخص")
        preview_url = track.get("previewUrl")
        artwork = track.get("artworkUrl100")

        caption = f"🎵 {title}\n👤 {artist}"

        if preview_url:
            try:
                await update.message.reply_audio(
                    audio=preview_url,
                    title=title,
                    performer=artist,
                    caption=caption,
                )
            except Exception as e:
                logger.error(f"Send audio error: {e}")
                await update.message.reply_text(caption)
        else:
            await update.message.reply_text(caption)


def download_instagram_media(url: str, output_path: str):
    ydl_opts = {
        "outtmpl": output_path,
        "format": "best",
        "ffmpeg_location": FFMPEG_PATH,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def recognize_song(file_path: str):
    if not AUDD_API_TOKEN:
        return None

    with open(file_path, "rb") as f:
        files = {"file": f}
        data = {"api_token": AUDD_API_TOKEN, "return": "apple_music,spotify"}
        resp = requests.post("https://api.audd.io/", data=data, files=files, timeout=30)

    resp.raise_for_status()
    result = resp.json()

    if result.get("status") == "success" and result.get("result"):
        return result["result"]
    return None


async def handle_instagram_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    await update.message.reply_text("در حال دانلود... ⏳")

    file_id = str(update.message.message_id)
    video_path = f"/tmp/{file_id}.mp4"

    try:
        download_instagram_media(url, video_path)
    except Exception as e:
        logger.error(f"Download error: {e}")
        await update.message.reply_text("دانلود ناموفق بود 😕")
        return

    if not os.path.exists(video_path):
        await update.message.reply_text("فایل پیدا نشد، دوباره امتحان کن.")
        return

    try:
        with open(video_path, "rb") as video_file:
            await update.message.reply_video(video=video_file)
    except Exception as e:
        logger.error(f"Send video error: {e}")

    try:
        song_info = recognize_song(video_path)
        if song_info:
            title = song_info.get("title", "نامشخص")
            artist = song_info.get("artist", "نامشخص")
            await update.message.reply_text(f"🎵 {title}\n👤 {artist}")
        else:
            await update.message.reply_text("آهنگ شناسایی نشد 🙁")
    except Exception as e:
        logger.error(f"Recognition error: {e}")
        await update.message.reply_text("خطا در شناسایی آهنگ.")

    if os.path.exists(video_path):
        os.remove(video_path)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("در حال شناسایی آهنگ... 🎧")

    audio = update.message.voice or update.message.audio
    if not audio:
        return

    file = await context.bot.get_file(audio.file_id)
    file_path = f"/tmp/{audio.file_id}.ogg"
    await file.download_to_drive(file_path)

    try:
        song_info = recognize_song(file_path)
        if song_info:
            title = song_info.get("title", "نامشخص")
            artist = song_info.get("artist", "نامشخص")
            await update.message.reply_text(f"🎵 {title}\n👤 {artist}")
        else:
            await update.message.reply_text("آهنگ شناسایی نشد 🙁")
    except Exception as e:
        logger.error(f"Recognition error: {e}")
        await update.message.reply_text("خطا در شناسایی آهنگ.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
