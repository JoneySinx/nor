import re
from hydrogram import Client, filters, enums
from motor.motor_asyncio import AsyncIOMotorClient

# आपके प्रोजेक्ट के utils से एडमिन चेक इम्पोर्ट करें
from utils import is_check_admin
from info import DATABASE_URL

# ─────────────────────────────────────────────
# 🗄️ DATABASE SETUP FOR FILTERS
# ─────────────────────────────────────────────
db_client = AsyncIOMotorClient(DATABASE_URL)
filters_db = db_client["GroupManager"]["Filters"]

async def save_filter_db(chat_id, keyword, text, file_id, file_type):
    filter_data = {
        "chat_id": chat_id,
        "keyword": keyword.lower(),
        "text": text,
        "file_id": file_id,
        "file_type": file_type
    }
    await filters_db.update_one(
        {"chat_id": chat_id, "keyword": keyword.lower()},
        {"$set": filter_data},
        upsert=True
    )

async def get_all_filters_db(chat_id):
    cursor = filters_db.find({"chat_id": chat_id})
    return [doc async for doc in cursor]

async def delete_filter_db(chat_id, keyword):
    result = await filters_db.delete_one({"chat_id": chat_id, "keyword": keyword.lower()})
    return result.deleted_count > 0


# ─────────────────────────────────────────────
# 🛠️ HELPER FUNCTION: GET FILE DETAILS
# ─────────────────────────────────────────────
def get_file_details(message):
    if message.photo: return message.photo.file_id, "photo"
    if message.document: return message.document.file_id, "document"
    if message.video: return message.video.file_id, "video"
    if message.animation: return message.animation.file_id, "animation"
    if message.audio: return message.audio.file_id, "audio"
    if message.voice: return message.voice.file_id, "voice"
    if message.sticker: return message.sticker.file_id, "sticker"
    return None, "text"


# ─────────────────────────────────────────────
# ➕ ADD FILTER COMMAND (/filter)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("filter") & filters.group)
async def add_filter(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # एडमिन चेक
    if not await is_check_admin(client, chat_id, user_id):
        return await message.reply("❌ सिर्फ एडमिन ही फ़िल्टर सेट कर सकते हैं!")

    if len(message.command) < 2:
        return await message.reply("<b>इस्तेमाल:</b>\nकिसी मैसेज पर रिप्लाई करें और लिखें:\n<code>/filter keyword</code>\n\nया सीधा लिखें:\n<code>/filter keyword आपका रिप्लाई मैसेज</code>", parse_mode=enums.ParseMode.HTML)

    keyword = message.command[1].lower()
    text = ""
    file_id, file_type = None, "text"

    # अगर किसी मैसेज पर रिप्लाई किया है (Media/Text सेव करने के लिए)
    if message.reply_to_message:
        replied_msg = message.reply_to_message
        file_id, file_type = get_file_details(replied_msg)
        text = replied_msg.text or replied_msg.caption or ""
    # अगर एक ही लाइन में कमांड दिया है (उदा: /filter hi Hello bro)
    elif len(message.command) > 2:
        text = message.text.split(None, 2)[2]
    else:
        return await message.reply("❌ कृपया फ़िल्टर के लिए कोई रिप्लाई मैसेज या मीडिया सेट करें।")

    await save_filter_db(chat_id, keyword, text, file_id, file_type)
    await message.reply(f"✅ फ़िल्टर <b>{keyword}</b> सफलतापूर्वक सेव कर लिया गया है!\n\nअब जब भी कोई <code>{keyword}</code> लिखेगा, मैं रिप्लाई करूँगा।", parse_mode=enums.ParseMode.HTML)


# ─────────────────────────────────────────────
# 🛑 STOP FILTER COMMAND (/stop)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("stop") & filters.group)
async def stop_filter(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_check_admin(client, chat_id, user_id):
        return await message.reply("❌ सिर्फ एडमिन ही फ़िल्टर हटा सकते हैं!")

    if len(message.command) < 2:
        return await message.reply("<b>इस्तेमाल:</b> <code>/stop keyword</code>")

    keyword = message.command[1].lower()
    is_deleted = await delete_filter_db(chat_id, keyword)
    
    if is_deleted:
        await message.reply(f"✅ फ़िल्टर <b>{keyword}</b> डिलीट कर दिया गया है।")
    else:
        await message.reply(f"❌ <b>{keyword}</b> नाम का कोई फ़िल्टर मौजूद नहीं है।")


# ─────────────────────────────────────────────
# 📋 LIST FILTERS COMMAND (/filters)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("filters") & filters.group)
async def list_filters(client, message):
    chat_id = message.chat.id
    all_filters = await get_all_filters_db(chat_id)

    if not all_filters:
        return await message.reply("इस ग्रुप में कोई फ़िल्टर सेव नहीं है।")

    text = "<b>इस ग्रुप के एक्टिव फ़िल्टर्स:</b>\n\n"
    for f in all_filters:
        text += f"• <code>{f['keyword']}</code>\n"

    await message.reply(text, parse_mode=enums.ParseMode.HTML)


# ─────────────────────────────────────────────
# 🤖 AUTO FILTER WATCHER (Group=1)
# ─────────────────────────────────────────────
# Group=1 इसलिए सेट किया है ताकि यह दूसरे कमांड्स/सर्च के साथ-साथ बैकग्राउंड में काम करे
@Client.on_message(filters.group & filters.text & filters.incoming, group=1)
async def filter_watcher(client, message):
    if message.text.startswith("/"):
        return

    chat_id = message.chat.id
    all_filters = await get_all_filters_db(chat_id)

    if not all_filters:
        return

    message_text = message.text.lower()

    for f in all_filters:
        keyword = f["keyword"]
        # Regex \b यह पक्का करता है कि शब्द पूरा मैच हो
        # (ताकि 'bot' फ़िल्टर 'bottle' शब्द पर रिप्लाई न करे)
        pattern = r"(?i)\b" + re.escape(keyword) + r"\b"
        
        if re.search(pattern, message_text):
            text = f.get("text", "")
            file_id = f.get("file_id")
            file_type = f.get("file_type")

            try:
                # Reply Logic
                if file_type == "text":
                    await message.reply_text(text, disable_web_page_preview=True)
                elif file_type == "photo":
                    await message.reply_photo(photo=file_id, caption=text)
                elif file_type == "document":
                    await message.reply_document(document=file_id, caption=text)
                elif file_type == "video":
                    await message.reply_video(video=file_id, caption=text)
                elif file_type == "animation":
                    await message.reply_animation(animation=file_id, caption=text)
                elif file_type == "audio":
                    await message.reply_audio(audio=file_id, caption=text)
                elif file_type == "voice":
                    await message.reply_voice(voice=file_id, caption=text)
                elif file_type == "sticker":
                    await message.reply_sticker(sticker=file_id)
            except Exception:
                pass
            
            # एक बार रिप्लाई करने के बाद लूप ब्रेक करें (ताकि एक मैसेज पर 10 रिप्लाई न आएं)
            break 
