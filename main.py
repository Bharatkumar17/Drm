import os
import re
import sys
import m3u8
import json
import time
import pytz
import asyncio
import requests
import subprocess
import urllib
import urllib.parse
import yt_dlp
import tgcrypto
import cloudscraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64encode, b64decode
from logs import logging
from bs4 import BeautifulSoup
import saini as helper
from utils import progress_bar
from vars import API_ID, API_HASH, BOT_TOKEN, OWNER, CREDIT, AUTH_USERS
from aiohttp import ClientSession
from subprocess import getstatusoutput
from pytube import YouTube
from aiohttp import web
import random
from pyromod import listen
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid
from pyrogram.types.messages_and_media import message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiohttp
import aiofiles
import zipfile
import shutil
import ffmpeg
from collections import deque

# Initialize the bot
bot = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ==================== NEW FEATURES ====================
# 1. Download queue system
download_queue = deque()
current_downloads = {}
MAX_CONCURRENT_DOWNLOADS = 3  # Limit concurrent downloads

# 2. Error tracking dictionary
error_tracker = {}

# 3. Instagram download function
async def download_instagram(url, quality):
    ydl_opts = {
        'format': f'bestvideo[height<={quality}]+bestaudio/best' if quality != '0' else 'best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'retries': 3,
        'fragment_retries': 3,
        'skip_unavailable_fragments': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, "Failed to extract video info"
                
            filename = ydl.prepare_filename(info)
            return filename, None
    except yt_dlp.utils.DownloadError as e:
        return None, f"Instagram download error: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"

# 4. Process download queue
async def process_queue():
    while download_queue:
        if len(current_downloads) >= MAX_CONCURRENT_DOWNLOADS:
            await asyncio.sleep(5)
            continue
            
        chat_id, url, quality, message = download_queue.popleft()
        current_downloads[chat_id] = True
        
        try:
            # Instagram handling
            if "instagram.com" in url:
                await message.edit("🔄 Downloading Instagram content...")
                file_path, error = await download_instagram(url, quality)
                
                if error:
                    await message.edit(f"❌ Instagram download failed:\n{error}")
                elif file_path:
                    await message.edit("📤 Uploading Instagram content...")
                    await bot.send_video(
                        chat_id=chat_id,
                        video=file_path,
                        caption=f"📸 Instagram Content\n🔄 Downloaded via @{bot.me.username}"
                    )
                    os.remove(file_path)
                    await message.delete()
            else:
                # Existing download logic
                await handle_download(chat_id, url, quality, message)
                
        except Exception as e:
            await message.edit(f"⚠️ Download failed:\n{str(e)}")
        finally:
            current_downloads.pop(chat_id, None)
            await asyncio.sleep(1)

# 5. Enhanced Classplus DRM handling
def fix_classplus_drm(url):
    # Improved error handling for Classplus URLs
    try:
        if "classplusapp.com/drm/" in url:
            fixed_url = 'https://dragoapi.vercel.app/classplus?link=' + url
            response = requests.get(fixed_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('mpd'), data.get('keys', [])
            else:
                raise Exception(f"Classplus API failed: {response.status_code}")
        return url, []
    except Exception as e:
        logging.error(f"Classplus DRM fix error: {str(e)}")
        return url, []

# ==================== MODIFIED EXISTING CODE ====================
# ... [REST OF YOUR ORIGINAL CODE REMAINS THE SAME UNTIL THE TEXT HANDLER] ...

@bot.on_message(filters.command(["insta", "instagram"]) & filters.private)
async def insta_handler(client: Client, message: Message):
    if not message.text.split(" ", 1)[1:]:
        return await message.reply_text("Please provide an Instagram URL\nExample: /insta https://www.instagram.com/p/Cxample/")
    
    url = message.text.split(" ", 1)[1]
    editable = await message.reply_text("🔄 Processing Instagram link...")
    
    # Add to queue
    download_queue.append((message.chat.id, url, '1080', editable))
    await editable.edit(f"📥 Added to queue. Position: {len(download_queue)}")
    
    # Start processing if not already running
    if not current_downloads:
        asyncio.create_task(process_queue())

@bot.on_message(filters.text & filters.private)
async def text_handler(bot: Client, m: Message):
    # ... [EXISTING CODE] ...
    
    # Inside the main download logic, add queue support:
    editable = await m.reply_text(f"<pre><code>**🔹Processing your link...\n🔁Please wait...⏳**</code></pre>")
    
    # Add to queue instead of processing immediately
    download_queue.append((m.chat.id, link, raw_text2, editable))
    await editable.edit(f"📥 Added to queue. Position: {len(download_queue)}")
    
    # Start processing if not already running
    if not current_downloads:
        asyncio.create_task(process_queue())

# Modified DRM handling in existing flow
async def handle_download(chat_id, url, quality, message):
    # ... [EXISTING DOWNLOAD LOGIC] ...
    
    # FIXED CLASSPLUS DRM HANDLING
    elif "classplusapp.com/drm/" in url:
        try:
            mpd, keys = fix_classplus_drm(url)
            keys_string = " ".join([f"--key {key}" for key in keys])
            # Continue with decryption...
        except Exception as e:
            await message.edit(f"❌ Classplus DRM error:\n{str(e)}")
            return
    
    # ... [REST OF DOWNLOAD LOGIC] ...
    
    # ENHANCED ERROR HANDLING
    try:
        # Download logic here...
        pass
    except requests.exceptions.RequestException as e:
        error_type = "Connection Error"
    except yt_dlp.utils.DownloadError as e:
        error_type = "Download Failed"
    except Exception as e:
        error_type = "Unexpected Error"
    
    # Track errors
    error_tracker.setdefault(error_type, 0)
    error_tracker[error_type] += 1
    
    # Send detailed error
    await message.edit(f"""
⚠️ **Download Failed**
• URL: `{url}`
• Error Type: {error_type}
• Details: {str(e)[:200]}
""")

# ==================== NEW ERROR REPORTING COMMAND ====================
@bot.on_message(filters.command("errors") & filters.private)
async def error_report_handler(client: Client, m: Message):
    if not error_tracker:
        return await m.reply_text("✅ No errors recorded yet!")
    
    report = "📊 **Error Report**\n"
    for error_type, count in error_tracker.items():
        report += f"• {error_type}: {count} errors\n"
    
    report += f"\nTotal Errors: {sum(error_tracker.values())}"
    await m.reply_text(report)

# ... [REST OF YOUR ORIGINAL CODE] ...

bot.run()
