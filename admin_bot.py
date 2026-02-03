# ==========================
# ADMIN BOT PY (FULL FILE – COPY & PASTE READY)
# ==========================
import os
import sqlite3
import logging
import datetime
import calendar
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- REQUIRED LIBRARIES ---
import nest_asyncio
nest_asyncio.apply()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, 
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler,
    ChatMemberHandler
)
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.error import BadRequest
from collections import defaultdict
import asyncio

# ==========================
# CONFIG
# ==========================
ADMIN_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
ALLOWED_ADMINS = [8346273059]
DB_PATH = "storage/stats_v3.db"

# ==========================
# STATES
# ==========================
(
    WAITING_CHAT_LINK, 
    WAITING_POST_CONTENT, 
    WAITING_POST_TIME, 
    WAITING_POST_DELETE
) = range(4)

# ==========================
# LOGGING
# ==========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================
# WEB SERVER (KEEP ALIVE)
# ==========================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active")
    def log_message(self, format, *args):
        return

def start_web_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        server.serve_forever()
    except:
        pass

# ==========================
# DATABASE
# ==========================
def init_db():
    os.makedirs("storage", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT, username TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings (
        chat_id TEXT PRIMARY KEY,
        comment TEXT DEFAULT "ON",
        chat TEXT DEFAULT "ON",
        reaction TEXT DEFAULT "ON",
        protect TEXT DEFAULT "OFF",
        ss TEXT DEFAULT "ON",
        rc TEXT DEFAULT "OFF",
        banned_active TEXT DEFAULT "OFF",
        spam_filter TEXT DEFAULT "OFF"
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats_data (
        chat_id TEXT,
        metric TEXT,
        date TEXT,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, metric, date)
    )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('language', 'my')")
    conn.commit()
    conn.close()

# ==========================
# LANGUAGE
# ==========================
def get_current_lang():
    try:
        conn = sqlite3.connect(DB_PATH)
        res = conn.execute("SELECT value FROM settings WHERE key='language'").fetchone()
        conn.close()
        return res[0] if res else 'my'
    except:
        return 'my'

# ==========================
# ADDON FULL MULTI-LANGUAGE DICTIONARY
# ==========================
ADDON_LANG = {
    "my": {
        "welcome": "👋 *အက်ဒမင် ထိန်းချုပ်ရေးစင်တာ* မှ ကြိုဆိုပါတယ်။",
        "menu_setting": "⚙️ ဆက်တင်များ",
        "menu_graph": "📊 စာရင်းဇယား",
        "menu_post": "🤖 အော်တိုပို့စ်",
        "menu_lang": "🌍 ဘာသာစကား",
        "add_chat": "➕ ချတ်အသစ်ထည့်",
        "back": "🔙 နောက်သို့",
        "channel_settings": "📢 ချန်နယ် ဆက်တင်များ",
        "group_settings": "👥 ဂရု ဆက်တင်များ",
        "control_panel": "⚙️ ထိန်းချုပ်ရေး Panel",
        "comment": "💬 မှတ်ချက်",
        "chat": "⌨️ စကားပြော",
        "reaction": "😊 တုံ့ပြန်မှု",
        "protect": "🛡 ကာကွယ်ရေး",
        "ss": "📸 Screenshot ပိတ်",
        "rc": "🔗 Remote Control",
        "forward": "🚫 Forward",
        "member_copy": "📋 Member Copy",
        "on": "ON",
        "off": "OFF"
    },
    "en": {
        "welcome": "👋 Welcome to *Admin Control Panel*.",
        "menu_setting": "⚙️ Settings",
        "menu_graph": "📊 Statistics",
        "menu_post": "🤖 Auto Post",
        "menu_lang": "🌍 Language",
        "add_chat": "➕ Add Chat",
        "back": "🔙 Back",
        "channel_settings": "📢 Channel Settings",
        "group_settings": "👥 Group Settings",
        "control_panel": "⚙️ Control Panel",
        "comment": "💬 Comment",
        "chat": "⌨️ Chat",
        "reaction": "😊 Reaction",
        "protect": "🛡 Protect",
        "ss": "📸 Screenshot Block",
        "rc": "🔗 Remote Control",
        "forward": "🚫 Forward",
        "member_copy": "📋 Member Copy",
        "on": "ON",
        "off": "OFF"
    },
    "zh": {
        "welcome": "👋 欢迎使用 *管理控制面板*。",
        "menu_setting": "⚙️ 设置",
        "menu_graph": "📊 统计",
        "menu_post": "🤖 自动发帖",
        "menu_lang": "🌍 语言",
        "add_chat": "➕ 添加聊天",
        "back": "返回",
        "channel_settings": "📢 频道设置",
        "group_settings": "👥 群组设置",
        "control_panel": "⚙️ 控制面板",
        "comment": "💬 评论",
        "chat": "⌨️ 聊天",
        "reaction": "😊 反应",
        "protect": "🛡 防护",
        "ss": "📸 防截屏",
        "rc": "🔗 远程控制",
        "forward": "🚫 转发",
        "member_copy": "📋 成员复制",
        "on": "开启",
        "off": "关闭"
    }
}


def t(key):
    lang = get_current_lang()
    return ADDON_LANG.get(lang, ADDON_LANG['en']).get(key, key)

# ==========================
# MAIN MENU
# ==========================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("menu_setting"), callback_data="nav_setting")],
        [InlineKeyboardButton(t("menu_graph"), callback_data="nav_graph")],
        [InlineKeyboardButton(t("menu_post"), callback_data="nav_post")],
        [InlineKeyboardButton(t("menu_lang"), callback_data="nav_lang")]
    ])

# ==========================
# COMMANDS
# ==========================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ALLOWED_ADMINS:
        await update.message.reply_text(t("welcome"), reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

# ==========================
# CALLBACK HANDLER
# ==========================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    await q.answer()

    if data == "nav_setting":
        kb = [
            [InlineKeyboardButton(t("channel_settings"), callback_data="channels")],
            [InlineKeyboardButton(t("group_settings"), callback_data="groups")],
            [InlineKeyboardButton(t("back"), callback_data="main")]
        ]
        await q.edit_message_text(t("menu_setting"), reply_markup=InlineKeyboardMarkup(kb))

    elif data == "channels":
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT id,title FROM chats").fetchall()
        conn.close()
        kb = [[InlineKeyboardButton(title, callback_data=f"manage_{cid}")] for cid, title in rows]
        kb.append([InlineKeyboardButton(t("back"), callback_data="nav_setting")])
        await q.edit_message_text(t("channel_settings"), reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("manage_"):
        cid = data.split("_")[1]
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT * FROM chat_settings WHERE chat_id=?", (cid,)).fetchone()
        conn.close()
        kb = [
            [InlineKeyboardButton(f"{t('comment')} {t(row[1].lower())}", callback_data="noop"), InlineKeyboardButton(f"{t('chat')} {t(row[2].lower())}", callback_data="noop")],
            [InlineKeyboardButton(f"{t('reaction')} {t(row[3].lower())}", callback_data="noop"), InlineKeyboardButton(f"{t('protect')} {t(row[4].lower())}", callback_data="noop")],
            [InlineKeyboardButton(f"{t('ss')} {t(row[5].lower())}", callback_data="noop"), InlineKeyboardButton(f"{t('rc')} {t(row[6].lower())}", callback_data="noop")],
            [InlineKeyboardButton(t("forward"), callback_data="noop"), InlineKeyboardButton(t("member_copy"), callback_data="noop")],
            [InlineKeyboardButton(t("back"), callback_data="channels")]
        ]
        await q.edit_message_text(f"{t('control_panel')}\nID: `{cid}`", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    elif data == "main":
        await q.edit_message_text(t("welcome"), reply_markup=main_menu(), parse_mode=ParseMode.MARKDOWN)

# ==========================
# BOT START
# ==========================
if __name__ == '__main__':
    init_db()
    threading.Thread(target=start_web_server, daemon=True).start()

    app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Admin Bot started (FULL COPY VERSION)")
    app.run_polling(drop_pending_updates=True)
