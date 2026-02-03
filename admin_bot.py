# ==========================
# ADMIN TELEGRAM BOT – FULL SYSTEM ACTIVE (SINGLE FILE)
# ==========================
# FIXED VERSION:
# ✔ Buttons working correctly (no dead callbacks)
# ✔ Channel / Group add
# ✔ Language switch (MY / EN / ZH)
# ✔ Auto Post (text)
# ✔ Statistics (real events)
# ==========================

import os
import sqlite3
import logging
import datetime
import threading
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler

import nest_asyncio
nest_asyncio.apply()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler,
    ChatMemberHandler, filters
)
from telegram.constants import ParseMode, ChatMemberStatus

# ==========================
# CONFIG
# ==========================
ADMIN_BOT_TOKEN = "8324982217:AAEQ85YcMran1X0UEirIISV831FR1jrzXG4"
ALLOWED_ADMINS = [8346273059]
DB_PATH = "storage/admin_bot.db"

# ==========================
# LOGGING
# ==========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================
# KEEP ALIVE WEB SERVER
# ==========================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active")
    def log_message(self, *args): return

def start_web_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        HTTPServer(('0.0.0.0', port), HealthCheckHandler).serve_forever()
    except:
        pass

# ==========================
# DATABASE
# ==========================
def init_db():
    os.makedirs("storage", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS stats (chat_id TEXT, date TEXT, joins INTEGER DEFAULT 0, leaves INTEGER DEFAULT 0, messages INTEGER DEFAULT 0, PRIMARY KEY(chat_id,date))")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('language','my')")
    conn.commit(); conn.close()

# ==========================
# LANGUAGE – FULL VERSION
# ==========================
LANG = {
    "my": {
        "welcome": "👋 *အက်ဒမင် ထိန်းချုပ်ရေးစင်တာ* မှ ကြိုဆိုပါတယ်။",
        "settings": "⚙️ ဆက်တင်များ",
        "stats": "📊 စာရင်းဇယား",
        "post": "🤖 အော်တိုပို့စ်",
        "lang": "🌍 ဘာသာစကား",
        "add_chat": "➕ Channel / Group ထည့်",
        "back": "🔙 နောက်သို့",
        "send_link": "Channel / Group link (သို့) @username ပို့ပါ",
        "added": "✅ အောင်မြင်စွာ ထည့်ပြီးပါပြီ",
        "send_post": "ပို့စ် စာသား ပို့ပါ",
        "send_time": "ဘယ်နှစ်မိနစ်နောက် တင်မလဲ?",
        "scheduled": "✅ ပို့စ်ကို စီစဉ်ပြီးပါပြီ",
        "stats_today": "ဒီနေ့ စာရင်းဇယား"
    },
    "en": {
        "welcome": "👋 Welcome to *Admin Control Panel*.",
        "settings": "⚙️ Settings",
        "stats": "📊 Statistics",
        "post": "🤖 Auto Post",
        "lang": "🌍 Language",
        "add_chat": "➕ Add Channel / Group",
        "back": "🔙 Back",
        "send_link": "Send channel/group link or @username",
        "added": "✅ Successfully added",
        "send_post": "Send post text",
        "send_time": "Post after how many minutes?",
        "scheduled": "✅ Post scheduled",
        "stats_today": "Today's statistics"
    },
    "zh": {
        "welcome": "👋 欢迎使用 *管理控制面板*。",
        "settings": "⚙️ 设置",
        "stats": "📊 统计",
        "post": "🤖 自动发帖",
        "lang": "🌍 语言",
        "add_chat": "➕ 添加频道 / 群组",
        "back": "返回",
        "send_link": "发送频道/群组链接 或 @用户名",
        "added": "✅ 添加成功",
        "send_post": "发送帖子内容",
        "send_time": "多少分钟后发布？",
        "scheduled": "✅ 已排期",
        "stats_today": "今日统计"
    }
}

def get_lang():
    conn = sqlite3.connect(DB_PATH)
    v = conn.execute("SELECT value FROM settings WHERE key='language'").fetchone()[0]
    conn.close(); return v

def t(k): return LANG.get(get_lang(), LANG['en']).get(k, k)

# ==========================
# UI
# ==========================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("settings"), callback_data="settings")],
        [InlineKeyboardButton(t("stats"), callback_data="stats")],
        [InlineKeyboardButton(t("post"), callback_data="post")],
        [InlineKeyboardButton(t("lang"), callback_data="lang")]
    ])

# ==========================
# COMMAND
# ==========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ALLOWED_ADMINS:
        await update.message.reply_text(t("welcome"), reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

# ==========================
# CALLBACK HANDLER
# ==========================
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "settings":
        kb = [[InlineKeyboardButton(t("add_chat"), callback_data="add_chat")],[InlineKeyboardButton(t("back"), callback_data="main")]]
        await q.edit_message_text(t("settings"), reply_markup=InlineKeyboardMarkup(kb))

    elif q.data == "stats":
        today = datetime.date.today().isoformat()
        conn = sqlite3.connect(DB_PATH)
        r = conn.execute("SELECT SUM(joins),SUM(leaves),SUM(messages) FROM stats WHERE date=?",(today,)).fetchone()
        conn.close()
        j,l,m = r if r else (0,0,0)
        await q.edit_message_text(f"{t('stats_today')}\n➕ {j}  ➖ {l}\n💬 {m}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t("back"), callback_data="main")]]))

    elif q.data == "post":
        await q.edit_message_text(t("send_post"))
        context.user_data['mode'] = 'post'

    elif q.data == "add_chat":
        await q.edit_message_text(t("send_link"))
        context.user_data['mode'] = 'add'

    elif q.data == "lang":
        kb=[[InlineKeyboardButton("🇲🇲 MY",callback_data="l_my"),InlineKeyboardButton("🇺🇸 EN",callback_data="l_en")],[InlineKeyboardButton("🇨🇳 ZH",callback_data="l_zh")],[InlineKeyboardButton(t("back"),callback_data="main")]]
        await q.edit_message_text(t("lang"), reply_markup=InlineKeyboardMarkup(kb))

    elif q.data.startswith("l_"):
        lang=q.data.split("_")[1]
        conn=sqlite3.connect(DB_PATH)
        conn.execute("UPDATE settings SET value=? WHERE key='language'",(lang,))
        conn.commit(); conn.close()
        await q.edit_message_text(t("welcome"), reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

    elif q.data == "main":
        await q.edit_message_text(t("welcome"), reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

# ==========================
# TEXT HANDLER
# ==========================
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('mode')

    if mode == 'add':
        chat = await context.bot.get_chat(update.message.text)
        conn=sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO chats VALUES (?,?)",(str(chat.id),chat.title))
        conn.commit(); conn.close()
        await update.message.reply_text(t("added"), reply_markup=main_menu())
        context.user_data.clear()

    elif mode == 'post':
        context.user_data['text']=update.message.text
        await update.message.reply_text(t("send_time"))
        context.user_data['mode']='time'

    elif mode == 'time':
        minutes=int(update.message.text)
        text=context.user_data['text']
        conn=sqlite3.connect(DB_PATH)
        chats=conn.execute("SELECT id FROM chats").fetchall()
        conn.close()
        async def job():
            for (cid,) in chats:
                try: await context.bot.send_message(cid,text)
                except: pass
        context.application.job_queue.run_once(lambda *_: asyncio.create_task(job()), minutes*60)
        await update.message.reply_text(t("scheduled"), reply_markup=main_menu())
        context.user_data.clear()

# ==========================
# STATS EVENTS
# ==========================
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    cid=str(update.effective_chat.id)
    d=datetime.date.today().isoformat()
    conn=sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO stats(chat_id,date) VALUES(?,?)",(cid,d))
    conn.execute("UPDATE stats SET messages=messages+1 WHERE chat_id=? AND date=?",(cid,d))
    conn.commit(); conn.close()

async def on_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid=str(update.chat_member.chat.id)
    d=datetime.date.today().isoformat()
    o=update.chat_member.old_chat_member.status
    n=update.chat_member.new_chat_member.status
    conn=sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO stats(chat_id,date) VALUES(?,?)",(cid,d))
    if o in (ChatMemberStatus.LEFT,ChatMemberStatus.KICKED) and n==ChatMemberStatus.MEMBER:
        conn.execute("UPDATE stats SET joins=joins+1 WHERE chat_id=? AND date=?",(cid,d))
    if o==ChatMemberStatus.MEMBER and n in (ChatMemberStatus.LEFT,ChatMemberStatus.KICKED):
        conn.execute("UPDATE stats SET leaves=leaves+1 WHERE chat_id=? AND date=?",(cid,d))
    conn.commit(); conn.close()

# ==========================
# START
# ==========================
if __name__ == '__main__':
    init_db()
    threading.Thread(target=start_web_server, daemon=True).start()
    app=ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(ChatMemberHandler(on_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ALL, on_message))
    logger.info("ADMIN BOT – FULL LANGUAGE FIXED")
    app.run_polling()
