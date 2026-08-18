import os
import re
import logging
import requests
import yt_dlp
import imageio_ffmpeg

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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
# Optional: path to a cookies.txt file (Netscape format) to help yt-dlp bypass
# YouTube's "Sign in to confirm you're not a bot" wall. Not required, but if
# downloads keep failing this is usually the fix. Set the COOKIES_FILE env var
# on Railway to the path of an uploaded cookies file if needed.
COOKIES_FILE = os.environ.get("COOKIES_FILE")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set.")

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

INSTAGRAM_REGEX = re.compile(
    r"(https?://(?:www\.)?instagram\.com/(?:reel|p|reels)/[^\s]+)"
)

# -----------------------------------------------------------------------
# Ethnic / regional keyword map
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
# Ethnic singer lists (for the inline-keyboard browsing feature)
# -----------------------------------------------------------------------

ETHNIC_SINGERS = {
    "بندری": [
        "مهران میررستمی", "مرشد میررستمی", "محسن فیروزیان", "حمیدرضا ذاکری",
        "فیصل و مروان اسماعیلی", "همت و حشمت لشکری", "شاهرخ غلامی", "محمدامین مؤمن‌زاده",
        "دانیال درگ", "غلامحسین نظری", "ناصر عبداللهی", "فرامرز صالحی",
        "علی موسی‌زاده", "علی محبوب", "علی باقری", "امیرارسلان صالحی‌زاده",
        "محمد منصور", "محمد روهنده", "مرتضی شعمیر", "آرش کارکن",
        "معین علی‌نسب", "جاوید سفالگر", "احمد جمشید", "مصطفی جهانگیری",
        "آلوین مقدم", "مهرشاد", "ناصر زرجام", "احمد رضایی",
        "محمد عیسی قادری", "عارف شاکری", "ایوب گلزاری", "مجتبی تابدار",
        "محسن باغی", "احمد قائد", "احمد پاداش", "مهرزاد نوازنده",
        "محمد بهرامی", "محمد کیانفر", "محسن ناصری", "میثم نظری",
        "موسی نظری", "ابراهیم آروین", "پویا پاسلار", "هادی صدری",
        "فرشاد افرا", "عقیل رحیمی", "موسی لبنانی", "فاطمه سوئیتی",
        "قنبر نارویی", "حبیب قلندری", "یاسین شهریاری", "فرزاد بخرد",
        "غلام مارگیری", "اسلام نظری", "وحید آور", "یونس توکلی",
        "ایمان سیاهپوشان", "بهروز سکتور", "مجید یحیایی", "محمود جهان",
        "سعید شنبه‌زاده", "علیرضا آرمین", "علی آرامی",
    ],
    "ترکی_آذری": [
        "رحیم شهریاری", "رحیم مؤذن‌زاده اردبیلی", "ودود مؤذن‌زاده اردبیلی",
        "سلیم مؤذن‌زاده اردبیلی", "پیمان تبریزی", "سخاوت ممدو",
        "افشین اسدی", "سجاد آراسته", "افشین آذری", "علی پرمهر",
        "کاظم معرفت", "امیر ارونقی", "هوشنگ آذراوغلو", "اصغر صفی‌پور",
    ],
    "کردی": [
        "حمید حمیدی", "ناصر رزازی", "حسن زیرک", "محسن لرستانی",
        "حسین صفامنش", "مهستی", "احمد نازدار", "عبدالله پرتوانداز",
        "فردین ملاسلیمی", "هیبت محمدی", "شاکر ساعدی", "میلاد ستاره",
        "کاوه مرادی", "کیوان مرادی", "آشنا رحمت‌الهی", "ادریس مریوانی",
        "آزاد رضایی", "افشین حمه‌ویسی", "بهزاد سواری", "آوات بوکانی",
        "عثمان هورامی", "رامین کرمی", "یاسر امیری‌فر", "رامین تجنگی",
        "فرهاد خزایی", "علی احمدیانی", "محمد لیام", "امیر لیام",
        "حمیدرضا بابایی", "روح‌الله کرمی", "میلاد غلامی", "علیرضا رنگرز",
        "فرهاد فرهادی", "عسکر قربانی", "شهاب مرادیان", "غلام ملکشاهی",
        "محمد ماملی", "مظهر خالقی", "علی مردان", "سیدعلی‌اصغر کردستانی",
        "کریم کابان", "طاهر توفیق", "شوان پرور", "محمد جزا",
        "رضا سقایی", "عزیز ویسی", "عادل هورامی", "جواد رضایی",
    ],
    "لری": [
        "سعید حسینی", "رضا سقایی", "ایرج رحمان‌پور", "مصطفی صوفی‌زاده",
        "غلامرضا طوسی", "محسن اسفندیاری", "منوچهر زنگنه", "امید محمودی",
        "شروین پناهی", "سجاد رزمجو", "فریدون آسرایی", "احمد بیرانوند",
        "هومن پناهی", "قاسم فاضلی", "علی شهرآبادی", "یونس بخرد",
        "احمد فتحی", "محسن نصری", "علی پاپی", "دیدار محمودی",
        "بهمن اسکینی", "سجاد اسکینی", "عباس محمدی تیام", "حمزه بیرانوند",
        "میلاد بیرانوند", "محمد میرزاوندی", "سیف‌الدین آشتیانی",
        "مسعود بختیاری", "حشمت رجب‌زاده", "داریوش نظری", "فرج علیپور",
        "اسفندیار رنجبری", "آستاره بختیاری", "رضا صالحی",
    ],
    "عربی": [
        "مهدی الزایری", "عباس سحاگی", "علوان الشویع", "عبدالامیر ادریس",
        "حمدی صالح", "احمد کنعانی", "خضیر ابو عنب", "ضاحی الاهوازی",
        "حسین الاهوازی", "احمد ماها",
    ],
    "بلوچی": [
        "کمال خان هوت", "عارف بلوچ", "خالد راوین", "محمدرضا میر",
        "اسحاق شهریاری", "رستم میرلاشاری", "بهروز شبستری", "عبداله صالح‌زهی",
        "دین محمد زنگشاهی", "علی محمد بلوچ", "سهیل حسین‌زهی", "محمد مجاهد",
        "خدانظر بلوچ", "عابد رییسی", "حسن براهویی", "وحید فرزانه",
        "شبیر سید", "یاسر بلوچ‌اندیش", "عارف دهقان", "عبدالله موسی‌زهی",
        "عرفان طهماسبی", "نوری رخشانی", "عیسی همراز", "عیسی رند",
    ],
    "گیلکی": [
        "ناصر وحدتی", "صادق بوقی", "آرمین نصرتی", "فرامرز دعایی",
        "فرامرز محجوب", "مسعود درویش",
    ],
    "مازندرانی": [
        "ابی عالی", "جواد یساری", "محمد اسمعلی", "کیوان محمدی",
        "عماد رام", "نادیا رام", "مهدی احمدزاده", "جهانبخش کرد",
        "عباد محمدی", "رضا کورد", "مهرشاد مهاجر",
    ],
    "ترکمن": [
        "عباس نظافت", "پلوان حالمیرادف", "عثمان نوروزف",
        "خلیفه نظرلی محجوبی", "اخلاص دادایف", "جلیل ماهرخ",
    ],
}

SINGERS_PER_PAGE = 8


# -----------------------------------------------------------------------
# /start and /booking commands
# -----------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "سلام 👋 به ربات DJ Ar3in خوش اومدی!\n\n"
        "🎵 اسم آهنگ مورد نظرت رو برام بفرست تا برات پیدا و ارسالش کنم.\n"
        "🎬 یا لینک ریل اینستاگرام رو بفرست تا آهنگش رو برات تشخیص بدم.\n"
        "🎤 با دستور /singers می‌تونی خواننده‌های محلی هر قومیت رو ببینی.\n\n"
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
# Ethnic singer browsing (inline keyboard)
# -----------------------------------------------------------------------

def build_ethnics_keyboard():
    keyboard = []
    row = []
    for ethnic in ETHNIC_SINGERS.keys():
        row.append(InlineKeyboardButton(ethnic, callback_data=f"ethnic:{ethnic}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


async def singers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 یک قومیت رو انتخاب کن:",
        reply_markup=build_ethnics_keyboard(),
    )


async def ethnic_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    ethnic = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0

    singers = ETHNIC_SINGERS.get(ethnic, [])
    start_idx = page * SINGERS_PER_PAGE
    end_idx = start_idx + SINGERS_PER_PAGE
    page_singers = singers[start_idx:end_idx]

    keyboard = []
    row = []
    for singer in page_singers:
        row.append(InlineKeyboardButton(singer, callback_data=f"singer:{ethnic}:{singer}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_row = []
    if start_idx > 0:
        nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"ethnic:{ethnic}:{page-1}"))
    if end_idx < len(singers):
        nav_row.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"ethnic:{ethnic}:{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🔙 بازگشت به قومیت‌ها", callback_data="back_to_ethnics")])

    await query.edit_message_text(
        f"🎤 خواننده‌های {ethnic} رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def _extract_tracks_from_search(query: str):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    if COOKIES_FILE:
        ydl_opts["cookiefile"] = COOKIES_FILE
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        entries = info.get("entries", []) if info else []
        tracks = []
        for e in entries:
            if not e:
                continue
            title = e.get("title", "").strip()
            vid_id = e.get("id")
            url = e.get("url")
            if url and not url.startswith("http"):
                # extract_flat sometimes returns just the video id in "url"
                url = f"https://www.youtube.com/watch?v={url}"
            if not url and vid_id:
                url = f"https://www.youtube.com/watch?v={vid_id}"
            if url and title:
                tracks.append({"title": title, "url": url, "id": vid_id})
        return tracks


def search_singer_tracks(singer: str, limit: int = 8):
    """Search YouTube (then SoundCloud as fallback) for tracks by this singer."""
    try:
        tracks = _extract_tracks_from_search(f"ytsearch{limit}:{singer}")
        if tracks:
            return tracks
    except Exception as e:
        logger.error(f"YouTube track search error for {singer}: {e}")

    try:
        tracks = _extract_tracks_from_search(f"scsearch{limit}:{singer}")
        if tracks:
            return tracks
    except Exception as e:
        logger.error(f"SoundCloud track search error for {singer}: {e}")

    return []


async def singer_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, ethnic, singer = query.data.split(":", 2)

    await query.edit_message_text(f"🔎 در حال پیدا کردن آهنگ‌های {singer}...")

    tracks = search_singer_tracks(singer)

    if not tracks:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"😕 آهنگی از {singer} پیدا نشد.",
        )
        return

    context.user_data[f"tracks_{singer}"] = tracks
    context.user_data[f"singer_name_{singer}"] = singer

    keyboard = []
    for i, track in enumerate(tracks):
        title = track["title"]
        if len(title) > 40:
            title = title[:40] + "..."
        keyboard.append([InlineKeyboardButton(f"🎵 {title}", callback_data=f"track:{singer}:{i}")])

    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"ethnic:{ethnic}")])

    await query.edit_message_text(
        f"🎶 آهنگ‌های {singer} رو انتخاب کن:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def download_track_with_fallback(track: dict, singer: str, output_base: str):
    """Try several strategies to fetch the actual audio for a chosen track.
    Returns yt-dlp info dict on success, or None if every attempt failed."""
    mp3_path = output_base + ".mp3"

    attempts = []

    # 1) The exact URL/id we found during the search step.
    direct_target = track.get("url") or track.get("id")
    if direct_target:
        attempts.append(("direct link", direct_target, "ytsearch1"))

    # 2) Re-search YouTube using "singer - title" (helps when the direct
    #    link from extract_flat was stale, region-blocked, or malformed).
    title = track.get("title", "")
    if title:
        attempts.append(("youtube re-search", f"{singer} {title}", "ytsearch1"))

    # 3) Re-search YouTube using just the title (sometimes the singer name
    #    duplicated in the query causes zero results).
    if title:
        attempts.append(("youtube title-only", title, "ytsearch1"))

    # 4) Fall back to SoundCloud with singer + title.
    if title:
        attempts.append(("soundcloud", f"{singer} {title}", "scsearch1"))

    for label, target, search_prefix in attempts:
        try:
            info = download_song(target, output_base, search_prefix)
            if info and os.path.exists(mp3_path):
                logger.info(f"Track download succeeded via {label}")
                return info
        except Exception as e:
            logger.error(f"Track download attempt '{label}' failed: {e}")
        finally:
            # Clean up any partial file before trying the next strategy.
            if os.path.exists(mp3_path) and not (os.path.getsize(mp3_path) > 0):
                os.remove(mp3_path)

    return None


async def track_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, singer, index_str = query.data.split(":", 2)
    index = int(index_str)

    tracks = context.user_data.get(f"tracks_{singer}", [])
    if index >= len(tracks):
        await context.bot.send_message(chat_id=query.message.chat_id, text="😕 این آهنگ دیگه در دسترس نیست.")
        return

    track = tracks[index]
    await query.edit_message_text(f"⏳ در حال دانلود «{track['title']}»...")

    unique_id = f"{query.message.message_id}_{index}"
    output_base = f"/tmp/{unique_id}"
    mp3_path = output_base + ".mp3"

    info = download_track_with_fallback(track, singer, output_base)

    if not info or not os.path.exists(mp3_path):
        await context.bot.send_message(chat_id=query.message.chat_id, text="😕 دانلود این آهنگ ممکن نشد.")
        return

    title = info.get("title", track["title"])
    uploader = info.get("uploader", "")
    caption = f"🎵 {title}"
    if uploader:
        caption += f"\n👤 {uploader}"

    try:
        with open(mp3_path, "rb") as audio_file:
            await context.bot.send_audio(chat_id=query.message.chat_id, audio=audio_file, title=title, caption=caption)
    except Exception as e:
        logger.error(f"Send track error: {e}")
        await context.bot.send_message(chat_id=query.message.chat_id, text="😕 مشکلی در ارسال فایل پیش اومد.")
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)


async def back_to_ethnics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🎵 یک قومیت رو انتخاب کن:",
        reply_markup=build_ethnics_keyboard(),
    )


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
        "geo_bypass": True,
        "retries": 3,
        "fragment_retries": 3,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    if search_prefix.startswith("ytsearch") or (isinstance(query, str) and "youtube.com" in query):
        # Trying multiple internal YouTube clients helps avoid the
        # "Sign in to confirm you're not a bot" wall that plain requests
        # sometimes hit.
        ydl_opts["extractor_args"] = {"youtube": {"player_client": ["android", "web"]}}
    if COOKIES_FILE:
        ydl_opts["cookiefile"] = COOKIES_FILE

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if "entries" in info:
            info = info["entries"][0]
        return info


async def download_and_send_song(message, song_name: str, unique_id: str) -> bool:
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

    group = detect_ethnic_group(song_name)
    if group:
        label, extra = group
        sources.append(("scsearch1", f"{song_name} {extra}", f"ساندکلاود {label}"))
        sources.append(("ytsearch1", f"{song_name} {extra}", f"یوتیوب {label}"))
    else:
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
            await message.reply_audio(audio=audio_file, title=title, caption=caption)
        return True
    except Exception as e:
        logger.error(f"Send audio error: {e}")
        return False
    finally:
        if os.path.exists(mp3_path):
            os.remove(mp3_path)


async def send_itunes_preview(message, context: ContextTypes.DEFAULT_TYPE, song_name: str):
    """Fallback: search iTunes for a short preview clip when full download fails."""
    await message.reply_text("🔎 در حال جستجوی پیش‌نمایش کوتاه...")

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
        await message.reply_text("😕 متأسفانه در حال حاضر امکان پیدا کردن این آهنگ نبود.")
        return

    results = data.get("results", [])
    if not results:
        await message.reply_text("😕 آهنگی با این نام پیدا نشد.")
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
            await message.reply_audio(
                audio=preview_url, title=title, performer=artist, caption=caption
            )
        except Exception as e:
            logger.error(f"Send preview error: {e}")
            await message.reply_text(caption)
    else:
        await message.reply_text(caption)


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
    if COOKIES_FILE:
        ydl_opts["cookiefile"] = COOKIES_FILE
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
        with open(video_path, "rb") as video_file:
            await update.message.reply_video(video=video_file)

        await update.message.reply_text("🎧 در حال شناسایی آهنگ...")
        song_info = recognize_song(video_path)

        if song_info:
            title = song_info.get("title", "نامشخص")
            artist = song_info.get("artist", "")
            caption = f"🎶 {title}"
            if artist:
                caption += f"\n👤 {artist}"
            await update.message.reply_text(caption)

            search_query = f"{artist} {title}".strip() if artist else title
            unique_id = f"{file_id}_song"
            success = await download_and_send_song(update.message, search_query, unique_id)
            if not success:
                await send_itunes_preview(update.message, context, search_query)
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

async def search_and_reply(message, context: ContextTypes.DEFAULT_TYPE, song_name: str):
    await message.reply_text(f"🔎🎵 در حال جستجو و دانلود آهنگ «{song_name}»...")

    unique_id = str(message.message_id)
    success = await download_and_send_song(message, song_name, unique_id)

    if not success:
        await message.reply_text("😕 دانلود کامل ممکن نشد، در حال ارسال پیش‌نمایش...")
        await send_itunes_preview(message, context, song_name)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()

    instagram_match = INSTAGRAM_REGEX.search(message_text)
    if instagram_match:
        await handle_instagram_link(update, context, instagram_match.group(1))
        return

    await search_and_reply(update.message, context, message_text)


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("booking", booking))
    application.add_handler(CommandHandler("singers", singers_command))
    application.add_handler(CallbackQueryHandler(ethnic_selected, pattern="^ethnic:"))
    application.add_handler(CallbackQueryHandler(singer_selected, pattern="^singer:"))
    application.add_handler(CallbackQueryHandler(track_selected, pattern="^track:"))
    application.add_handler(CallbackQueryHandler(back_to_ethnics, pattern="^back_to_ethnics$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot started polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
