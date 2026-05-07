import re
from datetime import datetime, timedelta
from hydrogram import Client, filters, enums
from hydrogram.types import ChatPermissions
from motor.motor_asyncio import AsyncIOMotorClient

# आपके प्रोजेक्ट के utils से एडमिन चेक इम्पोर्ट करें
from utils import is_check_admin
from info import DATABASE_URL

# ─────────────────────────────────────────────
# 🗄️ DATABASE SETUP FOR BLOCKLIST
# ─────────────────────────────────────────────
db_client = AsyncIOMotorClient(DATABASE_URL)
blocklist_db = db_client["GroupManager"]["AdvancedBlocklist"]

async def get_bl_config(chat_id):
    config = await blocklist_db.find_one({"chat_id": chat_id})
    if not config:
        config = {
            "chat_id": chat_id,
            "triggers": [], # List of dicts: [{"trigger": "word", "reason": "reason"}]
            "mode": "nothing",
            "delete": True,
            "default_reason": ""
        }
        await blocklist_db.insert_one(config)
    return config

async def update_bl_config(chat_id, update_data):
    await blocklist_db.update_one({"chat_id": chat_id}, {"$set": update_data}, upsert=True)


# ─────────────────────────────────────────────
# ⏱️ TIME PARSER HELPER (For tban/tmute)
# ─────────────────────────────────────────────
def parse_time(time_str):
    """1d, 2h, 30m को datetime में बदलता है"""
    time_str = time_str.lower()
    match = re.match(r"(\d+)([dhms])", time_str)
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    if unit == "d": delta = timedelta(days=amount)
    elif unit == "h": delta = timedelta(hours=amount)
    elif unit == "m": delta = timedelta(minutes=amount)
    elif unit == "s": delta = timedelta(seconds=amount)
    return datetime.now() + delta


# ─────────────────────────────────────────────
# 🛑 COMMANDS
# ─────────────────────────────────────────────

@Client.on_message(filters.command("addblocklist") & filters.group)
async def add_blocklist(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_check_admin(client, chat_id, user_id):
        return await message.reply("❌ यह कमांड सिर्फ एडमिन्स के लिए है!")

    if len(message.command) < 2:
        return await message.reply("<b>इस्तेमाल:</b>\n<code>/addblocklist [शब्द या \"पूरा वाक्य\"] [कारण]</code>", parse_mode=enums.ParseMode.HTML)

    # Quotes ("") और Reason को अलग करने का लॉजिक
    text = message.text.split(None, 1)[1]
    match = re.match(r'^(?:"([^"]+)"|(\S+))(?:\s+(.*))?$', text)
    
    if not match:
        return await message.reply("❌ फॉर्मेट गलत है।")

    trigger = (match.group(1) or match.group(2)).lower()
    reason = match.group(3) or ""

    config = await get_bl_config(chat_id)
    triggers = config.get("triggers", [])

    # अगर ट्रिगर पहले से है तो अपडेट करें
    for t in triggers:
        if t["trigger"] == trigger:
            t["reason"] = reason
            break
    else:
        triggers.append({"trigger": trigger, "reason": reason})

    await update_bl_config(chat_id, {"triggers": triggers})
    await message.reply(f"✅ <b>{trigger}</b> को ब्लॉकलिस्ट में जोड़ दिया गया है!", parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("rmblocklist") & filters.group)
async def rm_blocklist(client, message):
    chat_id = message.chat.id
    if not await is_check_admin(client, chat_id, message.from_user.id): return

    if len(message.command) < 2:
        return await message.reply("<b>इस्तेमाल:</b> <code>/rmblocklist [शब्द]</code>", parse_mode=enums.ParseMode.HTML)

    # Quotes सपोर्ट
    text = message.text.split(None, 1)[1]
    match = re.match(r'^(?:"([^"]+)"|(\S+))$', text)
    trigger = (match.group(1) or match.group(2)).lower() if match else text.lower()

    config = await get_bl_config(chat_id)
    triggers = config.get("triggers", [])
    
    new_triggers = [t for t in triggers if t["trigger"] != trigger]
    
    if len(triggers) == len(new_triggers):
        return await message.reply(f"❌ <b>{trigger}</b> ब्लॉकलिस्ट में नहीं मिला।", parse_mode=enums.ParseMode.HTML)

    await update_bl_config(chat_id, {"triggers": new_triggers})
    await message.reply(f"✅ <b>{trigger}</b> को ब्लॉकलिस्ट से हटा दिया गया है।", parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("unblocklistall") & filters.group)
async def unblocklist_all(client, message):
    chat_id = message.chat.id
    
    # सिर्फ Group Creator (Owner) के लिए
    member = await client.get_chat_member(chat_id, message.from_user.id)
    if member.status != enums.ChatMemberStatus.OWNER:
        return await message.reply("❌ यह कमांड सिर्फ ग्रुप के <b>Creator</b> (मालिक) इस्तेमाल कर सकते हैं!", parse_mode=enums.ParseMode.HTML)

    await update_bl_config(chat_id, {"triggers": []})
    await message.reply("✅ ग्रुप के सभी ब्लॉकलिस्टेड शब्द हटा दिए गए हैं!")


@Client.on_message(filters.command("blocklist") & filters.group)
async def list_blocklist(client, message):
    config = await get_bl_config(message.chat.id)
    triggers = config.get("triggers", [])

    if not triggers:
        return await message.reply("इस ग्रुप की ब्लॉकलिस्ट खाली है।")

    text = "<b>इस ग्रुप की ब्लॉकलिस्ट:</b>\n\n"
    for t in triggers:
        reason_txt = f" - <i>{t['reason']}</i>" if t['reason'] else ""
        text += f"• <code>{t['trigger']}</code>{reason_txt}\n"

    await message.reply(text, parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("blocklistmode") & filters.group)
async def set_bl_mode(client, message):
    chat_id = message.chat.id
    if not await is_check_admin(client, chat_id, message.from_user.id): return

    if len(message.command) < 2:
        return await message.reply("<b>इस्तेमाल:</b> <code>/blocklistmode [nothing/ban/mute/kick/warn/tban/tmute]</code>\n(tban/tmute के लिए समय भी दें, जैसे: <code>/blocklistmode tban 1d</code>)", parse_mode=enums.ParseMode.HTML)

    mode = message.command[1].lower()
    valid_modes = ["nothing", "ban", "mute", "kick", "warn", "tban", "tmute"]
    
    if mode not in valid_modes:
        return await message.reply("❌ अमान्य मोड! कृपया इनमें से चुनें: nothing, ban, mute, kick, warn, tban, tmute.")

    # tban/tmute के लिए समय सेट करना
    full_mode = mode
    if mode in ["tban", "tmute"]:
        if len(message.command) < 3:
            return await message.reply(f"❌ {mode} के लिए समय बताना ज़रूरी है! (उदा: 1d, 2h)")
        time_str = message.command[2]
        if not parse_time(time_str):
            return await message.reply("❌ अमान्य समय फॉर्मेट! (1d, 2h, 30m का इस्तेमाल करें)")
        full_mode = f"{mode} {time_str}"

    await update_bl_config(chat_id, {"mode": full_mode})
    await message.reply(f"✅ ब्लॉकलिस्ट मोड को <b>{full_mode}</b> पर सेट कर दिया गया है।", parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("blocklistdelete") & filters.group)
async def set_bl_delete(client, message):
    chat_id = message.chat.id
    if not await is_check_admin(client, chat_id, message.from_user.id): return

    if len(message.command) < 2:
        config = await get_bl_config(chat_id)
        status = "चालू (ON)" if config.get("delete", True) else "बंद (OFF)"
        return await message.reply(f"अभी ब्लॉकलिस्ट डिलीट मोड: <b>{status}</b> है।\nबदलने के लिए: <code>/blocklistdelete on/off</code>", parse_mode=enums.ParseMode.HTML)

    opt = message.command[1].lower()
    if opt in ["yes", "on", "true"]:
        await update_bl_config(chat_id, {"delete": True})
        await message.reply("✅ ब्लॉकलिस्टेड मैसेज अब डिलीट किए जाएंगे।")
    elif opt in ["no", "off", "false"]:
        await update_bl_config(chat_id, {"delete": False})
        await message.reply("✅ ब्लॉकलिस्टेड मैसेज अब डिलीट <b>नहीं</b> किए जाएंगे (सिर्फ एक्शन लिया जाएगा)।", parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("setblocklistreason") & filters.group)
async def set_bl_reason(client, message):
    chat_id = message.chat.id
    if not await is_check_admin(client, chat_id, message.from_user.id): return

    if len(message.command) < 2:
        return await message.reply("<b>इस्तेमाल:</b> <code>/setblocklistreason [कारण]</code>", parse_mode=enums.ParseMode.HTML)

    reason = message.text.split(None, 1)[1]
    await update_bl_config(chat_id, {"default_reason": reason})
    await message.reply(f"✅ डिफ़ॉल्ट ब्लॉकलिस्ट कारण सेट कर दिया गया है:\n<i>{reason}</i>", parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("resetblocklistreason") & filters.group)
async def reset_bl_reason(client, message):
    chat_id = message.chat.id
    if not await is_check_admin(client, chat_id, message.from_user.id): return

    await update_bl_config(chat_id, {"default_reason": ""})
    await message.reply("✅ डिफ़ॉल्ट कारण को रीसेट कर दिया गया है।")


# ─────────────────────────────────────────────
# 🤖 BLACKLIST WATCHER (REGEX & ACTIONS)
# ─────────────────────────────────────────────
@Client.on_message(filters.group & (filters.text | filters.caption) & filters.incoming, group=2)
async def blocklist_watcher(client, message):
    text = message.text or message.caption
    if not text: return

    chat_id = message.chat.id
    user = message.from_user

    if not user or await is_check_admin(client, chat_id, user.id):
        return  # एडमिन्स को हमेशा छूट है

    config = await get_bl_config(chat_id)
    triggers = config.get("triggers", [])
    if not triggers: return

    text_lower = text.lower()
    matched_trigger = None
    reason_found = ""

    # वाइल्डकार्ड्स को Regex में बदलकर चेक करना
    for t in triggers:
        trig = t["trigger"]
        # Rose के स्पेशल सिंबल्स को Regex में कन्वर्ट करना
        # ** -> .* (कुछ भी, स्पेस के साथ)
        # * -> \S* (बिना स्पेस का कुछ भी)
        # ? -> \S (बिना स्पेस का एक करैक्टर)
        
        regex_pattern = trig.replace("**", "\x01").replace("*", "\x02").replace("?", "\x03")
        regex_pattern = re.escape(regex_pattern)
        regex_pattern = regex_pattern.replace("\x01", ".*").replace("\x02", r"\S*").replace("\x03", r"\S")
        
        # Word boundaries सेट करना ताकि "ass" "glass" से मैच न हो (जब तक वाइल्डकार्ड न हो)
        final_pattern = r"(?i)(?:^|\W)" + regex_pattern + r"(?:\W|$)"
        
        if re.search(final_pattern, text_lower):
            matched_trigger = trig
            reason_found = t["reason"]
            break

    if not matched_trigger:
        return

    # अगर ट्रिगर मैच हो गया तो एक्शन लें!
    final_reason = reason_found or config.get("default_reason", "")
    reason_text = f"\n<b>कारण:</b> {final_reason}" if final_reason else ""
    
    # 1. डिलीट मैसेज
    if config.get("delete", True):
        try:
            await message.delete()
        except: pass

    # 2. सज़ा (Punishment Mode)
    mode = config.get("mode", "nothing")
    mode_parts = mode.split()
    action = mode_parts[0]
    
    try:
        if action == "ban":
            await client.ban_chat_member(chat_id, user.id)
            await message.reply(f"🚫 {user.mention} को ब्लॉकलिस्टेड शब्द बोलने के कारण बैन कर दिया गया है!{reason_text}")
            
        elif action == "mute":
            await client.restrict_chat_member(chat_id, user.id, ChatPermissions(can_send_messages=False))
            await message.reply(f"🔇 {user.mention} को ब्लॉकलिस्टेड शब्द बोलने के कारण म्यूट कर दिया गया है!{reason_text}")
            
        elif action == "kick":
            await client.ban_chat_member(chat_id, user.id)
            await client.unban_chat_member(chat_id, user.id) # Ban and immediately unban is Kick
            await message.reply(f"👢 {user.mention} को ग्रुप से निकाल (Kick) दिया गया है!{reason_text}")
            
        elif action == "warn":
            # (अगर आपने Warns प्लगइन नहीं बनाया है, तो यह सिम्पल वार्निंग टेक्स्ट भेजेगा)
            await message.reply(f"⚠️ <b>चेतावनी!</b> {user.mention}, आपने एक ब्लॉकलिस्टेड शब्द का इस्तेमाल किया है। ऐसा दोबारा न करें!{reason_text}", parse_mode=enums.ParseMode.HTML)
            
        elif action == "tban" and len(mode_parts) > 1:
            until_date = parse_time(mode_parts[1])
            await client.ban_chat_member(chat_id, user.id, until_date=until_date)
            await message.reply(f"⏳ {user.mention} को {mode_parts[1]} के लिए बैन कर दिया गया है!{reason_text}")
            
        elif action == "tmute" and len(mode_parts) > 1:
            until_date = parse_time(mode_parts[1])
            await client.restrict_chat_member(chat_id, user.id, ChatPermissions(can_send_messages=False), until_date=until_date)
            await message.reply(f"⏳ {user.mention} को {mode_parts[1]} के लिए म्यूट कर दिया गया है!{reason_text}")
            
    except Exception as e:
        print(f"Blocklist Action Error: {e}")
