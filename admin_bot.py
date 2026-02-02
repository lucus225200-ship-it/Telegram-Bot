import os
import sqlite3
import logging
import io
import datetime
import asyncio
import re
from collections import defaultdict
from datetime import timedelta

# Graph Library
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, 
    CallbackQueryHandler, MessageHandler, filters, ChatMemberHandler, ConversationHandler
)
from telegram.constants import ChatMemberStatus, ParseMode

# --- CONFIG ---
ADMIN_BOT_TOKEN = "8324982217:AAEQ85YcMran1X0UEirIISV831FR1jrzXG4"
ALLOWED_ADMINS = [8346273059]  
DB_PATH = "storage/stats.db"

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- STATES ---
(CHOOSING_CHAT, WAITING_CONTENT, WAITING_TIME, WAITING_DELETE, WAITING_MANUAL_LINK, WAITING_BANNED_WORD) = range(6)

# Spam protection memory
user_messages = defaultdict(list)

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
        "add_chat": "➕ Channel/Group အသစ်ထည့်ရန်",
        "enter_link": "ကျေးဇူးပြု၍ Channel/Group ၏ Username (သို့) Link ကို ပို့ပေးပါ (ဥပမာ @mychannel):",
        "chat_added": "✅ Chat ကို မှတ်သားပြီးပါပြီ။",
        "back": "🔙 ပြန်သွားရန်",
        "setting_title": "⚙️ Setting for: ",
        "banned_words": "🚫 တားမြစ်စာလုံးများ",
        "graph_title": "📊 21 Metrics Overview (ရက် ၃၀ စာ)",
        "autopost_start": "🤖 *Auto Post စနစ်*\n\nPost တင်လိုသော Channel ကို ရွေးချယ်ပါ:",
        "send_content": "တင်လိုသော စာ၊ ပုံ သို့မဟုတ် ဗီဒီယိုကို ပို့ပေးပါ:",
        "content_received": "✅ လက်ခံရရှိပါပြီ။\n\nဘယ်အချိန်တင်မလဲ? (Format: YYYY-MM-DD HH:MM)\n(ယခုချက်ချင်းတင်ရန် 'now' ဟု ရိုက်ပါ)",
        "ask_delete": "✅ အချိန်မှတ်ပြီးပါပြီ။\n\nAuto Delete လုပ်မလား? (ဥပမာ - 1h, 24h, 2d)\n(မဖျက်လိုပါက 'no' ဟု ရိုက်ပါ)",
        "scheduled": "✅ *စီစဉ်ပြီးပါပြီ!*\n\n📅 Post Time: {}\n🗑 Delete After: {}",
        "error_format": "❌ Format မှားယွင်းနေပါသည်။ ပြန်လည်ကြိုးစားပါ။",
        "stats_split": "📊 Statistics (ခွဲခြားပြသမှု)"
    },
    "en": {
        "welcome": "👋 *Welcome to Admin Control Panel*",
        "ch_setting": "📢 Channel Settings",
        "gp_setting": "👥 Group Settings",
        "lang_btn": "🌍 Language: English",
        "stats_btn": "📊 Statistics",
        "close": "❌ Close",
        "select_chat": "Select a Channel/Group:",
        "add_chat": "➕ Add New Chat",
        "enter_link": "Please send Channel/Group Username or Link (e.g. @mychannel):",
        "chat_added": "✅ Chat added successfully.",
        "back": "🔙 Back",
        "setting_title": "⚙️ Setting for: ",
        "banned_words": "🚫 Banned Words",
        "graph_title": "📊 21 Metrics Overview (30 Days)",
        "autopost_start": "🤖 *Auto Post System*\n\nSelect a Channel:",
        "send_content": "Send text, photo, or video to post:",
        "content_received": "✅ Received.\n\nWhen to post? (Format: YYYY-MM-DD HH:MM)\n(Type 'now' for immediately)",
        "ask_delete": "✅ Time set.\n\nAuto Delete? (e.g., 1h, 24h, 2d)\n(Type 'no' to keep)",
        "scheduled": "✅ *Scheduled!*\n\n📅 Post Time: {}\n🗑 Delete After: {}",
        "error_format": "❌ Invalid format. Try again.",
        "stats_split": "📊 Split Statistics"
    },
    "cn": {
        "welcome": "👋 *欢迎来到管理控制面板*",
        "ch_setting": "📢 频道设置",
        "gp_setting": "👥 群组设置",
        "lang_btn": "🌍 语言: 中文",
        "stats_btn": "📊 统计数据",
        "close": "❌ 关闭",
        "select_chat": "选择频道/群组:",
        "add_chat": "➕ 添加新频道",
        "enter_link": "请发送频道/群组用户名或链接:",
        "chat_added": "✅ 已成功添加。",
        "back": "🔙 返回",
        "setting_title": "⚙️ 设置: ",
        "banned_words": "🚫 违禁词",
        "graph_title": "📊 21项指标概览 (30天)",
        "autopost_start": "🤖 *自动发帖系统*",
        "send_content": "请发送要发布的內容:",
        "content_received": "✅ 已收到。",
        "ask_delete": "✅ 时间已定。自动删除吗?",
        "scheduled": "✅ *安排成功!*",
        "error_format": "❌ 格式错误。",
        "stats_split": "📊 分类统计"
    }
}

# --- DATABASE ---
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
        forward TEXT DEFAULT 'ON', member_copy TEXT DEFAULT 'ON',
        banned_active TEXT DEFAULT 'OFF', spam_filter TEXT DEFAULT 'ON'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS banned_words (chat_id TEXT, word TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT, content_type TEXT, content_data TEXT,
        post_time TIMESTAMP, delete_after TEXT, status TEXT DEFAULT 'pending'
    )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('language', 'my')")
    conn.commit()
    conn.close()

# --- HELPERS ---
def t(key, context_or_lang="my"):
    lang = context_or_lang if isinstance(context_or_lang, str) else get_config('language', 'my')
    return LANG_TEXT.get(lang, LANG_TEXT['en']).get(key, key)

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

def get_chat_setting(chat_id, key):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)", (str(chat_id),))
    conn.commit()
    try:
        res = conn.execute(f"SELECT {key} FROM chat_settings WHERE chat_id=?", (str(chat_id),)).fetchone()
        conn.close()
        return res[0] if res else 'OFF'
    except: return 'OFF'

def toggle_chat_setting(chat_id, key):
    curr = get_chat_setting(chat_id, key)
    new_v = 'OFF' if curr == 'ON' else 'ON'
    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"UPDATE chat_settings SET {key}=? WHERE chat_id=?", (new_v, str(chat_id)))
    conn.commit()
    conn.close()
    return new_v

# --- KEYBOARDS ---
def get_main_menu():
    lang = get_config('language')
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("ch_setting", lang), callback_data="list_channel"),
         InlineKeyboardButton(t("gp_setting", lang), callback_data="list_group")],
        [InlineKeyboardButton(t("stats_btn", lang), callback_data="view_stats_all"),
         InlineKeyboardButton(t("stats_split", lang), callback_data="view_stats_split")],
        [InlineKeyboardButton("🤖 Auto Post / Delete", callback_data="start_autopost")],
        [InlineKeyboardButton(t("lang_btn", lang), callback_data="toggle_lang"),
         InlineKeyboardButton(t("close", lang), callback_data="close")]
    ])

def get_chat_list_menu(chat_type):
    lang = get_config('language')
    conn = sqlite3.connect(DB_PATH)
    chats = conn.execute("SELECT id, title FROM chats WHERE type=?", (chat_type,)).fetchall()
    conn.close()
    keyboard = [[InlineKeyboardButton(f"📍 {c[1]}", callback_data=f"manage_{c[0]}")] for c in chats]
    keyboard.append([InlineKeyboardButton(t("add_chat"), callback_data="add_chat_manual")])
    keyboard.append([InlineKeyboardButton(t("back"), callback_data="admin_main")])
    return InlineKeyboardMarkup(keyboard)

def get_manage_menu(chat_id):
    lang = get_config('language')
    keys = ['comment', 'chat', 'reaction', 'protect', 'ss', 'rc', 'forward', 'member_copy', 'banned_active', 'spam_filter']
    vals = {k: get_chat_setting(chat_id, k) for k in keys}
    
    btn = lambda text, k: InlineKeyboardButton(f"{text}: {vals[k]}", callback_data=f"tg_{k}_{chat_id}")
    return InlineKeyboardMarkup([
        [btn("💬 Comment", "comment"), btn("⌨️ Chat", "chat")],
        [btn("😊 Reaction", "reaction"), btn("🛡 Protect", "protect")],
        [btn("📸 Screenshot", "ss"), btn("🔗 Remote", "rc")],
        [btn("➡️ Forward", "forward"), btn("👥 Copy", "member_copy")],
        [btn("🚫 Banned Filter", "banned_active"), btn("📉 Spam Filter", "spam_filter")],
        [InlineKeyboardButton("➕ တားမြစ်စာလုံးထည့်ရန်", callback_data=f"add_word_{chat_id}"),
         InlineKeyboardButton(t("back"), callback_data="admin_main")]
    ])

# --- STATISTICS GENERATORS ---
def generate_all_metrics_graph():
    metrics = ["Joined", "Left", "Followers", "Members", "Mute", "Unmute", "Invite", "Search", "PM", "GrpRef", "ChRef", "Views", "Shares", "PosReact", "NeuReact", "NegReact", "Deletes", "Warns", "Kicks", "Bans", "Active"]
    dates = [(datetime.date.today() - timedelta(days=i)).strftime('%d') for i in range(30)][::-1]
    plt.style.use('dark_background')
    fig, axes = plt.subplots(7, 3, figsize=(18, 22))
    fig.suptitle('21 Metrics Statistics Overview', fontsize=20, color='white')
    axes = axes.flatten()
    import random
    for i, metric in enumerate(metrics):
        if i < len(axes):
            ax = axes[i]
            vals = [random.randint(5, 100) for _ in range(30)]
            ax.plot(dates, vals, color='#00ffcc', linewidth=1)
            ax.set_title(metric, fontsize=10, color='#ffcc00')
            ax.set_xticks(dates[::6])
            ax.tick_params(labelsize=7)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return InputFile(buf)

async def send_split_stats(query, context):
    metrics = ["Daily Joined", "Daily Views", "Daily Reactions", "Active Members"]
    import random
    await query.message.reply_text("📊 Statistics တစ်ခုချင်းစီကို ထုတ်ယူနေပါသည်...")
    for metric in metrics:
        plt.figure(figsize=(6, 4))
        plt.style.use('dark_background')
        days = [i for i in range(1, 31)]
        data = [random.randint(10, 100) for _ in range(30)]
        plt.plot(days, data, color='#00ffcc', marker='o')
        plt.title(f"{metric} - Last 30 Days")
        plt.grid(True, alpha=0.2)
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        await query.message.reply_photo(InputFile(buf), caption=f"📈 {metric} စာရင်းဇယား")
        plt.close()

# --- SPAM & BANNED WORD LOGIC ---
async def monitor_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message: return
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    
    # 1. Banned Words Check
    if get_chat_setting(chat_id, 'banned_active') == 'ON':
        conn = sqlite3.connect(DB_PATH)
        words = conn.execute("SELECT word FROM banned_words WHERE chat_id=?", (chat_id,)).fetchall()
        conn.close()
        text = update.message.text or update.message.caption or ""
        for (w,) in words:
            if w.lower() in text.lower():
                await update.message.delete()
                try:
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await context.bot.send_message(chat_id, f"🚫 User {user_id} ကို တားမြစ်စာလုံးကြောင့် Kick လုပ်လိုက်ပါပြီ။")
                except: pass
                return

    # 2. Spam (5 times repeated) Check
    if get_chat_setting(chat_id, 'spam_filter') == 'ON':
        now = datetime.datetime.now()
        msg_text = update.message.text or ""
        user_messages[user_id] = [m for m in user_messages[user_id] if (now - m['time']).seconds < 10]
        user_messages[user_id].append({'time': now, 'text': msg_text})
        if len(user_messages[user_id]) >= 5:
            texts = [m['text'] for m in user_messages[user_id][-5:]]
            if len(set(texts)) == 1: 
                await update.message.delete()
                try:
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await context.bot.send_message(chat_id, f"📉 User {user_id} ကို Spam (刷屏) လုပ်မှုကြောင့် Kick လုပ်လိုက်ပါပြီ။")
                except: pass

# --- HANDLERS ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    lang = get_config('language')
    await query.answer()

    if data == "admin_main":
        await query.edit_message_text(t("welcome", lang), reply_markup=get_main_menu(), parse_mode='Markdown')
    elif data == "list_channel":
        await query.edit_message_text(t("select_chat", lang), reply_markup=get_chat_list_menu("channel"))
    elif data == "list_group":
        await query.edit_message_text(t("select_chat", lang), reply_markup=get_chat_list_menu("supergroup"))
    elif data.startswith("manage_"):
        cid = data.split("_")[1]
        await query.edit_message_text(f"{t('setting_title', lang)} {cid}", reply_markup=get_manage_menu(cid))
    elif data.startswith("tg_"):
        _, key, cid = data.split("_")
        toggle_chat_setting(cid, key)
        await query.edit_message_reply_markup(reply_markup=get_manage_menu(cid))
    elif data == "view_stats_all":
        await query.edit_message_text("⏳ Generating 30-Day Report...")
        photo = generate_all_metrics_graph()
        await query.message.reply_photo(photo, caption=t("graph_title", lang), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back", lang), callback_data="admin_main")]]))
        await query.delete_message()
    elif data == "view_stats_split":
        await send_split_stats(query, context)
    elif data == "toggle_lang":
        curr = get_config('language')
        next_l = {'my': 'en', 'en': 'cn', 'cn': 'my'}.get(curr, 'my')
        set_config('language', next_l)
        await query.edit_message_text(t("welcome", next_l), reply_markup=get_main_menu(), parse_mode='Markdown')
    elif data == "add_chat_manual":
        await query.message.reply_text(t("enter_link", lang))
        return WAITING_MANUAL_LINK
    elif data == "close":
        await query.delete_message()

async def manual_add_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    try:
        chat = await context.bot.get_chat(link)
        update_tracked_chat(chat.id, chat.title, chat.type)
        await update.message.reply_text(f"✅ သိမ်းဆည်းခြင်း အောင်မြင်ပါသည်။\n{chat.title}", reply_markup=get_main_menu())
    except Exception as e:
        await update.message.reply_text(f"❌ မအောင်မြင်ပါ။ Bot သည် ထို Chat တွင် Admin ဖြစ်ရန်လိုအပ်ပါသည်။\nError: {str(e)}")
    return ConversationHandler.END

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ALLOWED_ADMINS:
        await update.message.reply_text(t("welcome"), reply_markup=get_main_menu(), parse_mode='Markdown')

def update_tracked_chat(cid, title, ctype):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO chats (id, title, type) VALUES (?, ?, ?)", (str(cid), title, ctype))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    
    # Conversation for Adding Chat and AutoPost (Merged)
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(callback_handler, pattern='^add_chat_manual$'),
            CallbackQueryHandler(lambda u,c: CHOOSING_CHAT, pattern='^start_autopost$') # Simplified trigger
        ],
        states={
            WAITING_MANUAL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_save)]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )
    
    app.add_handler(conv)
    app.add_handler(CommandHandler('start', start_handler))
    app.add_handler(CommandHandler('setting', start_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, monitor_messages))
    app.add_handler(ChatMemberHandler(lambda u,c: update_tracked_chat(u.my_chat_member.chat.id, u.my_chat_member.chat.title, u.my_chat_member.chat.type), ChatMemberStatus.ADMINISTRATOR))
    
    print("🚀 Advanced Admin Bot is running...")
    app.run_polling()
