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
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiohttp
import aiofiles
import zipfile
import shutil
import ffmpeg
from collections import deque
from typing import Tuple, Optional, Dict, Deque

# Initialize the bot with better error handling
try:
    bot = Client(
        "bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        workers=100,
        max_concurrent_transmissions=5
    )
except Exception as e:
    logging.critical(f"Failed to initialize bot: {str(e)}")
    sys.exit(1)

# ==================== ENHANCED SYSTEM ====================
class DownloadSystem:
    def __init__(self):
        self.download_queue: Deque = deque()
        self.current_downloads: Dict[int, bool] = {}
        self.MAX_CONCURRENT_DOWNLOADS = 3
        self.error_tracker: Dict[str, int] = {}
        self.active_tasks = set()

    async def add_to_queue(self, chat_id: int, url: str, quality: str, message: Message) -> None:
        """Add download task to queue with proper validation"""
        if not self._validate_url(url):
            await message.edit("❌ Invalid URL provided")
            return

        self.download_queue.append((chat_id, url, quality, message))
        position = len(self.download_queue)
        await message.edit(f"📥 Added to queue. Position: {position}")

        if len(self.current_downloads) < self.MAX_CONCURRENT_DOWNLOADS:
            task = asyncio.create_task(self.process_queue())
            self.active_tasks.add(task)
            task.add_done_callback(self.active_tasks.discard)

    @staticmethod
    def _validate_url(url: str) -> bool:
        """Validate URLs before processing"""
        patterns = [
            r'https?://(www\.)?instagram\.com/',
            r'https?://(www\.)?youtube\.com/',
            r'https?://(www\.)?youtu\.be/',
            r'https?://(www\.)?classplusapp\.com/',
            # Add more patterns as needed
        ]
        return any(re.match(pattern, url) for pattern in patterns)

    async def process_queue(self) -> None:
        """Process download queue with enhanced error handling"""
        while self.download_queue:
            if len(self.current_downloads) >= self.MAX_CONCURRENT_DOWNLOADS:
                await asyncio.sleep(5)
                continue

            chat_id, url, quality, message = self.download_queue.popleft()
            self.current_downloads[chat_id] = True

            try:
                if "instagram.com" in url:
                    await self.handle_instagram(chat_id, url, quality, message)
                elif "classplusapp.com" in url:
                    await self.handle_classplus(chat_id, url, quality, message)
                else:
                    await self.handle_generic_download(chat_id, url, quality, message)
            except Exception as e:
                self._track_error(str(e))
                await message.edit(f"⚠️ Download failed:\n{str(e)[:500]}")
            finally:
                self.current_downloads.pop(chat_id, None)
                await asyncio.sleep(1)

    async def handle_instagram(self, chat_id: int, url: str, quality: str, message: Message) -> None:
        """Enhanced Instagram download handler"""
        await message.edit("🔄 Downloading Instagram content...")
        file_path, error = await self.download_instagram(url, quality)

        if error:
            await message.edit(f"❌ Instagram download failed:\n{error}")
        elif file_path:
            await message.edit("📤 Uploading Instagram content...")
            try:
                await self.upload_media(chat_id, file_path, "Instagram")
                await message.delete()
            except Exception as e:
                await message.edit(f"❌ Upload failed: {str(e)}")
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)

    async def download_instagram(self, url: str, quality: str) -> Tuple[Optional[str], Optional[str]]:
        """Improved Instagram download with retry logic"""
        ydl_opts = {
            'format': f'bestvideo[height<={quality}]+bestaudio/best' if quality != '0' else 'best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
            'extractor_args': {
                'instagram': {
                    'skip_auth': True,
                    'requested_clips': 1
                }
            }
        }

        for attempt in range(3):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        return None, "Failed to extract video info"
                    
                    filename = ydl.prepare_filename(info)
                    return filename, None
            except yt_dlp.utils.DownloadError as e:
                if attempt == 2:  # Last attempt
                    return None, f"Instagram download error: {str(e)}"
                await asyncio.sleep(2)
            except Exception as e:
                return None, f"Unexpected error: {str(e)}"

    async def handle_classplus(self, chat_id: int, url: str, quality: str, message: Message) -> None:
        """Advanced Classplus DRM handling"""
        await message.edit("🔒 Processing Classplus DRM content...")
        try:
            mpd_url, keys = self.fix_classplus_drm(url)
            if not mpd_url:
                raise Exception("Failed to process Classplus DRM")

            # Download and process the content
            await message.edit("⬇️ Downloading DRM content...")
            file_path = await self.download_drm_content(mpd_url, keys)
            
            await message.edit("📤 Uploading content...")
            await self.upload_media(chat_id, file_path, "Classplus")
            await message.delete()
        except Exception as e:
            await message.edit(f"❌ Classplus processing failed:\n{str(e)[:500]}")
        finally:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)

    def fix_classplus_drm(self, url: str) -> Tuple[Optional[str], list]:
        """Enhanced Classplus DRM fix with multiple fallback options"""
        try:
            if "classplusapp.com/drm/" not in url:
                return url, []

            # Try primary API
            primary_api = 'https://dragoapi.vercel.app/classplus?link='
            response = requests.get(primary_api + url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return data.get('mpd'), data.get('keys', [])

            # Fallback to secondary API
            secondary_api = 'https://classplus-drm-decryptor.herokuapp.com/?url='
            response = requests.get(secondary_api + url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return data.get('manifest_url'), data.get('keys', [])

            raise Exception(f"All DRM APIs failed. Last status: {response.status_code}")
        except Exception as e:
            logging.error(f"Classplus DRM error: {str(e)}")
            return None, []

    async def download_drm_content(self, mpd_url: str, keys: list) -> str:
        """Download and decrypt DRM content"""
        # Implement your DRM download and decryption logic here
        # This is a placeholder implementation
        output_path = f"downloads/drm_content_{int(time.time())}.mp4"
        
        # Example using yt-dlp with decryption keys
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'quiet': True,
            'allow_unplayable_formats': True,
            'external_downloader': 'ffmpeg',
            'external_downloader_args': {
                'ffmpeg_i': ['-keys', ' '.join(keys)] if keys else []
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([mpd_url])

        return output_path

    async def handle_generic_download(self, chat_id: int, url: str, quality: str, message: Message) -> None:
        """Handle generic downloads with progress tracking"""
        await message.edit("⬇️ Starting download...")
        try:
            # Implement your generic download logic here
            file_path = await self._download_generic(url, quality, message)
            
            await message.edit("📤 Uploading content...")
            await self.upload_media(chat_id, file_path, "Downloaded Content")
            await message.delete()
        except Exception as e:
            await message.edit(f"❌ Download failed:\n{str(e)[:500]}")
        finally:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)

    async def upload_media(self, chat_id: int, file_path: str, source: str) -> None:
        """Universal media uploader with type detection"""
        mime_type = await self._get_mime_type(file_path)
        
        if mime_type.startswith('video'):
            await bot.send_video(
                chat_id=chat_id,
                video=file_path,
                caption=f"🎬 {source} Content\n🔄 Downloaded via @{bot.me.username}",
                supports_streaming=True
            )
        elif mime_type.startswith('audio'):
            await bot.send_audio(
                chat_id=chat_id,
                audio=file_path,
                caption=f"🎵 {source} Audio\n🔄 Downloaded via @{bot.me.username}"
            )
        else:
            await bot.send_document(
                chat_id=chat_id,
                document=file_path,
                caption=f"📄 {source} File\n🔄 Downloaded via @{bot.me.username}"
            )

    @staticmethod
    async def _get_mime_type(file_path: str) -> str:
        """Detect file MIME type"""
        proc = await asyncio.create_subprocess_exec(
            'file', '--mime-type', '-b', file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    def _track_error(self, error_msg: str) -> None:
        """Track and categorize errors"""
        error_type = "Unknown"
        
        if "ConnectionError" in error_msg:
            error_type = "Connection"
        elif "Timeout" in error_msg:
            error_type = "Timeout"
        elif "DRM" in error_msg:
            error_type = "DRM"
        elif "Instagram" in error_msg:
            error_type = "Instagram"
            
        self.error_tracker[error_type] = self.error_tracker.get(error_type, 0) + 1

# Initialize download system
download_system = DownloadSystem()

# ==================== BOT HANDLERS ====================
@bot.on_message(filters.command(["insta", "instagram"]) & filters.private)
async def insta_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Please provide an Instagram URL\nExample: /insta https://www.instagram.com/p/Cxample/")
    
    url = message.text.split(" ", 1)[1]
    await download_system.add_to_queue(message.chat.id, url, '1080', message)

@bot.on_message(filters.command("errors") & filters.private)
async def error_report_handler(client: Client, message: Message):
    if not download_system.error_tracker:
        return await message.reply_text("✅ No errors recorded yet!")
    
    report = "📊 **Error Report**\n"
    for error_type, count in download_system.error_tracker.items():
        report += f"• {error_type}: {count} errors\n"
    
    report += f"\nTotal Errors: {sum(download_system.error_tracker.values())}"
    await message.reply_text(report)

@bot.on_message(filters.text & filters.private)
async def text_handler(client: Client, message: Message):
    url = message.text.strip()
    if not download_system._validate_url(url):
        return await message.reply_text("❌ Unsupported URL provided")
    
    editable = await message.reply_text("🔹 Processing your link...")
    await download_system.add_to_queue(message.chat.id, url, 'best', editable)

# ==================== STARTUP AND CLEANUP ====================
async def startup():
    """Initialize necessary components"""
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    logging.info("Bot startup completed")

async def cleanup():
    """Cleanup resources before shutdown"""
    logging.info("Cleaning up resources...")
    # Cancel all active tasks
    for task in download_system.active_tasks:
        task.cancel()
    # Clear download queue
    download_system.download_queue.clear()
    # Clean download directory
    for filename in os.listdir('downloads'):
        file_path = os.path.join('downloads', filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            logging.error(f"Failed to delete {file_path}: {e}")

# ==================== MAIN ENTRY POINT ====================
if __name__ == "__main__":
    try:
        # Run startup tasks
        asyncio.get_event_loop().run_until_complete(startup())
        
        # Start the bot
        bot.run()
    except KeyboardInterrupt:
        logging.info("Received interrupt signal")
    except Exception as e:
        logging.critical(f"Bot crashed: {str(e)}")
    finally:
        # Cleanup before exit
        asyncio.get_event_loop().run_until_complete(cleanup())
