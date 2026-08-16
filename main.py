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

# -----------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
AUDD_API_TOKEN = os.environ.get("AUDD_API_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set.")

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

INSTAGRAM_REGEX = re.compile(
    r"(https?://(?:www\.)?instagram\.com/(?:reel|p|reels)/[^\s]+)"
)

# -----------------------------------------------------------------------
# Ethnic / regional keyword map
# Each entry: group_label -> (list of trigger keywords, extra search terms
# appended to the query to bias SoundCloud/YouTube search results)
# -----------------------------------------------------------------------

ETHNIC_KEYWORDS = {
    "بندری": {
        "triggers": [
            "بندری", "هرمزگان", "بندرعباس", "میناب", "بشاگرد", "قشم",
            "جاسک", "بندرلنگه", "رودان", "حاجی‌آباد", "بستک", "پارسیان",
            "خمیر", "سیریک", "ابوموسی",
        ],
        "extra": "آهنگ بندری هرمزگان",
    },
    "ترکی": {
        "triggers": [
            "ترکی", "آذری", "آذربایجان", "تبریز", "ارومیه", "اردبیل",
            "زنجان", "مراغه", "میانه", "خوی", "مرند", "اهر", "سراب",
        ],
        "extra": "آهنگ ترکی آذری",
    },
    "کردی": {
        "triggers": [
            "کردی", "کردستان", "سنندج", "کرمانشاه", "ایلام", "مریوان",
            "سقز", "بانه", "پاوه", "جوانرود", "بوکان", "مهاباد",
        ],
        "extra": "آهنگ کردی",
    },
    "لری": {
        "triggers": [
            "لری", "بختیاری", "لرستان", "خرم‌آباد", "بروجرد", "الیگودرز",
            "یاسوج", "چهارمحال", "شهرکرد", "اندیمشک",
        ],
        "extra": "آهنگ لری بختیاری",
    },
    "عربی": {
        "triggers": [
            "عربی", "خوزستانی", "خوزستان", "اهواز", "آبادان", "خرمشهر",
            "شادگان", "سوسنگرد", "هویزه", "دزفول", "شوشتر", "ماهشهر",
        ],
        "extra": "آهنگ عربی خوزستانی",
    },
    "بلوچی": {
        "triggers": [
            "بلوچی", "بلوچستان", "زاهدان", "چابهار", "ایرانشهر", "خاش",
            "سراوان", "نیکشهر", "کنارک", "سرباز", "راسک",
        ],
        "extra": "آهنگ بلوچی",
    },
    "گیلکی": {
        "triggers": [
            "گیلکی", "گیلان", "رشت", "انزلی", "لاهیجان", "لنگرود",
            "تالش", "آستارا", "صومعه‌سرا", "فومن",
        ],
        "extra": "آهنگ گیلکی رشت",
    },
    "مازندرانی": {
        "triggers": [
            "مازندرانی", "مازنی", "مازندران", "ساری", "آمل", "بابل",
            "قائم‌شهر", "بابلسر", "نور", "چالوس", "رامسر", "تنکابن",
        ],
        "extra": "آهنگ مازندرانی",
    },
    "ترکمن": {
        "triggers": [
            "ترکمنی", "ترکمن", "ترکمن‌صحرا", "گنبدکاووس", "گنبد کاووس",
            "بندرترکمن", "بندر ترکمن", "آق‌قلا", "آق قلا", "کلاله",
            "گمیش‌تپه", "گمیش تپه",
        ],
        "extra": "آهنگ ترکمنی",
    },
}


def detect_ethnic_group(song_name: str):
    """Check if the query mentions a region/ethnicity. Returns (label, extra) or None."""
    lowered = song_name.strip()
    for label, data in ETHNIC_KEYWORDS.items():
        for kw in data["triggers"]:
            if kw in lowered:
                return label, data["extra"]
    return None


# -----------------------------------------------------------------------
# /start and /booking commands
# -----------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "سلام 👋 به ربات DJ Ar3in خوش اومدی!\n\n"
        "🎵 اسم آهنگ مورد نظرت رو برام بفرست تا برات پیدا و ارسالش کنم.\n"
        "🎬 یا لینک ریل اینستاگرام رو بفرست تا آهنگش رو برات تشخیص بدم.\n\n"
        "برای رزرو دی‌جی از دستور /booking استفاده کن."
    )
    await update.message.reply_text(text)


async def booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📅 برای رزرو DJ Ar3in، لطفاً پیام بدید و جزئیات رویدادتون "
        "(تاریخ، مکان، نوع رویداد) رو براتون هماهنگ کنیم."
    )
    await update.message.reply_text(text)


# -----------------------------------------------------------------------
# Song search & download (SoundCloud -> YouTube -> regional fallback)
# -----------------------------------------------------------------------

def download_song(query: str, output_base: str, search_prefix: str):
    """Download a single track using yt-dlp with the given search engine prefix."""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_base + ".%(ext)s",
        "ffmpeg_location": FFMPEG_PATH,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "default_search": search_prefix,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if "entries" in info:
            info = info["entries"][0]
        return info


async def download_and_send_song(update: Update, song_name: str, unique_id: str) -> bool:
    """Try to download the full song (SoundCloud -> YouTube -> regional fallback) and send it.
    Returns True if a song was successfully sent, False otherwise."""
    output_base = f"/tmp/{unique_id}"
    mp3_path = output_base + ".mp3"

    info = None

    sources = [
        ("scsearch1", song_name, "ساندکلاود"),
        ("ytsearch1", f"{song_name} official audio", "یوتیوب"),
        ("ytsearch1", song_name, "یوتیوب"),
    ]

    # Regional/ethnic fallback: if the query mentions a specific region or
    # ethnicity, retry the search biased toward that group's music.
    group = detect_ethnic_group(song_name)
    if group:
        label, extra = group
        sources.append(("scsearch1", f"{song_name} {extra}", f"ساندکلاود {label}"))
        sources.append(("ytsearch1", f"{song_name} {extra}", f"یوتیوب {label}"))
    else:
        # Keep the original Bandari-specific fallback as a last resort
        sources.append(("scsearch1", f"{song_name} بندری", "ساندکلاود بندری"))
        sources.append(("ytsearch1", f"{song_name} آهنگ بندری هرمزگان بندرعباس", "یوتیوب بندری"))
        sources.append(("ytsearch1", f"{song_name} بندری میناب بشاگرد", "یوتیوب بندری"))

    for search_prefix, query, label in sources:
        try:
            info = download_song(query, output_base, search_prefix)
            if info and os.path.exists(mp3_path):
                break
            info = None
        except Exception as e:
            logger.error(f"{label} download error: {e}")
            info = None

    if not info or not os.path.exists(mp3_path):
        return False

    title = info.get("title", song_name)
    uploader = info.get("uploader", "")
    caption = f"🎵 {title}"
    if uploader:
        caption += f"\n👤 {uploader}"

    try:
        with open(mp3_path, "rb") as audio_file:
            await update.message.reply_audio(audio=audio_file, title=title, caption=caption)
        return True
    except Exception as e:
        logger.error(f"Send audio error: {e}")
        return False
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)


async def send_itunes_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, song_name: str):
    """Fallback: search iTunes for a short preview clip when full download fails."""
    await update.message.reply_text("🔎 در حال جستجوی پیش‌نمایش کوتاه...")

    try:
        resp = requests.get(
            "https://itunes.apple.com/search",
            params={"term": song_name, "media": "music", "limit": 1},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"iTunes search error: {e}")
        await update.message.reply_text("😕 متأسفانه در حال حاضر امکان پیدا کردن این آهنگ نبود.")
        return

    results = data.get("results", [])
    if not results:
        await update.message.reply_text("😕 آهنگی با این نام پیدا نشد.")
        return

    track = results[0]
    preview_url = track.get("previewUrl")
    title = track.get("trackName", song_name)
    artist = track.get("artistName", "")

    caption = f"🎵 {title}"
    if artist:
        caption += f"\n👤 {artist}"
    caption += "\n\n⚠️ فقط پیش‌نمایش کوتاه در دسترسه (یوتیوب فعلاً محدودیت داره)"

    if preview_url:
        try:
            await update.message.reply_audio(
                audio=preview_url, title=title, performer=artist, caption=caption
            )
        except Exception as e:
            logger.error(f"Send preview error: {e}")
            await update.message.reply_text(caption)
    else:
        await update.message.reply_text(caption)


# -----------------------------------------------------------------------
# Instagram reel download + song recognition (AudD)
# -----------------------------------------------------------------------

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
    """Send a media file to AudD to identify the song. Returns dict or None."""
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
    await update.message.reply_text("⏳ در حال دانلود...")

    file_id = str(update.message.message_id)
    video_path = f"/tmp/{file_id}.mp4"

    try:
        download_instagram_media(url, video_path)
    except Exception as e:
        logger.error(f"Download error: {e}")
        await update.message.reply_text("😕 دانلود ناموفق بود.")
        return

    if not os.path.exists(video_path):
        await update.message.reply_text("😕 فایل پیدا نشد، دوباره امتحان کنید.")
        return

    try:
        # Send the downloaded reel itself
        with open(video_path, "rb") as video_file:
            await update.message.reply_video(video=video_file)

        # Try to identify the song playing in it
        await update.message.reply_text("🎧 در حال شناسایی آهنگ...")
        song_info = recognize_song(video_path)

        if song_info:
            title = song_info.get("title", "نامشخص")
            artist = song_info.get("artist", "")
            caption = f"🎶 {title}"
            if artist:
                caption += f"\n👤 {artist}"
            await update.message.reply_text(caption)

            # Try to fetch and send the full track too
            search_query = f"{artist} {title}".strip() if artist else title
            unique_id = f"{file_id}_song"
            success = await download_and_send_song(update, search_query, unique_id)
            if not success:
                await send_itunes_preview(update, context, search_query)
        else:
            await update.message.reply_text("🙁 آهنگ شناسایی نشد")

    except Exception as e:
        logger.error(f"Process error: {e}")
        await update.message.reply_text("😕 مشکلی پیش اومد، دوباره امتحان کنید.")
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)


# -----------------------------------------------------------------------
# Text message router
# -----------------------------------------------------------------------

async def search_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, song_name: str):
    await update.message.reply_text(f"🔎🎵 در حال جستجو و دانلود آهنگ «{song_name}»...")

    unique_id = str(update.message.message_id)
    success = await download_and_send_song(update, song_name, unique_id)

    if not success:
        await update.message.reply_text("😕 دانلود کامل ممکن نشد، در حال ارسال پیش‌نمایش...")
        await send_itunes_preview(update, context, song_name)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()

    instagram_match = INSTAGRAM_REGEX.search(message_text)
    if instagram_match:
        await handle_instagram_link(update, context, instagram_match.group(1))
        return

    await search_and_reply(update, context, message_text)


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("booking", booking))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
