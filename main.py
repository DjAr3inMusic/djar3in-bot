import os
import re
import logging
import tempfile
import requests
import imageio_ffmpeg
from urllib.parse import quote
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
    "🎵 اسم آهنگ یا خواننده رو برام بفرست تا کاملشو برات پیدا کنم.\n"
    "📸 یا لینک ریلز اینستاگرام رو بفرست تا اسم آهنگش رو پیدا کنم.\n"
    "🎤 برای رزرو دی‌جی از دستور /booking استفاده کن."
)

INSTAGRAM_LINK_PATTERN = r
