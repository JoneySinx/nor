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
    URL,
    STICKERS,
    ADMINS,
    DELETE_TIME,
    LOG_CHANNEL,
    PICS,
    REACTIONS,
    PM_FILE_DELETE_TIME
)

from utils import (
    is_premium,
    get_settings,
    get_size,
    is_check_admin,
    save_group_settings,
    temp,
    get_readable_time,
    get_wish
)

# ─────────────────────────────────────
# HELPERS
# ─────────────────────────────────────
def progress_bar(value, total, size=12):
    if total <= 0:
        return "░" * size
    filled = int((value / total) * size)
    return "█" * filled + "░" * (size - filled)

async def del_stk(msg):
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except:
        pass


# ─────────────────────────────────────
# /start
# ─────────────────────────────────────
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):

    # ───── GROUP START ─────
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            username = f"@{message.chat.username}" if message.chat.username else "Private"
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
            f"<b>Hey {message.from_user.mention}, {get_wish()}</b>"
        )
        return

    # ───── PRIVATE START ─────

    # reaction safe
    try:
        if REACTIONS:
            await message.react(random.choice(REACTIONS), big=True)
    except:
        pass

    # sticker safe
    if STICKERS:
        try:
            stk = await client.send_sticker(
                message.chat.id,
                random.choice(STICKERS)
            )
            asyncio.create_task(del_stk(stk))
        except:
            pass

    # user db
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(
            LOG_CHANNEL,
            script.NEW_USER_TXT.format(
                message.from_user.mention,
                message.from_user.id
            )
        )

    # premium check
    if not await is_premium(message.from_user.id, client) and message.from_user.id not in ADMINS:
        return await message.reply_photo(
            random.choice(PICS),
            caption="❌ This bot is only for Premium users and Admins!"
        )

    # normal ui
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
                ]
            ])
        )


# ─────────────────────────────────────
# FILE START HANDLER
# ─────────────────────────────────────
@Client.on_message(filters.command("start") & filters.regex(r"file_"))
async def file_start(client, message):

    try:
        _, file_id = message.text.split("_", 1)
    except:
        return

    file = await get_file_details(file_id)
    if not file:
        return await message.reply("❌ File not found")

    btn = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "▶️ Watch / Download",
                callback_data=f"stream#{file_id}"
            )
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="close_data")
        ]
    ])

    sent = await client.send_cached_media(
        chat_id=message.chat.id,
        file_id=file["file_id"],
        caption=f"<b>{file['file_name']}</b>",
        reply_markup=btn
    )

    # auto delete
    await asyncio.sleep(PM_FILE_DELETE_TIME)
    try:
        await sent.delete()
    except:
        pass


# ─────────────────────────────────────
# WATCH / DOWNLOAD BUTTON
# ─────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^stream#"))
async def stream_file(client, query):

    file_id = query.data.split("#", 1)[1]
    file = await get_file_details(file_id)

    if not file:
        return await query.answer("File expired", show_alert=True)

    watch = f"{URL}/watch/{file_id}"
    download = f"{URL}/download/{file_id}"

    await query.message.edit_reply_markup(
        InlineKeyboardMarkup([
            [
                InlineKeyboardButton("▶️ Watch Online", url=watch),
                InlineKeyboardButton("⬇️ Download", url=download)
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="close_data")
            ]
        ])
    )


# ─────────────────────────────────────
# CLOSE BUTTON
# ─────────────────────────────────────
@Client.on_callback_query(filters.regex("^close_data$"))
async def close_btn(_, query):
    try:
        await query.message.delete()
    except:
        pass


# ─────────────────────────────────────
# STATS (ADMIN)
# ─────────────────────────────────────
@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats(_, message):

    files = db_count_documents()
    primary = files.get("primary", 0)
    cloud = files.get("cloud", 0)
    archive = files.get("archive", 0)
    total = files.get("total", 0)

    users = await db.total_users_count()
    chats = await db.total_chat_count()
    prm = db.get_premium_count()

    p_bar = progress_bar(primary, total)
    c_bar = progress_bar(cloud, total)
    a_bar = progress_bar(archive, total)

    uptime = get_readable_time(time_now() - temp.START_TIME)

    text = f"""
📊 <b>Bot Statistics</b>

👥 Users   : {users}
💎 Premium : {prm}
👥 Chats   : {chats}

📁 <b>Files</b>

Primary   {p_bar}  {primary}
Cloud     {c_bar}  {cloud}
Archive   {a_bar}  {archive}

🧮 Total : {total}
⏰ Uptime : {uptime}
"""

    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
