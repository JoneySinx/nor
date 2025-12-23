import math
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from info import MAX_BTN, temp, DELETE_TIME
from utils import get_size, get_settings, get_shortlink, is_premium, get_readable_time

# ये ग्लोबल डिक्शनरी pm_filter.py में भी होनी चाहिए या utils.py में
BUTTONS = {}
CAP = {}

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
    
    try:
        offset = int(offset)
    except:
        offset = 0

    search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not search:
        return await query.answer("Send New Request Again!", show_alert=True)

    from database.ia_filterdb import get_search_results # Local import to avoid circular error
    files, n_offset, total = await get_search_results(search, offset=offset)
    
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0

    if not files:
        return
    
    temp.FILES[key] = files
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ɪɴ: <code>{get_readable_time(DELETE_TIME)}</code></b>" if settings["auto_delete"] else ''
    
    files_link = ''
    if settings['links']:
        btn = []
        for file_num, file in enumerate(files, start=offset+1):
            files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""
    else:
        btn = [[InlineKeyboardButton(text=f"{get_size(file['file_size'])} - {file['file_name']}", callback_data=f"file#{file['_id']}")] for file in files]

    # Language & Quality Buttons
    btn.insert(0, [
        InlineKeyboardButton("📰 ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}#{req}#{offset}"),
        InlineKeyboardButton("🔍 ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")
    ])
    
    # Send All Button
    if settings['shortlink'] and not await is_premium(query.from_user.id, bot):
        btn.insert(1, [InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ ♻️", url=await get_shortlink(settings['url'], settings['api'], f'https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{key}'))])
    else:
        btn.insert(1, [InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ", callback_data=f"send_all#{key}#{req}")])

    # Next/Back Logic
    off_set = 0 if 0 < offset <= MAX_BTN else (None if offset == 0 else offset - MAX_BTN)
    
    if n_offset == 0:
        btn.append([InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons")])
    elif off_set is None:
        btn.append([InlineKeyboardButton(f"{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"next_{req}_{key}_{n_offset}")])
    else:
        btn.append([InlineKeyboardButton("« ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton("ɴᴇxᴛ »", callback_data=f"next_{req}_{key}_{n_offset}")])
    
    btn.append([InlineKeyboardButton('🤑 Buy Premium', url=f"https://t.me/{temp.U_NAME}?start=premium")])
    
    await query.message.edit_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex(r"^(languages|quality|lang_search|qual_search|lang_next|qual_next)"))
async def filter_navigation(client, query):
    # यहाँ Languages और Quality वाले सभी handlers (lang_search, quality_search आदि) आएँगे
    # जो आपने pm_filter.py में भेजे थे।
    pass
