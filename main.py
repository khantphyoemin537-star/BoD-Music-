import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pytgcalls import pytgcalls
from pytgcalls.types import AudioPiped
from yt_dlp import YoutubeDL
from motor.motor_asyncio import AsyncIOMotorClient

# Setup Logging
logging.basicConfig(level=logging.INFO)

# ==========================================
# ⚙️ CONFIGURATION & DATABASE SETUP
# ==========================================
API_ID = 39584681
API_HASH = 'c8c0685d6dd5b9e546093ea90d27733b'
BOT_TOKEN = '8851389371:AAGtL5vzAfnOsDqU_3Z6hSqmad75xngwfAo'
MONGO_URI = "mongodb+srv://kkt:944PJsFRda4Tcr3C@cluster0.kb5fzfl.mongodb.net/telegram_bot?appName=Cluster0&tlsAllowInvalidCertificates=true"
OWNER_ID = 6015356597 # มင်းရဲ့ Owner Telegram ID

# MongoDB Connection
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["telegram_bot"]
music_col = db["bod_music_settings"]

# Global Music Queue
QUEUE = {}

# Initialize Clients
bot = Client("bod_official_music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = None
call_py = None

# ==========================================
# 🌍 DYNAMIC USERBOT LIFECYCLE MANAGEMENT
# ==========================================
async def start_userbot_session(session_string):
    """ Restart or Start Userbot dynamically without restarting Render """
    global userbot, call_py
    try:
        # Existing session ရှိရင် အရင်ပိတ်မယ်
        if call_py:
            try: await call_py.stop()
            except: pass
        if userbot:
            try: await userbot.stop()
            except: pass

        print("⚡ [BOD SYSTEM] Booting up Userbot Stream Client...")
        userbot = Client("bod_vc_userbot", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
        call_py = PyTgCalls(userbot)
        
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

# ==========================================
# 🎵 YOUTUBE SEARCH & STREAM EXTRACTOR
# ==========================================
def get_youtube_stream(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'skip_download': True
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
    status_msg = await message.reply_text("⚡ **𝐁𝐎𝐃 𝐃𝐀𝐓𝐀𝐁𝐀𝐒𝐄:** `Updating string session...`")

    # MongoDB ထဲ သိမ်းဆည်းခြင်း
    await music_col.update_one(
        {"key": "string_session"},
        {"$set": {"value": session_str}},
        upsert=True
    )

    await status_msg.edit("🔄 **𝐁𝐎𝐃 𝐒𝐘𝐒𝐓𝐄𝐌:** `Hot-rebooting stream engine...`")
    
    # Run-time ထဲမှာတင် Userbot ကို ချက်ချင်း အလုပ်လုပ်အောင် Engine နှိုးပေးခြင်း
    success = await start_userbot_session(session_str)
    
    if success:
        await status_msg.edit(
            "🔮 **𝗦𝗘𝗦𝗦𝗜𝗢𝗡 𝗨𝗣𝗗𝗔𝗧𝗘𝗗 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟𝗟𝗬**\n\n"
            "» **Status:** `ONLINE` 🎧\n"
            "» **Engine:** `PyTgCalls Native Stream`\n\n"
            "_" + "Everything is set. Go stream the world, Owner." + "_"
        )
    else:
        await status_msg.edit("❌ **𝐄𝐍𝐆𝐈𝐍𝐄 𝐂𝐑𝐀𝐒𝐇:** Session string is invalid or rejected by Telegram API.")

# ==========================================
# 🤖 BOT COMMAND HANDLERS (GROUP COMMANDS)
# ==========================================

@bot.on_message(filters.command("play", prefixes=["/", "!"]) & filters.group)
async def play_command(client, message):
    global QUEUE
    chat_id = message.chat.id

    if not call_py:
        await message.reply_text("🛑 **𝐒𝐘𝐒𝐓𝐄𝐌 𝐃𝐎𝐖𝐍:** Userbot stream client is not active yet. Ask Owner to configure.")
        return
    
    if len(message.command) < 2:
        await message.reply_text("ℹ️ **𝐔𝐒𝐀𝐆𝐄:** `/play [Song Title or YouTube Link]`")
        return

    query = " ".join(message.command[1:])
    status_msg = await message.reply_text("🔍 **𝗦𝗘𝗔𝗥𝗖𝗛𝗜𝗡𝗚:** `Fetching audio vibes from YouTube...`")

    stream_url, title = get_youtube_stream(query)
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
                f"📝 **𝗧𝗶𝘁𝗹𝗲:** `{title}`\n"
                f"🎧 **𝗦𝘁𝗮𝘁𝘂𝘀:** `Streaming Live`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"> **Community:** `Brotherhood of Dexter`",
                reply_markup=get_control_buttons()
            )
        except Exception as e:
            QUEUE[chat_id].pop(0)
            await status_msg.edit(f"❌ **𝐒𝐓𝐑𝐄𝐀𝐌 𝐄𝐑𝐑𝐎𝐑:** Make sure Userbot account is inside this group VC.\n`Details: {e}`")
    else:
        await status_msg.edit(
            f"➕ **𝗧𝗥𝗔𝗖𝗞 𝗤𝗨𝗘𝗨𝗘𝗗**\n\n"
            f"📝 **𝗧𝗶𝘁𝗹ε:** `{title}`\n"
            f"🔢 **𝗣𝗼𝘀𝗶𝘁𝗶𝗼𝗻:** `#{len(QUEUE[chat_id])}`"
        )

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

# ==========================================
# 🎛️ CALLBACK QUERY HANDLER (CONTROL PANEL)
# ==========================================
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
            # Control panel မက်ဆေ့ချ်ကို ရှင်းထုတ်ဖျက်ဆီးပစ်မယ်
            await callback_query.message.delete()
        except Exception:
            await callback_query.answer("❌ Failed to close panel", show_alert=True)

# ==========================================
# 🚀 MAIN RUNNER (STARTUP LOGIC)
# ==========================================
async def main():
    print("⏳ Starting BOD Music Core...")
    
    # Web server background task
    asyncio.create_task(start_dummy_web_server())

    # Database ထဲမှာ session အဟောင်းရှိမရှိ စစ်မယ်
    session_doc = await music_col.find_one({"key": "string_session"})
    
    if session_doc:
        STRING_SESSION = session_doc.get("value")
        # Userbot အား စတင်နှိုးခြင်း
        await start_userbot_session(STRING_SESSION)
    else:
        print("💡 [BOD SYSTEM] Database contains no string session yet. Waiting for Owner via DM...")

    # Official Bot ကို စတင်ဖွင့်လှစ်ခြင်း
    await bot.start()
    print("🚀 BOD Music System is fully deployed and blasting live!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
