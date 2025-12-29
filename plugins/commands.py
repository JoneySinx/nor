import os
import random
import asyncio
from time import time as time_now
from datetime import datetime

from Script import script
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.ia_filterdb import (
    db_count_documents,
    get_file_details,
    delete_files
)
from database.users_chats_db import db

from info import (
    IS_PREMIUM,
    URL,
    BIN_CHANNEL,
    STICKERS,
    ADMINS,
    DELETE_TIME,
    LOG_CHANNEL,
    PICS,
    IS_STREAM,
    REACTIONS,
    PM_FILE_DELETE_TIME
)

from utils import (
    is_premium,
    get_settings,
    get_size,
    is_check_admin,
    temp,
    get_readable_time,
    get_wish
)

# ─────────────────────────
# HELPERS
# ─────────────────────────
def progress_bar(v, t, s=10):
    if t <= 0:
        return "░" * s
    f = int((v / t) * s)
    return "█" * f + "░" * (s - f)

async def del_stk(s):
    await asyncio.sleep(3)
    try:
        await s.delete()
    except:
        pass

async def auto_delete_message(msg, delay):
    """Auto delete message after delay"""
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass

# ─────────────────────────
# /start
# ─────────────────────────
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):

    # GROUP
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            username = f'@{message.chat.username}' if message.chat.username else 'Private'
            await client.send_message(
                LOG_CHANNEL,
                script.NEW_GROUP_TXT.format(
                    message.chat.title,
                    message.chat.id,
                    username,
                    total
                )
            )
            await db.add_chat(message.chat.id, message.chat.title)

        await message.reply(
            f"<b>ʜᴇʏ {message.from_user.mention}, <i>{get_wish()}</i>\n"
            f"ʜᴏᴡ ᴄᴀɴ ɪ ʜᴇʟᴘ ʏᴏᴜ??</b>",
            parse_mode=enums.ParseMode.HTML
        )
        return

    # PRIVATE
    try:
        if REACTIONS:
            await message.react(random.choice(REACTIONS), big=True)
    except:
        pass

    if STICKERS:
        try:
            stk = await client.send_sticker(
                message.chat.id,
                random.choice(STICKERS)
            )
            asyncio.create_task(del_stk(stk))
        except:
            pass

    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(
            LOG_CHANNEL,
            script.NEW_USER_TXT.format(
                message.from_user.mention,
                message.from_user.id
            )
        )

    if not await is_premium(message.from_user.id, client) and message.from_user.id not in ADMINS:
        return await message.reply_photo(
            random.choice(PICS),
            caption="❌ This bot is only for Premium users and Admins!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🤑 Buy Premium",
                    url=f"https://t.me/{temp.U_NAME}?start=premium"
                )
            ]])
        )

    if len(message.command) == 1:
        await message.reply_photo(
            random.choice(PICS),
            caption=script.START_TXT.format(
                message.from_user.mention,
                get_wish()
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "+ ADD ME TO YOUR GROUP +",
                        url=f"https://t.me/{temp.U_NAME}?startgroup=start"
                    )
                ],
                [
                    InlineKeyboardButton("👨‍🚒 HELP", callback_data="help"),
                    InlineKeyboardButton("📚 ABOUT", callback_data="about")
                ]
            ])
        )

# ─────────────────────────
# /stats
# ─────────────────────────
@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats(_, message):

    files = db_count_documents()
    primary = files.get("primary", 0)
    cloud = files.get("cloud", 0)
    archive = files.get("archive", 0)
    total = files.get("total", 0)

    users = await db.total_users_count()
    chats = await db.total_chat_count()
    premium = db.get_premium_count()

    text = f"""
📊 <b>Bot Statistics</b>

👥 Users   : {users}
👥 Groups  : {chats}
💎 Premium : {premium}

📁 <b>Files</b>

Primary   {progress_bar(primary,total)} {primary}
Cloud     {progress_bar(cloud,total)} {cloud}
Archive   {progress_bar(archive,total)} {archive}

🧮 Total Files : {total}
⏱ Uptime : {get_readable_time(time_now() - temp.START_TIME)}
"""

    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)

# ─────────────────────────
# FILE CLICK HANDLER (जब user file result पर click करे)
# ─────────────────────────
@Client.on_callback_query(filters.regex(r"^files#|^file#"))
async def send_file(client, query):
    """Handle file button clicks from search results"""
    try:
        # Extract file_id from callback data (supports both files# and file#)
        ident, file_id = query.data.split("#", 1)
        
        # Get file details from database
        files = await get_file_details(file_id)
        
        if not files:
            return await query.answer("❌ File not found in database!", show_alert=True)
        
        # Answer callback to remove loading
        await query.answer()
        
        # Get first file (in case multiple files returned)
        file = files[0] if isinstance(files, list) else files
        
        # Get file info
        file_name = file.get('file_name', 'Unknown File')
        file_size = get_size(file.get('file_size', 0))
        file_caption = file.get('caption', '')
        
        # Build caption
        caption = f"📁 <b>{file_name}</b>\n\n"
        caption += f"📊 <b>Size:</b> {file_size}\n"
        if file_caption:
            caption += f"\n{file_caption}"
        
        # Create buttons with streaming option
        buttons = [
            [
                InlineKeyboardButton("▶️ Watch / Download", callback_data=f"stream#{file_id}")
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="close_data")
            ]
        ]
        
        # Send file with buttons
        sent_msg = await client.send_cached_media(
            chat_id=query.message.chat.id,
            file_id=file.get('file_id'),
            caption=caption,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
            reply_to_message_id=query.message.id
        )
        
        # Auto delete after PM_FILE_DELETE_TIME
        if PM_FILE_DELETE_TIME and PM_FILE_DELETE_TIME > 0:
            asyncio.create_task(auto_delete_message(sent_msg, PM_FILE_DELETE_TIME))
                
    except Exception as e:
        print(f"❌ Error in send_file: {e}")
        import traceback
        traceback.print_exc()
        await query.answer("❌ Error sending file! Check logs.", show_alert=True)

# ─────────────────────────
# STREAM BUTTON (Watch/Download button पर click करने पर)
# ─────────────────────────
@Client.on_callback_query(filters.regex(r"^stream#"))
async def stream_cb(client, query):
    """Generate streaming and download links"""
    try:
        file_id = query.data.split("#", 1)[1]
        
        await query.answer("⏳ Generating links...", show_alert=False)

        # Get file details
        files = await get_file_details(file_id)
        if not files:
            return await query.answer("❌ File not found!", show_alert=True)
        
        file = files[0] if isinstance(files, list) else files
        
        # Send file to BIN_CHANNEL to generate links
        msg = await client.send_cached_media(
            chat_id=BIN_CHANNEL,
            file_id=file.get('file_id')
        )

        # Generate streaming links
        online_link = f"{URL}watch/{msg.id}"
        download_link = f"{URL}download/{msg.id}"

        # Create buttons with links
        buttons = [
            [
                InlineKeyboardButton("▶️ Watch Online", url=online_link),
                InlineKeyboardButton("⬇️ Download", url=download_link)
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="close_data")
            ]
        ]

        # Edit message with links
        try:
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except:
            # If edit fails, send new message
            await query.message.reply_text(
                "🎬 <b>Your Links:</b>\n\n"
                "▶️ Click <b>Watch Online</b> to stream\n"
                "⬇️ Click <b>Download</b> to save",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
        
    except Exception as e:
        print(f"❌ Error in stream_cb: {e}")
        import traceback
        traceback.print_exc()
        await query.answer("❌ Error generating links!", show_alert=True)

# ─────────────────────────
# CLOSE BUTTON
# ─────────────────────────
@Client.on_callback_query(filters.regex("^close_data$"))
async def close_cb(_, query):
    """Delete message when close button is clicked"""
    try:
        if query.message:
            await query.message.delete()
            await query.answer("✅ Deleted", show_alert=False)
        else:
            await query.answer("Already deleted", show_alert=False)
    except Exception as e:
        print(f"Error in close_cb: {e}")
        try:
            await query.answer()
        except:
            pass
