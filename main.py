import os
import re
import logging
import tempfile
import requests
import imageio_ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

WELCOME_TEXT = (
    "🎧 خوش اومدی به ربات رسمی DJ Ar3in!\n\n"
    "🎵 اسم آهنگ یا خواننده رو برام بفرست تا پیداش کنم.\n"
    "📸 یا لینک ریلز اینستاگرام رو بفرست تا اسم آهنگش رو پیدا کنم.\n"
    "🎤 برای رزرو دی‌جی از دستور /booking استفاده کن."
)

INSTAGRAM_LINK_PATTERN = re.compile(
    r"(https?://(www\.)?instagram\.com/(reel|p|tv)/[^\s]+)"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT)


async def booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎤 برای رزرو دی‌جی، لطفاً تاریخ، مکان و نوع رویداد رو برام بفرست."
    )


def search_itunes(query: str, limit: int = 5):
    try:
        url = "https://itunes.apple.com/search"
        params = {"term": query, "media": "music", "limit": limit}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except Exception as e:
        logger.error(f"iTunes search error: {e}")
        return []


def download_instagram_audio(url: str, out_path: str) -> bool:
    """Download the audio track of an Instagram reel/post."""
    try:
        import yt_dlp
    except ImportError:
        logger.error("yt-dlp is not installed")
        return False

    ydl_opts = {
        "format": "best",
        "outtmpl": out_path,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "postprocessors": [{"key": "FFmpegExtractAudio"}],
        "keepvideo": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        logger.error(f"yt-dlp download error: {e}")
        return False


def recognize_song_with_audd(file_path: str):
    """Send an audio file to AudD and return the recognition result."""
    if not AUDD_API_TOKEN:
        logger.error("AUDD_API_TOKEN is not set")
        return None

    url = "https://api.audd.io/"
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {
                "api_token": AUDD_API_TOKEN,
                "return": "apple_music,spotify",
            }
            resp = requests.post(url, data=data, files=files, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get("status") == "success" and result.get("result"):
            return result["result"]
        return None
    except Exception as e:
        logger.error(f"AudD recognition error: {e}")
        return None


async def handle_instagram_link(update: Update, context: ContextTypes.DEFAULT_TYPE, link: str):
    status_msg = await update.message.reply_text("🔎 در حال بررسی لینک...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_template = os.path.join(tmp_dir, "reel_audio.%(ext)s")
        ok = download_instagram_audio(link, out_template)

        if not ok:
            await status_msg.edit_text("😔 لینک خصوصی یا نامعتبر باشه.")
            return

        audio_file = None
        for fname in os.listdir(tmp_dir):
            if fname.endswith(".mp3"):
                audio_file = os.path.join(tmp_dir, fname)
                break

        for fname in os.listdir(tmp_dir):
            if fname.endswith((".mp4", ".mov", ".mkv", ".webm")):
                video_file = os.path.join(tmp_dir, fname)
                try:
                    with open(video_file, "rb") as vf:
                        await context.bot.send_video(chat_id=update.effective_chat.id, video=vf)
                except Exception as e:
                    logger.error(f"Failed to send video: {e}")

        if not audio_file:
            await status_msg.edit_text("😔 صوتی پیدا نشد.")
            return

        result = recognize_song_with_audd(audio_file)

        if not result:
            await status_msg.edit_text("😔 آهنگ تو ریلز واضح نبود.")
            return

        song_name = result.get("title", "نامشخص")
        artist = result.get("artist", "نامشخص")
        apple_music = result.get("apple_music", {}) or {}
        spotify = result.get("spotify", {}) or {}

        caption = f"🎵 {song_name}\n🎤 {artist}"

        buttons = []
        if apple_music.get("url"):
            buttons.append([InlineKeyboardButton("🍎 Apple Music", url=apple_music["url"])])
        if spotify.get("external_urls", {}).get("spotify"):
            buttons.append([InlineKeyboardButton("🎧 Spotify", url=spotify["external_urls"]["spotify"])])
        markup = InlineKeyboardMarkup(buttons) if buttons else None

        await status_msg.edit_text(caption, reply_markup=markup)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if not query:
        return

    match = INSTAGRAM_LINK_PATTERN.search(query)
    if match:
        await handle_instagram_link(update, context, match.group(1))
        return

    await update.message.reply_text(f"🔍 در حال جستجوی «{query}»...")

    results = search_itunes(query)
    if not results:
        await update.message.reply_text("😔 چیزی پیدا نشد، اسم دقیق‌تری امتحان کن.")
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
                await update.message.reply_audio(audio=preview_url)
            except Exception as e:
                logger.error(f"Error sending preview: {e}")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("booking", booking))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
