import os
import asyncio
import logging
import shutil
import urllib.request
import tarfile
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped
from yt_dlp import YoutubeDL
from motor.motor_asyncio import AsyncIOMotorClient

# Setup System Matrix Logging
logging.basicConfig(level=logging.INFO)

# ====================================================================================
# ⚙️ CONFIGURATION & DATABASE SETUP (HARDCODED VALUES)
# ====================================================================================
# Credentials အားလုံးကို ကုဒ်ထဲမှာ တိုက်ရိုက် အသေထည့်သွင်းထားပါသည်
API_ID = 39584681
API_HASH = "c8c0685d6dd5b9e546093ea90d27733b"
BOT_TOKEN = "8851389371:AAGtL5vzAfnOsDqU_3Z6hSqmad75xngwfAo"
MONGO_URI = "mongodb+srv://kkt:944PJsFRda4Tcr3C@cluster0.kb5fzfl.mongodb.net/telegram_bot?appName=Cluster0&tlsAllowInvalidCertificates=true"
OWNER_ID = 6015356597

# MongoDB Connection Bridge
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["telegram_bot"]
music_col = db["bod_music_settings"]

# Global Music Queue Matrix
QUEUE = {}

# Initialize Native Clients
bot = Client("bod_official_music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = None
call_py = None

# ==========================================
# 📦 DYNAMIC FFMPEG DEPLOYER FOR RENDER
# ==========================================
def ensure_ffmpeg_deployed():
    """Ensures FFmpeg binaries are dynamically provisioned in virtual environments like Render"""
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        print("✅ [BOD ENVIRONMENT] Native FFmpeg architecture detected in system PATH.")
        return

    print("📥 [BOD ENVIRONMENT] FFmpeg missing! Downloading static Linux binaries for Render instance...")
    bin_dir = os.path.join(os.getcwd(), "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    ffmpeg_target = os.path.join(bin_dir, "ffmpeg")
    if not os.path.exists(ffmpeg_target):
        static_url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
        archive_path = os.path.join(bin_dir, "ffmpeg.tar.xz")
        try:
            urllib.request.urlretrieve(static_url, archive_path)
            with tarfile.open(archive_path, "r:xz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("ffmpeg") or member.name.endswith("ffprobe"):
                        member.name = os.path.basename(member.name)
                        tar.extract(member, bin_dir)
            os.remove(archive_path)
            os.chmod(os.path.join(bin_dir, "ffmpeg"), 0o755)
            os.chmod(os.path.join(bin_dir, "ffprobe"), 0o755)
            print("✅ [BOD ENVIRONMENT] Static Linux FFmpeg compiled and extracted successfully.")
        except Exception as e:
            print(f"❌ [BOD ENVIRONMENT] Failed to hot-deploy static FFmpeg dependencies: {e}")
            return
            
    os.environ["PATH"] += os.pathsep + bin_dir
    print(f"🚀 [BOD ENVIRONMENT] Dynamic binary execution path set to: {bin_dir}")

# ==========================================
# 🌍 DYNAMIC USERBOT LIFECYCLE MANAGEMENT
# ==========================================
async def start_userbot_session(session_string):
    global userbot, call_py
    try:
        if call_py:
            try: await call_py.stop()
            except: pass
        if userbot:
            try: await userbot.stop()
            except: pass

        print("⚡ [BOD SYSTEM] Booting up Userbot Stream Client...")
        userbot = Client("bod_vc_userbot", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
        call_py = PyTgCalls(userbot)
        
        @call_py.on_stream_end()
        async def stream_end_handler(client, update):
            chat_id = update.chat_id
            if chat_id in QUEUE and len(QUEUE[chat_id]) > 1:
                QUEUE[chat_id].pop(0)
                next_song = QUEUE[chat_id][0]
                try:
                    await call_py.change_stream(chat_id, AudioPiped(next_song["url"]))
                    await bot.send_message(
                        chat_id,
                        f"⏭ **𝗔𝗨𝗧𝗢-𝗣𝗟𝗔𝗬: 𝗡𝗘𝗫𝗧 𝗧𝗥𝗔𝗖𝗞**\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📝 **𝗧𝗶𝘁𝗹𝗲:** `{next_song['title']}`\n"
                        f"━━━━━━━━━━━━━━━━━━━━",
                        reply_markup=get_control_buttons()
                    )
                except Exception as e:
                    print(f"Error in auto-play: {e}")
            else:
                QUEUE[chat_id] = []
                try: await call_py.leave_group_call(chat_id)
                except: pass

        await userbot.start()
        await call_py.start()
        print("🚀 [BOD SYSTEM] Userbot Client is now fully ONLINE!")
        return True
    except Exception as e:
        print(f"❌ [BOD SYSTEM] Failed to boot Userbot: {e}")
        return False

# ==========================================
# 🌍 RENDER KEEP-ALIVE SYSTEM
# ==========================================
async def handle_render_health_check(reader, writer):
    await reader.read(100)
    response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK"
    writer.write(response.encode('utf-8'))
    await writer.drain()
    writer.close()

async def start_dummy_web_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = await asyncio.start_server(handle_render_health_check, '0.0.0.0', port)
        print(f"🌍 Dummy HTTP Server started on port {port} for Render Keep-Alive!")
        async with server:
            await server.serve_forever()
    except Exception as e:
        print(f"❌ Failed to start Dummy Web Server: {e}")

# ====================================================================================
# 🎵 YOUTUBE SEARCH, STREAM & MP3 DOWNLOAD CORE ARCHITECTURE
# ====================================================================================
def get_youtube_stream(query):
    """VC Link Exporter Engine"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'skip_download': True,
        'geo_bypass': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if 'entries' in info and len(info['entries']) > 0:
                video = info['entries'][0]
                return video['url'], video['title']
        except Exception:
            return None, None
    return None, None

def download_mp3_file(query):
    """Direct MP3 Compiler Engine"""
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'geo_bypass': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            if 'entries' in info and len(info['entries']) > 0:
                video = info['entries'][0]
                filename = ydl.prepare_filename(video)
                base, _ = os.path.splitext(filename)
                return f"{base}.mp3", video.get('title', 'Audio Track')
        except Exception:
            return None, None
    return None, None

# ==========================================
# 🎛️ INLINE CONTROL BUTTONS GENERATOR
# ==========================================
def get_control_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("‖ ⏸ 𝗣𝗔𝗨𝗦𝗘 ‖", callback_data="cb_pause"),
            InlineKeyboardButton("‖ ▶️ 𝗥𝗘𝗦𝗨𝗠𝗘 ‖", callback_data="cb_resume")
        ],
        [
            InlineKeyboardButton("‖ ⏭ 𝗦𝗞𝗜𝗣 ‖", callback_data="cb_skip"),
            InlineKeyboardButton("‖ 🛑 𝗦𝗧𝗢𝗣 ‖", callback_data="cb_stop")
        ],
        [
            InlineKeyboardButton("【 🗑 𝗖𝗟𝗢𝗦𝗘 𝗣𝗔𝗡𝗘𝗟 】", callback_data="cb_close")
        ],
        [
            InlineKeyboardButton("👥 Brotherhood of Dexter", url="https://t.me/BOD_Community_Link")
        ]
    ])

# ==========================================
# 📥 OWNER DYNAMIC SESSION LOADER (DM / REPLY)
# ==========================================
@bot.on_message(filters.command("music", prefixes=["/", "!"]) & filters.private)
async def update_session_command(client, message):
    if message.from_user.id != OWNER_ID:
        return

    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply_text(
            "⚠️ **𝐒𝐘𝐒𝐓𝐄𝐌 𝐄𝐑𝐑𝐎𝐑**\n\n"
            "> Please reply to the raw Pyrogram String Session text with `/music` command to update the database."
        )
        return

    session_str = message.reply_to_message.text.strip()
    status_msg = await message.reply_text("⚡ **𝗕𝗢𝗗 𝗗𝗔𝗧𝗔𝗕𝗔𝗦𝗘:** `Updating string session...`")

    await music_col.update_one(
        {"key": "string_session"},
        {"$set": {"value": session_str}},
        upsert=True
    )

    await status_msg.edit("🔄 **𝗕𝗢𝗗 𝗦𝗬𝗦𝗧𝗘𝐌:** `Hot-rebooting stream engine...`")
    success = await start_userbot_session(session_str)
    
    if success:
        await status_msg.edit(
            "🔮 **𝗦𝗘𝗦𝗦𝗜𝗢𝗡 𝗨𝗣𝗗𝗔𝗧𝗘𝗗 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟𝗟𝗬**\n\n"
            "» **Status:** `ONLINE` 🎧\n"
            "» **Engine:** `PyTgCalls Native Stream`\n\n"
            "_Everything is set. Go stream the world, Owner._"
        )
    else:
        await status_msg.edit("❌ **𝐄𝐍𝐆𝐈𝐍𝐄 𝐂𝐑𝐀𝐒𝐇:** Session string is invalid or rejected by Telegram API.")

# ====================================================================================
# 🤖 BOT COMMAND INTERCEPTORS (THE TWO DISTINCT GATEWAYS)
# ====================================================================================

# 🛣️ GATEWAY 1: VOICE CHAT STREAM ENGINE (Requires Prefix: /play, !play, /music, etc.)
@bot.on_message(filters.command(["play", "music", "song", "search"], prefixes=["/", "!"]) & filters.group)
async def vc_play_handler(client, message):
    global QUEUE
    chat_id = message.chat.id

    if not call_py:
        await message.reply_text("🛑 **𝐒𝐘𝐒𝐓𝐄𝐌 𝐃𝐎𝐖𝐍:** Userbot stream client is not active yet. Ask Owner to configure.")
        return
    
    if len(message.command) < 2:
        await message.reply_text("ℹ️ **𝐔𝐒𝐀𝐆𝐄:** `/play [Song Title or YouTube Link]`")
        return

    query = " ".join(message.command[1:])
    status_msg = await message.reply_text("🔍 **𝗦𝗘𝗔𝗥𝗖𝗛𝗜𝗡𝗚 FOR VC:** `Connecting to YouTube stream grid...`")

    loop = asyncio.get_event_loop()
    stream_url, title = await loop.run_in_executor(None, get_youtube_stream, query)
    if not stream_url:
        await status_msg.edit("❌ **𝟰𝟬𝟰 𝗡𝗢𝗧 𝗙𝗢𝗨𝗡𝗗:** Could not locate the requested track on YouTube.")
        return

    if chat_id not in QUEUE:
        QUEUE[chat_id] = []
    
    QUEUE[chat_id].append({"url": stream_url, "title": title})

    if len(QUEUE[chat_id]) == 1:
        try:
            await call_py.join_group_call(chat_id, AudioPiped(stream_url))
            await status_msg.delete()
            await bot.send_message(
                chat_id,
                f"🔥 **𝗡𝗢𝗪 𝗣𝗟𝗔𝗬𝗜𝗡𝗚 𝗢𝗡 𝗩𝗖** 🔥\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"😎 **𝗧𝗶𝘁𝗹𝗲:** `{title}`\n"
                f"🎧 **𝗦𝘁𝗮𝘁𝘂𝘀:** `Streaming Live`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"> **Community:** `Brotherhood of Dexter`",
                reply_markup=get_control_buttons()
            )
        except Exception as e:
            QUEUE[chat_id].pop(0)
            await status_msg.edit(f"❌ **𝐒𝐓𝐑𝐄𝐀𝐌 𝐄𝐑𝐑𝐎𝐑:** Make sure the Userbot account is a member inside this group VC.\n`Details: {e}`")
    else:
        await status_msg.edit(
            f"➕ **𝗧𝗥𝗔𝗖𝗞 𝗤𝗨𝗘𝗨𝗘𝗗**\n\n"
            f"» **Title:** `{title}`\n"
            f"» **Position:** `#{len(QUEUE[chat_id])}`"
        )


# 🛣️ GATEWAY 2: DIRECT MP3 FILE DELIVERY ENGINE (Strictly No Prefix: play alone, music faded, etc.)
@bot.on_message(filters.regex(r"^(?i)^(play|music|song)\s+(.+)$") & filters.group)
async def mp3_delivery_handler(client, message):
    chat_id = message.chat.id
    query = message.matches[0].group(2).strip()
    
    status_msg = await message.reply_text("📥 **𝗗𝗢𝗪𝗡𝗟𝗢𝗔𝗗𝗜𝗡𝗚 𝗠𝗣𝟯:** `Extracting high-quality audio matrix...`")
    
    loop = asyncio.get_event_loop()
    mp3_path, title = await loop.run_in_executor(None, download_mp3_file, query)
    
    if not mp3_path or not os.path.exists(mp3_path):
        await status_msg.edit("❌ **DOWNLOAD ERROR:** Failed to extract MP3 track from YouTube database.")
        return
        
    try:
        await status_msg.edit("⚡ **𝗨block𝗣𝗟𝗢𝗔𝗗𝗜𝗡𝗚:** `Dispatching MP3 file packet to chat group...`")
        await client.send_audio(
            chat_id=chat_id,
            audio=mp3_path,
            caption=f"🎵 **𝗠𝗨𝗦𝗜𝗖 𝗗𝗘𝗟𝗜𝗩𝗘𝗥𝗬 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟**\n\n» **Track:** `{title}`\n» **Type:** `Direct MP3 Export`\n» **Powered by:** `BOD Music Engine`"
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit(f"❌ **DISPATCH ERROR:** `{e}`")
    finally:
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)


# ==========================================
# 🎛️ CONTROLS & UTILITIES HANDLERS
# ==========================================
@bot.on_message(filters.command("skip", prefixes=["/", "!"]) & filters.group)
async def skip_command(client, message):
    global QUEUE
    chat_id = message.chat.id
    
    if chat_id not in QUEUE or len(QUEUE[chat_id]) <= 1:
        await message.reply_text("⏭ **𝗡𝗢𝗧𝗛𝗜𝗡𝗚 𝗧𝗢 𝗦𝗞𝗜𝗣:** No more tracks left in the queue grid.")
        return
    
    try:
        QUEUE[chat_id].pop(0)
        next_song = QUEUE[chat_id][0]
        
        await call_py.change_stream(chat_id, AudioPiped(next_song["url"]))
        await message.reply_text(
            f"⏭ **𝗦𝗞𝗜𝗣𝗣𝗘𝗗 & 𝗡𝗘𝗫𝗧 𝗨𝗣**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 **𝗧𝗶𝘁𝗹𝗲:** `{next_song['title']}`\n"
            f"━━━━━━━━━━━━━━━━━━━━",
            reply_markup=get_control_buttons()
        )
    except Exception as e:
        await message.reply_text(f"❌ **𝗦𝗞𝗜𝗣 𝗘𝗥𝗥𝗢𝗥:** `{e}`")

@bot.on_message(filters.command(["end", "stop"], prefixes=["/", "!"]) & filters.group)
async def end_command(client, message):
    global QUEUE
    chat_id = message.chat.id
    
    try:
        if chat_id in QUEUE:
            QUEUE[chat_id] = []
            
        await call_py.leave_group_call(chat_id)
        await message.reply_text("🛑 **𝗦𝗧𝗥𝗘𝗔𝗠 𝗧𝗘𝗥𝗠𝗜𝗡𝗔𝗧𝗘𝗗**\n\n> Queue cleared. Voice Chat disconnected successfully.")
    except Exception:
        await message.reply_text("❌ **𝐄𝐑𝐑𝐎𝐑:** Stream client is already disconnected or inactive.")

@bot.on_message(filters.command("queue", prefixes=["/", "!"]) & filters.group)
async def queue_command(client, message):
    chat_id = message.chat.id
    if chat_id not in QUEUE or len(QUEUE[chat_id]) <= 1:
        await message.reply_text("📭 **𝗤𝗨𝗘𝗨𝗘 𝗘𝗠𝗣𝗧𝗬:** No upcoming tracks available.")
        return
    
    text = "📋 **𝗕𝗢𝗗 𝗠𝗨𝗦𝗜𝗖 𝗤𝗨𝗘𝗨𝗘 𝗟𝗜𝗦𝗧:**\n\n"
    for i, song in enumerate(QUEUE[chat_id][1:], start=1):
        text += f"**{i} .** `{song['title']}`\n"
    await message.reply_text(text)

@bot.on_callback_query(filters.regex(r"^cb_"))
async def callback_handler(client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    
    if data == "cb_pause":
        try:
            await call_py.pause_stream(chat_id)
            await callback_query.answer("⏸ Stream Paused", show_alert=False)
        except Exception:
            await callback_query.answer("❌ Stream is already paused or inactive", show_alert=True)

    elif data == "cb_resume":
        try:
            await call_py.resume_stream(chat_id)
            await callback_query.answer("▶️ Stream Resumed", show_alert=False)
        except Exception:
            await callback_query.answer("❌ Stream is already running or inactive", show_alert=True)

    elif data == "cb_stop":
        try:
            if chat_id in QUEUE:
                QUEUE[chat_id] = []
            await call_py.leave_group_call(chat_id)
            await callback_query.message.edit_text("🛑 **𝗦𝗧𝗥𝗘𝗔𝗠 𝗧𝗘𝗥𝗠𝗜𝗡𝗔𝗧𝗘𝗗**\n\n> Control Panel destroyed. Disconnected from Voice Chat.")
        except Exception:
            await callback_query.answer("❌ Bot is not in Voice Chat", show_alert=True)

    elif data == "cb_skip":
        if chat_id not in QUEUE or len(QUEUE[chat_id]) <= 1:
            await callback_query.answer("⏭ Queue is empty. No more tracks to skip!", show_alert=True)
            return
        try:
            QUEUE[chat_id].pop(0)
            next_song = QUEUE[chat_id][0]
            await call_py.change_stream(chat_id, AudioPiped(next_song["url"]))
            await callback_query.message.edit_text(
                f"⏭ **𝗦𝗞𝗜𝗣𝗣𝗘𝗗 & 𝗡𝗘𝗫𝗧 𝗨𝗣**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 **𝗧𝗶𝘁𝗹𝗲:** `{next_song['title']}`\n"
                f"━━━━━━━━━━━━━━━━━━━━",
                reply_markup=get_control_buttons()
            )
        except Exception as e:
            await callback_query.message.reply_text(f"❌ Skip Error: `{e}`")

    elif data == "cb_close":
        try:
            await callback_query.message.delete()
        except Exception:
            await callback_query.answer("❌ Failed to close panel", show_alert=True)

# ==========================================
# 🚀 MAIN RUNNER (STARTUP LOGIC)
# ==========================================
async def main():
    print("⏳ Starting BOD Music Core Matrix...")
    
    ensure_ffmpeg_deployed()
    asyncio.create_task(start_dummy_web_server())

    session_doc = await music_col.find_one({"key": "string_session"})
    if session_doc:
        STRING_SESSION = session_doc.get("value")
        await start_userbot_session(STRING_SESSION)
    else:
        print("💡 [BOD SYSTEM] Database contains no string session yet. Waiting for Owner via DM...")

    await bot.start()
    print("🚀 BOD Music System is fully deployed and blasting live!")
    await idle()
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())

