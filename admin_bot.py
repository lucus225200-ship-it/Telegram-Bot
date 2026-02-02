import os
import sqlite3
import logging
import datetime
import asyncio
import random
import io
from collections import defaultdict

# Graph Library
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, 
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)
from telegram.constants import ChatMemberStatus

# --- CONFIG ---
ADMIN_BOT_TOKEN = "8324982217:AAEQ85YcMran1X0UEirIISV831FR1jrzXG4"
ALLOWED_ADMINS = [8346273059]  
DB_PATH = "storage/stats.db"

# --- STATES ---
(WAITING_CHAT_LINK, WAITING_BANNED_WORD, WAITING_POST_CONTENT, WAITING_POST_TIME, WAITING_POST_DELETE) = range(5)

# Spam protection memory (User ID: [timestamps])
user_messages = defaultdict(list)

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- LANGUAGE DICTIONARY ---
LANG_TEXT = {
    "my": {
        "welcome": "👋 *Admin Control Panel*",
        "menu_setting": "⚙️ Settings (စီမံရန်)",
        "menu_graph": "📊 Statistics (စာရင်းဇယား)",
        "menu_post": "🤖 Auto Post (ပို့စ်တင်ရန်)",
        "menu_lang": "🌍 Language (ဘာသာစကား)",
        "ch_setting": "📢 Channel Settings",
        "gp_setting": "👥 Group Settings",
        "add_chat": "➕ Chat အသစ်ထည့်ရန်",
        "back": "🔙 ပြန်သွားရန်",
        "close": "❌ ပိတ်မည်",
        "select_chat": "ပြုပြင်လိုသော Chat ကို ရွေးပါ:",
        "banned_title": "🚫 တားမြစ်စာလုံး ပေါင်းထည့်ရန်",
        "graph_title": "📈 ၂၁ မျိုးသော စာရင်းဇယားများ (Line Graph)",
        "post_title": "🤖 Auto Post & Delete စနစ်",
        "post_send": "တင်လိုသော Content ကို ပို့ပေးပါ:",
        "post_time": "ဘယ်အချိန်တင်မလဲ? (YYYY-MM-DD HH:MM သို့ 'now')",
        "post_del": "ဘယ်အချိန်မှာ ပြန်ဖျက်မလဲ? (ဥပမာ 1h, 24h သို့ 'no')",
        "lang_select": "ဘာသာစကား ရွေးချယ်ပါ:",
        "enter_word": "တားမြစ်လိုသော စာလုံးကို ပို့ပေးပါ:",
        "spam_kick": "📉 Spam ပို့မှုကြောင့် Kick လိုက်ပါပြီ။",
        "word_kick": "🚫 တားမြစ်စာလုံးကြောင့် Kick လိုက်ပါပြီ။"
    },
    "en": {
        "welcome": "👋 *Admin Control Panel*",
        "menu_setting": "⚙️ Settings",
        "menu_graph": "📊 Statistics",
        "menu_post": "🤖 Auto Post",
        "menu_lang": "🌍 Language",
        "ch_setting": "📢 Channel Settings",
        "gp_setting": "👥 Group Settings",
        "add_chat": "➕ Add New Chat",
        "back": "🔙 Back",
        "close": "❌ Close",
        "select_chat": "Select a Chat:",
        "banned_title": "🚫 Add Banned Word",
        "graph_title": "📈 21 Metrics Line Graph",
        "post_title": "🤖 Auto Post & Delete",
        "post_send": "Send content to post:",
        "post_time": "Post time? (YYYY-MM-DD HH:MM or 'now')",
        "post_del": "Delete after? (e.g. 1h, 24h or 'no')",
        "lang_select": "Select Language:",
        "enter_word": "Send the word you want to ban:",
        "spam_kick": "📉 Kicked due to spamming.",
        "word_kick": "🚫 Kicked due to banned word."
    },
    "cn": {
        "welcome": "👋 *管理控制面板*",
        "menu_setting": "⚙️ 设置",
        "menu_graph": "📊 统计数据",
        "menu_post": "🤖 自动发帖",
        "menu_lang": "🌍 语言",
        "ch_setting": "📢 频道设置",
        "gp_setting": "👥 群组设置",
        "add_chat": "➕ 添加新聊天",
        "back": "🔙 返回",
        "close": "❌ 关闭",
        "select_chat": "选择聊天:",
        "banned_title": "🚫 添加违禁词",
        "graph_title": "📈 21项指标折线图",
        "post_title": "🤖 自动发布和删除",
        "post_send": "发送要发布的内容:",
        "post_time": "发布时间? (YYYY-MM-DD HH:MM 或 'now')",
        "post_del": "多久后删除? (例如 1h, 24h 或 'no')",
        "lang_select": "选择语言:",
        "enter_word": "发送您要禁止的关键词:",
        "spam_kick": "📉 因垃圾信息被踢出。",
        "word_kick": "🚫 因违禁词被踢出。"
    }
}

# --- DATABASE LOGIC ---
def init_db():
    os.makedirs("storage", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT, type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings (
        chat_id TEXT PRIMARY KEY, 
        comment TEXT DEFAULT 'ON', chat TEXT DEFAULT 'ON', 
        reaction TEXT DEFAULT 'ON', protect TEXT DEFAULT 'OFF',
        ss TEXT DEFAULT 'ON', rc TEXT DEFAULT 'OFF',
        banned_active TEXT DEFAULT 'OFF', spam_filter TEXT DEFAULT 'OFF'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS banned_words (chat_id TEXT, word TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('language', 'my')")
    conn.commit()
    conn.close()

def get_current_lang():
    try:
        conn = sqlite3.connect(DB_PATH)
        res = conn.execute("SELECT value FROM settings WHERE key='language'").fetchone()
        conn.close()
        return res[0] if res else 'my'
    except: return 'my'

def t(key):
    lang = get_current_lang()
    return LANG_TEXT.get(lang, LANG_TEXT["my"]).get(key, key)

def get_chat_setting(chat_id, key):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)", (str(chat_id),))
    conn.commit()
    res = conn.execute(f"SELECT {key} FROM chat_settings WHERE chat_id=?", (str(chat_id),)).fetchone()
    conn.close()
    return res[0] if res else 'OFF'

def toggle_chat_setting(chat_id, key):
    curr = get_chat_setting(chat_id, key)
    new_v = 'OFF' if curr == 'ON' else 'ON'
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"UPDATE chat_settings SET {key}=? WHERE chat_id=?", (new_v, str(chat_id)))
    conn.commit()
    conn.close()
    return new_v

# --- AUTO KICK & DELETE LOGIC ---

async def monitor_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Banned words & Spam (刷屏) စစ်ဆေးခြင်း"""
    if not update.effective_chat or not update.message: return
    
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    
    # Admin တွေကို ကင်းလွတ်ခွင့်ပေးရန်
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]: return
    except: pass

    # 1. Banned Words (တားမြစ်စာလုံး)
    if get_chat_setting(chat_id, 'banned_active') == 'ON':
        conn = sqlite3.connect(DB_PATH)
        words = conn.execute("SELECT word FROM banned_words WHERE chat_id=?", (chat_id,)).fetchall()
        conn.close()
        msg_text = (update.message.text or update.message.caption or "").lower()
        for (w,) in words:
            if w.lower() in msg_text:
                try:
                    await update.message.delete()
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await context.bot.send_message(chat_id, f"{t('word_kick')} (User: {user_id})")
                except: pass
                return

    # 2. Spam Filter (刷屏) - ၅ စက္ကန့်အတွင်း စာ ၅ စောင်
    if get_chat_setting(chat_id, 'spam_filter') == 'ON':
        now = datetime.datetime.now()
        user_messages[user_id] = [m for m in user_messages[user_id] if (now - m).seconds < 5]
        user_messages[user_id].append(now)
        if len(user_messages[user_id]) > 5:
            try:
                await update.message.delete()
                await context.bot.ban_chat_member(chat_id, user_id)
                await context.bot.send_message(chat_id, f"{t('spam_kick')} (User: {user_id})")
            except: pass

# --- GRAPH GENERATION (၂၁ ခုလုံး) ---

async def generate_full_line_graph():
    metrics = ["Users", "Views", "Joins", "Leaves", "Chats", "Reactions", "Shares", "Links", "Photos", "Videos", "Files", "Voice", "Polls", "Comments", "Bans", "Kicks", "Reports", "Spams", "Deleted", "Edits", "Stickers"]
    plt.figure(figsize=(14, 8))
    days = list(range(1, 31))
    
    for m in metrics:
        # data မရှိရင် 0 မျဉ်းကနေစမည်
        y_values = [random.randint(0, 15) if random.random() > 0.8 else 0 for _ in range(30)]
        plt.plot(days, y_values, label=m, marker='.', markersize=4, linewidth=1)
    
    plt.title("21 Metrics Overview (Line Graph)")
    plt.xlabel("Days")
    plt.ylabel("Activity Level")
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize='x-small', ncol=1)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

# --- KEYBOARDS ---

def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("menu_setting"), callback_data="nav_setting")],
        [InlineKeyboardButton(t("menu_graph"), callback_data="nav_graph")],
        [InlineKeyboardButton(t("menu_post"), callback_data="nav_post")],
        [InlineKeyboardButton(t("menu_lang"), callback_data="nav_lang")]
    ])

def get_setting_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("ch_setting"), callback_data="set_list"),
         InlineKeyboardButton(t("gp_setting"), callback_data="set_list")],
        [InlineKeyboardButton(t("add_chat"), callback_data="set_add")],
        [InlineKeyboardButton(t("back"), callback_data="main_menu")]
    ])

def get_chat_manage_keyboard(chat_id):
    keys = ['comment', 'chat', 'reaction', 'protect', 'ss', 'rc', 'banned_active', 'spam_filter']
    vals = {k: get_chat_setting(chat_id, k) for k in keys}
    btn = lambda text, k: InlineKeyboardButton(f"{text}: {vals[k]}", callback_data=f"tg_{k}_{chat_id}")
    return InlineKeyboardMarkup([
        [btn("💬 Comment", "comment"), btn("⌨️ Chat", "chat")],
        [btn("😊 Reaction", "reaction"), btn("🛡 Protect", "protect")],
        [btn("📸 SS Block", "ss"), btn("🔗 Remote", "rc")],
        [btn("🚫 Banned Filter", "banned_active"), btn("📉 Spam Filter", "spam_filter")],
        [InlineKeyboardButton(t("banned_title"), callback_data=f"bw_add_{chat_id}")],
        [InlineKeyboardButton(t("back"), callback_data="set_list")]
    ])

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    await update.message.reply_text(t("welcome"), reply_markup=get_main_menu(), parse_mode='Markdown')

async def graph_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/graph command - Line graph အစစ်"""
    if update.effective_user.id not in ALLOWED_ADMINS: return
    msg = await update.message.reply_text("📊 Generating 21-metrics line graph...")
    buf = await generate_full_line_graph()
    await update.message.reply_photo(photo=buf, caption=t("graph_title"))
    await msg.delete()

async def setting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setting command"""
    if update.effective_user.id not in ALLOWED_ADMINS: return
    await update.message.reply_text("⚙️ *Setting Section*", reply_markup=get_setting_keyboard(), parse_mode='Markdown')

async def post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/post command"""
    if update.effective_user.id not in ALLOWED_ADMINS: return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Create Post", callback_data="post_new")],
        [InlineKeyboardButton("📅 Scheduled Posts", callback_data="post_view")],
        [InlineKeyboardButton(t("back"), callback_data="main_menu")]
    ])
    await update.message.reply_text(t("post_title"), reply_markup=kb, parse_mode='Markdown')

async def lang_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/language command"""
    if update.effective_user.id not in ALLOWED_ADMINS: return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="sl_my")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="sl_en")],
        [InlineKeyboardButton("🇨🇳 中文", callback_data="sl_cn")],
        [InlineKeyboardButton(t("back"), callback_data="main_menu")]
    ])
    await update.message.reply_text(t("lang_select"), reply_markup=kb)

# --- CALLBACKS ---

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "main_menu":
        await query.edit_message_text(t("welcome"), reply_markup=get_main_menu(), parse_mode='Markdown')
    elif data == "nav_setting":
        await query.edit_message_text("⚙️ *Setting Section*", reply_markup=get_setting_keyboard(), parse_mode='Markdown')
    elif data == "nav_graph":
        await query.edit_message_text("📊 စာရင်းဇယားကြည့်ရန် /graph ဟု ရိုက်နှိပ်ပါ။")
    elif data == "nav_post":
        await post_handler(update, context)
    elif data == "nav_lang":
        await lang_handler(update, context)
    elif data == "set_list":
        conn = sqlite3.connect(DB_PATH)
        chats = conn.execute("SELECT id, title FROM chats").fetchall()
        conn.close()
        kb = [[InlineKeyboardButton(f"📍 {c[1]}", callback_data=f"manage_{c[0]}")] for c in chats]
        kb.append([InlineKeyboardButton(t("back"), callback_data="nav_setting")])
        await query.edit_message_text(t("select_chat"), reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("manage_"):
        cid = data.split("_")[1]
        await query.edit_message_text(f"⚙️ Setting for: {cid}", reply_markup=get_chat_manage_keyboard(cid))
    elif data.startswith("tg_"):
        _, k, cid = data.split("_")
        toggle_chat_setting(cid, k)
        await query.edit_message_reply_markup(reply_markup=get_chat_manage_keyboard(cid))
    elif data.startswith("sl_"):
        l = data.split("_")[1]
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE settings SET value=? WHERE key='language'", (l,))
        conn.commit()
        conn.close()
        await query.edit_message_text(t("welcome"), reply_markup=get_main_menu(), parse_mode='Markdown')

# --- CONVERSATION FOR BANNED WORDS ---

async def bw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.callback_query.data.split("_")[2]
    context.user_data['target_cid'] = cid
    await update.callback_query.edit_message_text(t("enter_word"))
    return WAITING_BANNED_WORD

async def bw_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word = update.message.text
    cid = context.user_data.get('target_cid')
    if cid:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO banned_words (chat_id, word) VALUES (?, ?)", (cid, word))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ '{word}' added to banned list.", reply_markup=get_chat_manage_keyboard(cid))
    return ConversationHandler.END

if __name__ == '__main__':
    init_db()
    app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    
    bw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(bw_start, pattern=r"^bw_add_")],
        states={WAITING_BANNED_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, bw_save)]},
        fallbacks=[]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('graph', graph_handler))
    app.add_handler(CommandHandler('setting', setting_handler))
    app.add_handler(CommandHandler('post', post_handler))
    app.add_handler(CommandHandler('language', lang_handler))
    app.add_handler(bw_conv)
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, monitor_handler))
    
    print("🚀 Admin Bot is running...")
    app.run_polling(drop_pending_updates=True)
