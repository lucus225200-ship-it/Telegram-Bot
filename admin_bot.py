import os
import sqlite3
import logging
import io
import datetime
import asyncio
from collections import defaultdict

# Graph ဆွဲရန်လိုအပ်သော Library
import matplotlib
matplotlib.use('Agg') # Server ပေါ်တွင် run ရန် GUI မလိုသော Backend သုံးသည်
import matplotlib.pyplot as plt

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, 
    CallbackQueryHandler, MessageHandler, filters, ChatMemberHandler
)
from telegram.constants import ChatMemberStatus

# --- CONFIG ---
ADMIN_BOT_TOKEN = "8324982217:AAEQ85YcMran1X0UEirIISV831FR1jrzXG4"
ALLOWED_ADMINS = [8346273059]  
DB_PATH = "storage/stats.db"

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- LANGUAGE DICTIONARY ---
LANG_TEXT = {
    "my": {
        "welcome": "👋 *Admin Control Panel မှ ကြိုဆိုပါတယ်*",
        "ch_setting": "📢 Channel Settings",
        "gp_setting": "👥 Group Settings",
        "lang_btn": "🌍 ဘာသာစကား: မြန်မာ",
        "stats_btn": "📊 Statistics (စာရင်းဇယား)",
        "close": "❌ ပိတ်မည်",
        "select_chat": "ပြုပြင်လိုသော Channel/Group ကို ရွေးချယ်ပါ:",
        "back": "🔙 ပြန်သွားရန်",
        "setting_title": "⚙️ Setting for: ",
        "banned_words": "🚫 တားမြစ်စာလုံးများ",
        "actions": "⚖️ အရေးယူမှုများ",
        "graph_title": "📊 21 Metrics Overview",
        "no_data": "ဒေတာမရှိပါ (0)",
        "auto_post": "Auto Post စနစ်",
        "spam_detect": "⚠️ Spam Detected!"
    },
    "en": {
        "welcome": "👋 *Welcome to Admin Control Panel*",
        "ch_setting": "📢 Channel Settings",
        "gp_setting": "👥 Group Settings",
        "lang_btn": "🌍 Language: English",
        "stats_btn": "📊 Statistics",
        "close": "❌ Close",
        "select_chat": "Select a Channel/Group to edit:",
        "back": "🔙 Back",
        "setting_title": "⚙️ Setting for: ",
        "banned_words": "🚫 Banned Words",
        "actions": "⚖️ Actions",
        "graph_title": "📊 21 Metrics Overview",
        "no_data": "No Data (0)",
        "auto_post": "Auto Post System",
        "spam_detect": "⚠️ Spam Detected!"
    },
    "cn": {
        "welcome": "👋 *欢迎来到管理控制面板*",
        "ch_setting": "📢 频道设置",
        "gp_setting": "👥以此 群组设置",
        "lang_btn": "🌍 语言: 中文",
        "stats_btn": "📊 统计数据",
        "close": "❌ 关闭",
        "select_chat": "选择要编辑的频道/群组:",
        "back": "🔙 返回",
        "setting_title": "⚙️ 设置: ",
        "banned_words": "🚫 违禁词",
        "actions": "⚖️ 惩罚措施",
        "graph_title": "📊 21项 指标概览",
        "no_data": "无数据 (0)",
        "auto_post": "自动发帖系统",
        "spam_detect": "⚠️ 检测到刷屏!"
    }
}

# --- DATABASE SETUP ---
def init_db():
    os.makedirs("storage", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Global Settings
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Tracked Chats (Bot is Admin)
    c.execute('''CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT, type TEXT)''')
    
    # Chat Specific Settings (Columns: chat_id, comment, chat, reaction, protect, ss, rc, forward, copy, banned_active)
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings (
        chat_id TEXT PRIMARY KEY, 
        comment TEXT DEFAULT 'ON', 
        chat TEXT DEFAULT 'ON', 
        reaction TEXT DEFAULT 'ON', 
        protect TEXT DEFAULT 'OFF',
        ss TEXT DEFAULT 'ON',
        rc TEXT DEFAULT 'OFF',
        forward TEXT DEFAULT 'ON',
        member_copy TEXT DEFAULT 'ON',
        banned_active TEXT DEFAULT 'OFF'
    )''')
    
    # Banned Words
    c.execute('''CREATE TABLE IF NOT EXISTS banned_words (word TEXT PRIMARY KEY)''')
    
    # Statistics Data
    c.execute('''CREATE TABLE IF NOT EXISTS daily_stats (
        date DATE, 
        chat_id TEXT, 
        metric_type TEXT, 
        count INTEGER DEFAULT 0,
        PRIMARY KEY (date, chat_id, metric_type)
    )''')

    # Default Language
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('language', 'my')")
    
    conn.commit()
    conn.close()

# --- DATABASE HELPERS ---
def get_config(key, default='my'):
    conn = sqlite3.connect(DB_PATH)
    res = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return res[0] if res else default

def set_config(key, value):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_chat_setting(chat_id, setting_key):
    conn = sqlite3.connect(DB_PATH)
    # Default values map
    defaults = {'comment': 'ON', 'chat': 'ON', 'reaction': 'ON', 'protect': 'OFF', 
                'ss': 'ON', 'rc': 'OFF', 'forward': 'ON', 'member_copy': 'ON', 'banned_active': 'OFF'}
    
    # Ensure row exists
    conn.execute("INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)", (str(chat_id),))
    conn.commit()
    
    try:
        query = f"SELECT {setting_key} FROM chat_settings WHERE chat_id=?"
        res = conn.execute(query, (str(chat_id),)).fetchone()
        conn.close()
        return res[0] if res else defaults.get(setting_key, 'OFF')
    except:
        return 'OFF'

def toggle_chat_setting(chat_id, setting_key):
    curr = get_chat_setting(chat_id, setting_key)
    new_val = "OFF" if curr == "ON" else "ON"
    conn = sqlite3.connect(DB_PATH)
    query = f"UPDATE chat_settings SET {setting_key}=? WHERE chat_id=?"
    conn.execute(query, (new_val, str(chat_id)))
    conn.commit()
    conn.close()
    return new_val

def update_tracked_chat(chat_id, title, chat_type):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO chats (id, title, type) VALUES (?, ?, ?)", (str(chat_id), title, chat_type))
    conn.commit()
    conn.close()

def get_tracked_chats(chat_type=None):
    conn = sqlite3.connect(DB_PATH)
    if chat_type:
        rows = conn.execute("SELECT id, title FROM chats WHERE type=?", (chat_type,)).fetchall()
    else:
        rows = conn.execute("SELECT id, title FROM chats").fetchall()
    conn.close()
    return rows

# --- TEXT HELPER ---
def t(key, context_or_lang="my"):
    lang = context_or_lang
    if not isinstance(context_or_lang, str):
        # If context passed, fetch lang from DB
        lang = get_config('language', 'my')
    return LANG_TEXT.get(lang, LANG_TEXT['en']).get(key, key)

# --- KEYBOARDS ---
def get_main_menu():
    lang = get_config('language')
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("ch_setting", lang), callback_data="list_channel"),
         InlineKeyboardButton(t("gp_setting", lang), callback_data="list_group")],
        [InlineKeyboardButton(t("stats_btn", lang), callback_data="view_stats")],
        [InlineKeyboardButton(t("lang_btn", lang), callback_data="toggle_lang")],
        [InlineKeyboardButton(t("close", lang), callback_data="close")]
    ])

def get_chat_list_menu(chat_type):
    chats = get_tracked_chats(chat_type) # 'channel' or 'supergroup'
    keyboard = []
    # Create buttons for each chat
    for cid, title in chats:
        keyboard.append([InlineKeyboardButton(title, callback_data=f"conf_{cid}")])
    
    keyboard.append([InlineKeyboardButton(t("back"), callback_data="admin_main")])
    return InlineKeyboardMarkup(keyboard)

def get_specific_chat_menu(chat_id):
    # Retrieve all settings for this chat
    s = {k: get_chat_setting(chat_id, k) for k in ['comment', 'chat', 'reaction', 'protect', 'ss', 'rc', 'forward', 'member_copy', 'banned_active']}
    
    # Build Logic grid
    btn = lambda text, key: InlineKeyboardButton(f"{text}: {s[key]}", callback_data=f"tog_{key}_{chat_id}")
    
    layout = [
        [btn("Comment", "comment"), btn("Chat", "chat")],
        [btn("Reaction", "reaction"), btn("Protect", "protect")],
        [btn("SS", "ss"), btn("RC", "rc")],
        [btn("Forward", "forward"), btn("Copy", "member_copy")],
        [InlineKeyboardButton(f"{t('banned_words')}: {s['banned_active']}", callback_data=f"banned_menu_{chat_id}")],
        [InlineKeyboardButton(t("back"), callback_data="admin_main")] # Or back to list
    ]
    return InlineKeyboardMarkup(layout)

# --- HANDLERS ---

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    await update.message.reply_text(t("welcome"), reply_markup=get_main_menu(), parse_mode='Markdown')

# Handle Auto-Reading Channels/Groups
async def chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This detects when bot is added to channel/group or promoted
    result = update.my_chat_member
    new_status = result.new_chat_member.status
    chat = result.chat
    
    if new_status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]:
        c_type = "channel" if chat.type == "channel" else "supergroup"
        update_tracked_chat(chat.id, chat.title, c_type)
        logger.info(f"Updated Chat: {chat.title} ({chat.id})")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if user_id not in ALLOWED_ADMINS:
        await query.answer("Unauthorized", show_alert=True)
        return

    await query.answer()

    if data == "admin_main":
        await query.edit_message_text(t("welcome"), reply_markup=get_main_menu(), parse_mode='Markdown')
        
    elif data == "toggle_lang":
        curr = get_config('language')
        next_lang = {'my': 'en', 'en': 'cn', 'cn': 'my'}.get(curr, 'my')
        set_config('language', next_lang)
        await query.edit_message_text(t("welcome", next_lang), reply_markup=get_main_menu(), parse_mode='Markdown')

    elif data == "list_channel":
        await query.edit_message_text(t("select_chat"), reply_markup=get_chat_list_menu("channel"))
        
    elif data == "list_group":
        await query.edit_message_text(t("select_chat"), reply_markup=get_chat_list_menu("supergroup")) # Usually groups are supergroups

    elif data.startswith("conf_"):
        chat_id = data.split("_")[1]
        await query.edit_message_text(f"{t('setting_title')} ID: {chat_id}", reply_markup=get_specific_chat_menu(chat_id))

    elif data.startswith("tog_"):
        # Format: tog_settingname_chatid
        parts = data.split("_")
        setting = parts[1] # e.g., comment, ss
        # Handle negative chat IDs which might have extra underscores? No, telegram IDs are just numbers with minus
        # But split with _ might break if we are not careful. Python split limit.
        setting = parts[1]
        chat_id = "_".join(parts[2:]) # Rejoin the rest as ID
        
        toggle_chat_setting(chat_id, setting)
        await query.edit_message_reply_markup(reply_markup=get_specific_chat_menu(chat_id))

    elif data == "view_stats":
        await query.edit_message_text("⏳ Generating Graphs...", reply_markup=None)
        photo = generate_statistics_graph()
        await query.message.reply_photo(photo, caption=t("graph_title"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back"), callback_data="admin_main")]]))
        await query.delete_message() # Delete the "Generating" text
        
    elif data == "close":
        await query.delete_message()

# --- STATISTICS GENERATOR ---
def generate_statistics_graph():
    # 21 Metrics requested by user
    metrics = [
        "Daily Joined", "Daily Left", "Total Followers", "Total Members", 
        "Daily Mute", "Daily Unmute", "Traffic-Invite", "Traffic-Search",
        "Traffic-PM", "Traffic-GrpRef", "Traffic-ChRef", "Daily Views",
        "Daily Shares", "Pos Reactions", "Neu Reactions", "Neg Reactions",
        "Msg Deletes", "Warn Actions", "Kick Actions", "Ban Actions", "Active Members"
    ]
    
    # Mock Data Generation (Since we don't have real data yet)
    # In production, query 'daily_stats' table
    dates = [(datetime.date.today() - datetime.timedelta(days=i)).strftime('%m-%d') for i in range(7)][::-1]
    
    plt.figure(figsize=(12, 10))
    plt.style.use('ggplot')
    
    # Plotting logic
    for metric in metrics:
        # Replace this list comprehension with DB query
        # val = SELECT count FROM daily_stats WHERE metric_type=? AND date=?
        # defaulting to 0 as requested
        values = [0] * 7 
        plt.plot(dates, values, marker='o', label=metric)

    plt.title("21 Metrics Statistics (Last 7 Days)")
    plt.xlabel("Date")
    plt.ylabel("Count")
    plt.legend(bbox_to_anchor=(1.04, 1), loc="upper left", ncol=1)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return InputFile(buf, filename="stats.png")

# --- POST SCHEDULING & SPAM MOCKUP ---
async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    # This would normally open a conversation handler for Time/Content inputs
    # Implementing a simplified placeholder
    lang = get_config('language')
    msg = f"*{t('auto_post', lang)}*\n\n" \
          f"To schedule: `/post <chat_id> <content> <time>`\n" \
          f"This feature requires a JobQueue setup."
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- MESSAGE WATCHER (Spam & Banned Words) ---
async def global_message_watcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message: return
    
    chat_id = update.effective_chat.id
    msg_text = update.message.text or ""
    
    # 1. Check if Protect is ON
    protect_mode = get_chat_setting(chat_id, 'protect')
    banned_active = get_chat_setting(chat_id, 'banned_active')
    
    if protect_mode == 'ON' or banned_active == 'ON':
        # Simple Banned Word Check
        conn = sqlite3.connect(DB_PATH)
        banned = [row[0] for row in conn.execute("SELECT word FROM banned_words").fetchall()]
        conn.close()
        
        for word in banned:
            if word in msg_text:
                try:
                    await update.message.delete()
                    # Perform kick/mute based on settings (Mocked here)
                    # await context.bot.ban_chat_member(chat_id, update.effective_user.id)
                except: pass
                return

# --- MAIN EXECUTION ---
if __name__ == '__main__':
    init_db()
    
    # Create App
    application = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    
    # Add Handlers
    application.add_handler(CommandHandler('start', start_handler))
    application.add_handler(CommandHandler('setting', start_handler))
    application.add_handler(CommandHandler('stats', lambda u,c: start_handler(u,c))) # Redirect to menu
    application.add_handler(CommandHandler('post', post_command))
    
    # Admin Menu Interactions
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Auto-detect Channels/Groups
    application.add_handler(ChatMemberHandler(chat_member_update, ChatMemberStatus.ADMINISTRATOR))
    
    # Message watcher for spam/banned words
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), global_message_watcher))

    print("Admin Bot started with Extended Features...")
    application.run_polling()
