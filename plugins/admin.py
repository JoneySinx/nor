import asyncio
from hydrogram import Client, filters, enums
from hydrogram.types import ChatPermissions

# आपके प्रोजेक्ट के utils से एडमिन चेक इम्पोर्ट करें
from utils import is_check_admin

# ─────────────────────────────────────────────
# 🛠️ HELPER FUNCTION: TARGET USER निकालें
# ─────────────────────────────────────────────
async def get_target_user(client, message):
    """यह फंक्शन रिप्लाई, मेंशन या ID से यूज़र को ढूंढता है"""
    if message.reply_to_message:
        return message.reply_to_message.from_user
    elif len(message.command) > 1:
        target = message.text.split()[1]
        try:
            user = await client.get_users(target)
            return user
        except Exception:
            return None
    return None


# ─────────────────────────────────────────────
# 🆔 ID COMMAND (/id)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("id"))
async def get_id(client, message):
    chat_type = message.chat.type
    
    # अगर किसी मैसेज पर रिप्लाई किया है
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        if target_user:
            text = f"👤 <b>{target_user.first_name} की ID:</b> <code>{target_user.id}</code>\n"
        else:
            text = "👤 <b>यूज़र की ID:</b> <i>छुपी हुई है</i>\n"
        
        text += f"💬 <b>मैसेज ID:</b> <code>{message.reply_to_message.id}</code>\n"
        
    else:
        # खुद की ID
        text = f"👤 <b>आपकी ID:</b> <code>{message.from_user.id}</code>\n"
        text += f"💬 <b>मैसेज ID:</b> <code>{message.id}</code>\n"

    # अगर ग्रुप में है तो ग्रुप की ID भी दें
    if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        text += f"🏘️ <b>ग्रुप ID:</b> <code>{message.chat.id}</code>"
        
    await message.reply(text, parse_mode=enums.ParseMode.HTML)


# ─────────────────────────────────────────────
# 🚫 BAN COMMAND (/ban & /unban)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("ban") & filters.group)
async def ban_user(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_check_admin(client, chat_id, user_id):
        return await message.reply("❌ यह कमांड सिर्फ एडमिन्स के लिए है!")

    target_user = await get_target_user(client, message)
    if not target_user:
        return await message.reply("❌ कृपया किसी यूज़र के मैसेज पर रिप्लाई करें या उसका Username/ID दें।")

    if target_user.id == client.me.id:
        return await message.reply("❌ मैं खुद को बैन नहीं कर सकता!")
        
    if await is_check_admin(client, chat_id, target_user.id):
        return await message.reply("❌ मैं किसी एडमिन को बैन नहीं कर सकता!")

    try:
        await client.ban_chat_member(chat_id, target_user.id)
        await message.reply(f"✅ <b>{target_user.mention}</b> को ग्रुप से बैन कर दिया गया है।", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ बैन करने में समस्या आई। क्या मेरे पास बैन करने के राइट्स हैं?\n<code>{e}</code>")


@Client.on_message(filters.command("unban") & filters.group)
async def unban_user(client, message):
    chat_id = message.chat.id
    if not await is_check_admin(client, chat_id, message.from_user.id): return

    target_user = await get_target_user(client, message)
    if not target_user:
        return await message.reply("❌ कृपया किसी यूज़र का Username/ID दें या रिप्लाई करें।")

    try:
        await client.unban_chat_member(chat_id, target_user.id)
        await message.reply(f"✅ <b>{target_user.mention}</b> को अनबैन कर दिया गया है।", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ अनबैन करने में एरर: <code>{e}</code>")


# ─────────────────────────────────────────────
# 👢 KICK COMMAND (/kick)
# ─────────────────────────────────────────────
@Client.on_message(filters.command(["kick", "kike"]) & filters.group)
async def kick_user(client, message):
    chat_id = message.chat.id
    if not await is_check_admin(client, chat_id, message.from_user.id):
        return await message.reply("❌ यह कमांड सिर्फ एडमिन्स के लिए है!")

    target_user = await get_target_user(client, message)
    if not target_user:
        return await message.reply("❌ कृपया किसी यूज़र के मैसेज पर रिप्लाई करें।")

    if await is_check_admin(client, chat_id, target_user.id):
        return await message.reply("❌ मैं किसी एडमिन को किक नहीं कर सकता!")

    try:
        # Kick करने के लिए पहले Ban करें, फिर तुरंत Unban कर दें
        await client.ban_chat_member(chat_id, target_user.id)
        await client.unban_chat_member(chat_id, target_user.id)
        await message.reply(f"👢 <b>{target_user.mention}</b> को ग्रुप से निकाल (Kick) दिया गया है।", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ किक करने में एरर: <code>{e}</code>")


# ─────────────────────────────────────────────
# 🔇 MUTE COMMAND (/mute & /unmute)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("mute") & filters.group)
async def mute_user(client, message):
    chat_id = message.chat.id
    if not await is_check_admin(client, chat_id, message.from_user.id): return

    target_user = await get_target_user(client, message)
    if not target_user:
        return await message.reply("❌ कृपया किसी यूज़र के मैसेज पर रिप्लाई करें।")

    if await is_check_admin(client, chat_id, target_user.id):
        return await message.reply("❌ एडमिन्स को म्यूट नहीं किया जा सकता!")

    try:
        await client.restrict_chat_member(chat_id, target_user.id, ChatPermissions(can_send_messages=False))
        await message.reply(f"🔇 <b>{target_user.mention}</b> को म्यूट कर दिया गया है।", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ म्यूट करने में एरर: <code>{e}</code>")


@Client.on_message(filters.command("unmute") & filters.group)
async def unmute_user(client, message):
    chat_id = message.chat.id
    if not await is_check_admin(client, chat_id, message.from_user.id): return

    target_user = await get_target_user(client, message)
    if not target_user:
        return await message.reply("❌ कृपया किसी यूज़र के मैसेज पर रिप्लाई करें।")

    try:
        # सभी परमिशन वापस देना
        perms = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        await client.restrict_chat_member(chat_id, target_user.id, perms)
        await message.reply(f"🔊 <b>{target_user.mention}</b> को अनम्यूट कर दिया गया है, अब वह मैसेज भेज सकता है।", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ अनम्यूट करने में एरर: <code>{e}</code>")


# ─────────────────────────────────────────────
# 📌 PIN & 🗑️ DELETE COMMANDS (/pin, /unpin, /del)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("pin") & filters.group)
async def pin_message(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id): return
    if not message.reply_to_message:
        return await message.reply("❌ किसी मैसेज को पिन करने के लिए उस पर रिप्लाई करें।")
    
    try:
        await message.reply_to_message.pin(disable_notification=False)
        await message.reply("📌 मैसेज सफलतापूर्वक पिन कर दिया गया है।")
    except Exception as e:
        await message.reply("❌ मैसेज पिन नहीं कर सका। क्या मेरे पास परमिशन है?")

@Client.on_message(filters.command("unpin") & filters.group)
async def unpin_message(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id): return
    try:
        if message.reply_to_message:
            await message.reply_to_message.unpin()
        else:
            await client.unpin_all_chat_messages(message.chat.id)
        await message.reply("✅ मैसेज अनपिन कर दिया गया है।")
    except Exception as e:
        pass

@Client.on_message(filters.command(["del", "delete"]) & filters.group)
async def delete_message(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id): return
    if not message.reply_to_message:
        return await message.reply("❌ किसी मैसेज को डिलीट करने के लिए उस पर रिप्लाई करें।")
    
    try:
        await message.reply_to_message.delete()
        await message.delete() # खुद का /del कमांड भी डिलीट कर दे
    except:
        pass


# ─────────────────────────────────────────────
# 📢 REPORT COMMAND (/report या @admin)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("report") & filters.group)
async def report_user(client, message):
    chat_id = message.chat.id
    
    if not message.reply_to_message:
        return await message.reply("❌ एडमिन्स को रिपोर्ट करने के लिए किसी आपत्तिजनक मैसेज पर रिप्लाई करके <code>/report</code> लिखें।", parse_mode=enums.ParseMode.HTML)

    # एडमिन्स की लिस्ट निकालना
    admins = []
    async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
        if not member.user.is_bot:
            admins.append(member.user.id)

    if not admins:
        return await message.reply("इस ग्रुप में कोई एडमिन नहीं है।")

    # एडमिन्स को अदृश्य रूप से टैग करना (Invisible Mention)
    hidden_mentions = "".join(f"[\u2064](tg://user?id={admin_id})" for admin_id in admins)
    
    await message.reply_to_message.reply_text(
        f"🚨 <b>रिपोर्ट सबमिट कर दी गई है!</b>\n\nग्रुप के एडमिन्स को इस मैसेज के बारे में सूचित कर दिया गया है।{hidden_mentions}",
        parse_mode=enums.ParseMode.HTML
    )
