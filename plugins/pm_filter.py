import asyncio
import re
import math

from hydrogram import Client, filters, enums
from hydrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from info import (
    ADMINS,
    DELETE_TIME,
    MAX_BTN,
)

from utils import (
    is_premium,
    get_size,
    is_check_admin,
    get_readable_time,
    temp,
    get_settings,
)

from database.users_chats_db import db
from database.ia_filterdb import get_search_results

BUTTONS = {}
CAP = {}

# ─────────────────────────────────────────────
# 🔍 PRIVATE SEARCH (ADMIN + PREMIUM)
# ─────────────────────────────────────────────
@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search(client, message):
    if message.text.startswith("/"):
        return

    if not await is_premium(message.from_user.id, client) and message.from_user.id not in ADMINS:
        return await message.reply_text(
            "❌ This bot is only for Premium users and Admins!"
        )

    s = await message.reply(
        f"<b><i>🔍 Searching for `{message.text}`...</i></b>",
        quote=True
    )
    await auto_filter(client, message, s)


# ─────────────────────────────────────────────
# 🔍 GROUP SEARCH
# ─────────────────────────────────────────────
@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    if not user_id:
        return

    if message.text.startswith("/"):
        return

    if not await is_premium(user_id, client) and user_id not in ADMINS:
        return

    # admin mention handler
    if "@admin" in message.text.lower() or "@admins" in message.text.lower():
        if await is_check_admin(client, chat_id, user_id):
            return

        admins = []
        async for member in client.get_chat_members(
            chat_id, enums.ChatMembersFilter.ADMINISTRATORS
        ):
            if not member.user.is_bot:
                admins.append(member.user.id)

        hidden = "".join(f"[\u2064](tg://user?id={i})" for i in admins)
        await message.reply_text("Report sent!" + hidden)
        return

    # block links for non-admins
    if re.findall(r"https?://\S+|www\.\S+|t\.me/\S+|@\w+", message.text):
        if await is_check_admin(client, chat_id, user_id):
            return
        await message.delete()
        return await message.reply("Links not allowed here!")

    s = await message.reply(
        f"<b><i>🔍 Searching for `{message.text}`...</i></b>"
    )
    await auto_filter(client, message, s)


# ─────────────────────────────────────────────
# 🔁 NEXT PAGE
# ─────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^next_"))
async def next_page(bot, query):
    _, req, key, offset = query.data.split("_")

    if int(req) != query.from_user.id:
        return await query.answer("Not for you!", show_alert=True)

    try:
        offset = int(offset)
    except Exception:
        offset = 0

    search = BUTTONS.get(key)
    cap = CAP.get(key)

    if not search:
        return

    files, n_offset, total = await get_search_results(search, offset=offset)
    if not files:
        return

    temp.FILES[key] = files

    files_text = ""
    for file in files:
        files_text += (
            f"📁 <a href='https://t.me/{temp.U_NAME}"
            f"?start=file_{query.message.chat.id}_{file['_id']}'>"
            f"[{get_size(file['file_size'])}] {file['file_name']}</a>\n\n"
        )

    btn = []
    if n_offset not in ("", None):
        btn.append([
            InlineKeyboardButton(
                "ɴᴇxᴛ »",
                callback_data=f"next_{req}_{key}_{n_offset}"
            )
        ])

    btn.append([InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_data")])

    await query.message.edit_text(
        cap + "\n\n" + files_text,
        reply_markup=InlineKeyboardMarkup(btn),
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML
    )


# ─────────────────────────────────────────────
# ❌ CLOSE
# ─────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^close_data$"))
async def close_cb(bot, query):
    await query.message.delete()


# ─────────────────────────────────────────────
# 🚀 AUTO FILTER CORE
# ─────────────────────────────────────────────
async def auto_filter(client, msg, s):
    message = msg
    settings = await get_settings(message.chat.id)

    search = message.text.strip()
    files, offset, total = await get_search_results(search)

    if not files:
        return await s.edit(f"❌ I can't find <b>{search}</b>")

    key = f"{message.chat.id}-{message.id}"
    temp.FILES[key] = files
    BUTTONS[key] = search

    files_text = ""
    for file in files:
        files_text += (
            f"📁 <a href='https://t.me/{temp.U_NAME}"
            f"?start=file_{message.chat.id}_{file['_id']}'>"
            f"[{get_size(file['file_size'])}] {file['file_name']}</a>\n\n"
        )

    cap = (
        f"<b>👑 Search: {search}\n"
        f"🎬 Total Files: {total}\n"
        f"📄 Page: 1 / {math.ceil(total / MAX_BTN) if total else 1}</b>\n\n"
    )
    CAP[key] = cap

    btn = []
    if offset not in ("", None):
        btn.append([
            InlineKeyboardButton(
                "ɴᴇxᴛ »",
                callback_data=f"next_{message.from_user.id}_{key}_{offset}"
            )
        ])

    btn.append([InlineKeyboardButton("❌ ᴄʟᴏsᴇ", callback_data="close_data")])

    k = await s.edit_text(
        cap + files_text,
        reply_markup=InlineKeyboardMarkup(btn),
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML
    )

    if settings.get("auto_delete"):
        await asyncio.sleep(DELETE_TIME)
        await k.delete()
