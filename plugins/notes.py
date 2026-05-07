import re
from hydrogram import Client, filters, enums
from motor.motor_asyncio import AsyncIOMotorClient

# आपके प्रोजेक्ट के utils से एडमिन चेक इम्पोर्ट करें
from utils import is_check_admin
from info import DATABASE_URL # या जहाँ भी आपका MongoDB URL सेव है

# ─────────────────────────────────────────────
# 🗄️ DATABASE SETUP FOR NOTES
# ─────────────────────────────────────────────
# MongoDB कनेक्शन (इसे अपने हिसाब से एडजस्ट कर सकते हैं)
db_client = AsyncIOMotorClient(DATABASE_URL)
notes_db = db_client["GroupManager"]["Notes"]

async def save_note_db(chat_id, note_name, text, file_id, file_type):
    note_data = {
        "chat_id": chat_id,
        "note_name": note_name.lower(),
        "text": text,
        "file_id": file_id,
        "file_type": file_type
    }
    # अगर नोट पहले से है तो अपडेट करें, नहीं तो नया बनाएं
    await notes_db.update_one(
        {"chat_id": chat_id, "note_name": note_name.lower()},
        {"$set": note_data},
        upsert=True
    )

async def get_note_db(chat_id, note_name):
    return await notes_db.find_one({"chat_id": chat_id, "note_name": note_name.lower()})

async def delete_note_db(chat_id, note_name):
    result = await notes_db.delete_one({"chat_id": chat_id, "note_name": note_name.lower()})
    return result.deleted_count > 0

async def get_all_notes_db(chat_id):
    notes = notes_db.find({"chat_id": chat_id})
    return [note["note_name"] async for note in notes]


# ─────────────────────────────────────────────
# 🛠️ HELPER FUNCTION: GET FILE DETAILS
# ─────────────────────────────────────────────
def get_file_details(message):
    """मैसेज से फाइल ID और टाइप निकालता है"""
    if message.photo: return message.photo.file_id, "photo"
    if message.document: return message.document.file_id, "document"
    if message.video: return message.video.file_id, "video"
    if message.animation: return message.animation.file_id, "animation"
    if message.audio: return message.audio.file_id, "audio"
    if message.voice: return message.voice.file_id, "voice"
    if message.sticker: return message.sticker.file_id, "sticker"
    return None, "text"


# ─────────────────────────────────────────────
# 📝 SAVE NOTE COMMAND (/save notename)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("save") & filters.group)
async def save_note(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # एडमिन चेक
    if not await is_check_admin(client, chat_id, user_id):
        return await message.reply("❌ सिर्फ एडमिन ही नोट्स सेव कर सकते हैं!")

    if len(message.command) < 2:
        return await message.reply("<b>इस्तेमाल का तरीका:</b>\nकिसी भी मैसेज (टेक्स्ट/फोटो) पर रिप्लाई करें और लिखें:\n<code>/save notename</code>", parse_mode=enums.ParseMode.HTML)

    note_name = message.command[1].lower()
    replied_msg = message.reply_to_message

    if not replied_msg:
        return await message.reply("❌ कृपया उस मैसेज पर रिप्लाई करें जिसे आप सेव करना चाहते हैं।")

    # फाइल और टेक्स्ट एक्सट्रेक्ट करें
    file_id, file_type = get_file_details(replied_msg)
    text = replied_msg.text or replied_msg.caption or ""

    # डेटाबेस में सेव करें
    await save_note_db(chat_id, note_name, text, file_id, file_type)
    
    await message.reply(f"✅ नोट <b>{note_name}</b> सफलतापूर्वक सेव कर लिया गया है!\n\nइसे देखने के लिए <code>#{note_name}</code> या <code>/get {note_name}</code> टाइप करें।", parse_mode=enums.ParseMode.HTML)


# ─────────────────────────────────────────────
# 🔍 GET NOTE COMMAND (/get notename OR #notename)
# ─────────────────────────────────────────────
# Regex filter Rose Bot की तरह #notename को डिटेक्ट करने के लिए
@Client.on_message((filters.command("get") | filters.regex(r"^#([a-zA-Z0-9_]+)")) & filters.group)
async def get_note(client, message):
    chat_id = message.chat.id

    # नोट का नाम निकालें (कमांड से या हैशटैग से)
    if message.text.startswith("#"):
        note_name = message.matches[0].group(1).lower()
    else:
        if len(message.command) < 2:
            return
        note_name = message.command[1].lower()

    # डेटाबेस से नोट खोजें
    note_data = await get_note_db(chat_id, note_name)
    
    if not note_data:
        # अगर # लगाकर कुछ और लिखा है (जो नोट नहीं है), तो बोट रिप्लाई नहीं करेगा
        if not message.text.startswith("#"):
            await message.reply(f"❌ <b>{note_name}</b> नाम का कोई नोट नहीं मिला।")
        return

    text = note_data.get("text", "")
    file_id = note_data.get("file_id")
    file_type = note_data.get("file_type")

    # रिप्लाई सेंड करने का लॉजिक (टेक्स्ट और मीडिया के आधार पर)
    try:
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
    except Exception as e:
        await message.reply(f"❌ नोट भेजने में एरर: {e}")


# ─────────────────────────────────────────────
# 🗑️ CLEAR NOTE COMMAND (/clear notename)
# ─────────────────────────────────────────────
@Client.on_message(filters.command("clear") & filters.group)
async def clear_note(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_check_admin(client, chat_id, user_id):
        return await message.reply("❌ सिर्फ एडमिन ही नोट्स डिलीट कर सकते हैं!")

    if len(message.command) < 2:
        return await message.reply("<b>इस्तेमाल:</b> <code>/clear notename</code>")

    note_name = message.command[1].lower()
    
    is_deleted = await delete_note_db(chat_id, note_name)
    
    if is_deleted:
        await message.reply(f"✅ नोट <b>{note_name}</b> डिलीट कर दिया गया है।")
    else:
        await message.reply(f"❌ <b>{note_name}</b> नाम का कोई नोट मौजूद नहीं है।")


# ─────────────────────────────────────────────
# 📋 LIST ALL NOTES (/notes)
# ─────────────────────────────────────────────
@Client.on_message(filters.command(["notes", "saved"]) & filters.group)
async def list_notes(client, message):
    chat_id = message.chat.id
    notes = await get_all_notes_db(chat_id)

    if not notes:
        return await message.reply("इस ग्रुप में कोई नोट्स सेव नहीं हैं।")

    text = "<b>इस ग्रुप के सेव्ड नोट्स:</b>\n\n"
    for note in notes:
        text += f"• <code>#{note}</code>\n"
        
    text += "\n<i>नोट देखने के लिए ऊपर दिए गए किसी भी नाम पर क्लिक करें या उसे टाइप करें।</i>"

    await message.reply(text, parse_mode=enums.ParseMode.HTML)
