import asyncio
from datetime import datetime
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# आपके प्रोजेक्ट के इंफो और यूटिल्स
from utils import is_check_admin
from info import DATABASE_URL

# ─────────────────────────────────────────────
# 🗄️ DATABASE SETUP
# ─────────────────────────────────────────────
db_client = AsyncIOMotorClient(DATABASE_URL)
users_history_db = db_client["GroupManager"]["UsersHistory"]
sangmata_settings_db = db_client["GroupManager"]["SangmataSettings"]

async def get_user_history(user_id):
    return await users_history_db.find_one({"_id": user_id})

async def update_user_history(user_id, first_name, last_name, username, old_data=None):
    """यूज़र का करंट डेटा अपडेट करना और हिस्ट्री में पुराना डेटा जोड़ना"""
    current_time = datetime.now().strftime("%d/%m/%Y, %H:%M")
    
    update_query = {
        "$set": {
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "last_seen": current_time
        }
    }

    # अगर पुराना डेटा मौजूद है, तो उसे 'history' एरे (list) में डाल दें
    if old_data:
        history_entry = {
            "first_name": old_data.get("first_name"),
            "last_name": old_data.get("last_name"),
            "username": old_data.get("username"),
            "changed_at": current_time
        }
        update_query["$push"] = {"history": history_entry}

    await users_history_db.update_one({"_id": user_id}, update_query, upsert=True)

async def is_sangmata_on(chat_id):
    chat = await sangmata_settings_db.find_one({"chat_id": chat_id})
    return chat.get("status", False) if chat else False

# ─────────────────────────────────────────────
# 📜 HISTORY COMMAND (/sg <id/username/reply>)
# ─────────────────────────────────────────────
@Client.on_message(filters.command(["sg", "history"]) & filters.group)
async def view_history(client, message):
    chat_id = message.chat.id
    if not await is_check_admin(client, chat_id, message.from_user.id):
        return await message.reply("❌ यह सिर्फ एडमिन्स के लिए है।")

    # टारगेट यूज़र ढूंढें
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try:
            target_user = await client.get_users(message.command[1])
        except:
            return await message.reply("❌ यूज़र नहीं मिला।")
    else:
        return await message.reply("❓ किसकी हिस्ट्री देखनी है? रिप्लाई करें या ID दें।")

    data = await get_user_history(target_user.id)
    if not data or not data.get("history"):
        return await message.reply(f"🔍 <b>{target_user.first_name}</b> की कोई पुरानी हिस्ट्री नहीं मिली।")

    history_list = data.get("history", [])
    
    # UI डिज़ाइन
    text = f"📜 <b>USER HISTORY: {target_user.first_name}</b>\n"
    text += f"🆔 <b>ID:</b> <code>{target_user.id}</code>\n"
    text += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    # पिछली 5-10 हिस्ट्री दिखाना (ताकि मैसेज बहुत बड़ा न हो)
    for i, entry in enumerate(history_list[-10:], 1):
        f_name = entry.get("first_name", "")
        l_name = entry.get("last_name", "")
        u_name = f"@{entry.get('username')}" if entry.get("username") else "None"
        date = entry.get("changed_at", "Unknown")
        
        text += f"{i}. 📅 <b>तारीख:</b> {date}\n"
        text += f"   📛 <b>नाम:</b> {f_name} {l_name}\n"
        text += f"   🔗 <b>Username:</b> {u_name}\n"
        text += f"──────────────────\n"

    text += f"\n✅ <b>वर्तमान नाम:</b> {target_user.first_name}"
    
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)


# ─────────────────────────────────────────────
# ⚙️ SANGMATA TOGGLE (/sangmata)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("sangmata") & filters.group)
async def sangmata_toggle(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id): return
    
    if len(message.command) < 2:
        status = await is_sangmata_on(message.chat.id)
        return await message.reply(f"SangMata Status: {'ON' if status else 'OFF'}\nUse: `/sangmata on` or `off`")

    action = message.command[1].lower()
    if action == "on":
        await sangmata_settings_db.update_one({"chat_id": message.chat.id}, {"$set": {"status": True}}, upsert=True)
        await message.reply("🟢 SangMata अलर्ट चालू!")
    else:
        await sangmata_settings_db.update_one({"chat_id": message.chat.id}, {"$set": {"status": False}}, upsert=True)
        await message.reply("🔴 SangMata अलर्ट बंद!")


# ─────────────────────────────────────────────
# 👁️ WATCHER (DETECT CHANGES & RECORD)
# ─────────────────────────────────────────────
@Client.on_message(filters.group & filters.incoming, group=3)
async def sangmata_watcher(client, message):
    user = message.from_user
    if not user: return

    old_data = await get_user_history(user.id)
    curr_fname = user.first_name or ""
    curr_lname = user.last_name or ""
    curr_uname = user.username or ""

    if not old_data:
        await update_user_history(user.id, curr_fname, curr_lname, curr_uname)
        return

    old_fname = old_data.get("first_name", "")
    old_lname = old_data.get("last_name", "")
    old_uname = old_data.get("username", "")

    name_changed = (old_fname != curr_fname) or (old_lname != curr_lname)
    uname_changed = old_uname != curr_uname

    if name_changed or uname_changed:
        # अलर्ट भेजें
        if await is_sangmata_on(message.chat.id):
            text = f"🕵️‍♂️ <b>SANGMATA ALERT</b>\n━━━━━━━━━━━━━━\n"
            text += f"👤 <b>यूज़र:</b> {user.mention}\n"
            if name_changed:
                text += f"📛 <b>Name Change:</b>\n  ❌ {old_fname} {old_lname}\n  ✅ {curr_fname} {curr_lname}\n"
            if uname_changed:
                text += f"🔗 <b>Username:</b>\n  ❌ @{old_uname}\n  ✅ @{curr_uname}\n"
            text += f"━━━━━━━━━━━━━━"
            
            btn = [[InlineKeyboardButton("📜 View Full History", callback_data=f"view_hist_{user.id}")]]
            await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

        # डेटाबेस में पुरानी चीज़ों को 'history' में डालना और नई अपडेट करना
        await update_user_history(user.id, curr_fname, curr_lname, curr_uname, old_data=old_data)
