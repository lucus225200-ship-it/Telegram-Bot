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

# --- CONFIG ---
ADMIN_BOT_TOKEN = "8324982217:AAEQ85YcMran1X0UEirIISV831FR1jrzXG4" 
ALLOWED_ADMINS = [8346273059]
DB_PATH = "storage/stats_v3.db"

# --- STATES ---
(
    WAITING_CHAT_LINK, 
    WAITING_POST_CONTENT, 
    WAITING_POST_TIME, 
    WAITING_POST_DELETE
) = range(4)

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- WEB SERVER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active")
    def log_message(self, format, *args): return 

def start_web_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        server.serve_forever()
    except: pass

# --- DATABASE ---
def init_db():
    os.makedirs("storage", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT, username TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS chat_settings (chat_id TEXT PRIMARY KEY, comment TEXT DEFAULT "ON", chat TEXT DEFAULT "ON", reaction TEXT DEFAULT "ON", protect TEXT DEFAULT "OFF", ss TEXT DEFAULT "ON", rc TEXT DEFAULT "OFF", banned_active TEXT DEFAULT "OFF", spam_filter TEXT DEFAULT "OFF")')
    c.execute('CREATE TABLE IF NOT EXISTS stats_data (chat_id TEXT, metric TEXT, date TEXT, count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, metric, date))')
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

# --- MULTI-LANGUAGE DICTIONARY (FULL VERSION) ---
LANG_TEXT = {
    "my": {
        "welcome": "👋 *အက်ဒမင် ထိန်းချုပ်ရေးစင်တာ* မှ ကြိုဆိုပါတယ်။",
        "menu_setting": "⚙️ ဆက်တင်များ", 
        "menu_graph": "📊 စာရင်းဇယား", 
        "menu_post": "🤖 အော်တိုပို့စ်", 
        "menu_lang": "🌍 ဘာသာစကား",
        "add_chat": "➕ ချတ်အသစ်ထည့်", 
        "back": "🔙 နောက်သို့",
        "stats_select": "📈 စာရင်းကြည့်လိုသော ချတ်ကို ရွေးပါ -",
        "month_select": "📅 လ (Month) ရွေးပါ -", 
        "day_select": "📆 ရက်စွဲ (Day) ရွေးပါ -",
        "metric_select": "🔎 အမျိုးအစား ရွေးပါ -", 
        "graph_gen": "⏳ တွက်ချက်နေပါသည်...",
        "post_send": "📝 တင်လိုသော စာသား သို့မဟုတ် ဓာတ်ပုံ ပေးပို့ပါ:",
        "post_time": "🕒 ဘယ်အချိန်မှာ တင်မလဲ? (ဥပမာ- now, 10m, 1h)",
        "post_del": "🗑 ဘယ်အချိန်မှာ ပြန်ဖျက်မလဲ? (ဥပမာ- no, 1h, 24h)",
        "post_success": "✅ ပို့စ်တင်ရန် အစီအစဉ် ဆွဲပြီးပါပြီ။",
        "chat_added": "✅ ချတ်ကို အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ!",
        "metrics": ["Joined (ဝင်)", "Left (ထွက်)", "Total Followers", "Mute", "Unmute", "Msg Deletes", "Bans"],
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "settings_labels": {
            "comment": "💬 မှတ်ချက်", "chat": "⌨️ စကားပြော", "reaction": "😊 တုံ့ပြန်မှု",
            "protect": "🛡 ကာကွယ်ရေး", "ss": "📸 ပုံရိုက်တားဆီး", "rc": "🔗 အဝေးထိန်း",
            "ban": "🚫 တားမြစ်", "spam": "📉 စပမ်း"
        }
    },
    "en": {
        "welcome": "👋 Welcome to *Admin Control Panel*.",
        "menu_setting": "⚙️ Settings", "menu_graph": "📊 Stats", "menu_post": "🤖 Auto Post", "menu_lang": "🌍 Language",
        "add_chat": "➕ Add Chat", "back": "🔙 Back",
        "stats_select": "📈 Select Chat:", "month_select": "📅 Select Month:", "day_select": "📆 Select Day:",
        "metric_select": "🔎 Select Metric:", "graph_gen": "⏳ Fetching...",
        "post_send": "📝 Send post content (Text/Photo):",
        "post_time": "🕒 When to post? (e.g., now, 10m, 1h)",
        "post_del": "🗑 When to delete? (e.g., no, 1h, 24h)",
        "post_success": "✅ Post scheduled successfully.",
        "chat_added": "✅ Chat added successfully!",
        "metrics": ["Joined", "Left", "Total Followers", "Mute", "Unmute", "Msg Deletes", "Bans"],
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "settings_labels": {
            "comment": "💬 Comments", "chat": "⌨️ Chat", "reaction": "😊 Reaction",
            "protect": "🛡 Protect", "ss": "📸 Anti-SS", "rc": "🔗 Remote",
            "ban": "🚫 Ban Words", "spam": "📉 Anti-Spam"
        }
    },
    "zh": {
        "welcome": "👋 欢迎使用 *管理控制面板*。",
        "menu_setting": "⚙️ 设置", "menu_graph": "📊 统计数据", "menu_post": "🤖 自动发帖", "menu_lang": "🌍 语言设置",
        "add_chat": "➕ 添加新聊天", "back": "返回",
        "stats_select": "📈 选择要查看统计的聊天：",
        "month_select": "📅 选择月份：", "day_select": "📆 选择日期：",
        "metric_select": "🔎 选择指标类型：", "graph_gen": "⏳ 正在获取...",
        "post_send": "📝 发送帖子内容（文字/图片）：",
        "post_time": "🕒 什么时候发布？(例如: now, 10m, 1h)",
        "post_del": "🗑 什么时候删除？(例如: no, 1h, 24h)",
        "post_success": "✅ 帖子已成功排期。",
        "chat_added": "✅ 聊天添加成功！",
        "metrics": ["加入", "离开", "总粉丝数", "静音", "取消静音", "消息删除", "封禁"],
        "months": ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"],
        "settings_labels": {
            "comment": "💬 评论", "chat": "⌨️ 聊天", "reaction": "😊 反应",
            "protect": "🛡 防护", "ss": "📸 防截屏", "rc": "🔗 远程",
            "ban": "🚫 违禁词", "spam": "📉 防刷屏"
        }
    }
}

def get_t(key):
    lang = get_current_lang()
    return LANG_TEXT.get(lang, LANG_TEXT['en']).get(key, key)

# --- KEYBOARDS ---
def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_t("menu_setting"), callback_data="nav_setting")],
        [InlineKeyboardButton(get_t("menu_graph"), callback_data="nav_graph_list")],
        [InlineKeyboardButton(get_t("menu_post"), callback_data="nav_post_start")],
        [InlineKeyboardButton(get_t("menu_lang"), callback_data="nav_lang")]
    ])

# --- COMMANDS ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ALLOWED_ADMINS:
        await update.message.reply_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

# --- CALLBACKS ---
async def main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "main_menu":
        await query.edit_message_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)
    
    elif data == "nav_lang":
        kb = [
            [InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="sl_my"), InlineKeyboardButton("🇺🇸 English", callback_data="sl_en")],
            [InlineKeyboardButton("🇨🇳 中文", callback_data="sl_zh")],
            [InlineKeyboardButton(get_t("back"), callback_data="main_menu")]
        ]
        await query.edit_message_text(get_t("choose_lang") if "choose_lang" in LANG_TEXT[get_current_lang()] else "Select Language:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif data.startswith("sl_"):
        new_lang = data[3:]
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE settings SET value=? WHERE key='language'", (new_lang,))
        conn.commit()
        conn.close()
        await query.edit_message_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)
    
    elif data == "nav_setting":
        conn = sqlite3.connect(DB_PATH)
        chats = conn.execute("SELECT id, title FROM chats").fetchall()
        conn.close()
        kb = [[InlineKeyboardButton(f"⚙️ {c[1]}", callback_data=f"manage_{c[0]}")] for c in chats]
        kb.append([InlineKeyboardButton(get_t("add_chat"), callback_data="add_chat_start")])
        kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
        await query.edit_message_text(get_t("stats_select"), reply_markup=InlineKeyboardMarkup(kb))
    
    elif data.startswith("manage_"):
        cid = data[7:]
        # Get settings for this chat
        lang = get_current_lang()
        labels = LANG_TEXT[lang]['settings_labels']
        # Simplified settings menu for Light version
        await query.edit_message_text(f"⚙️ *Managing Chat ID:* `{cid}`\n\n(Settings adjustment UI in progress...)", 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_t("back"), callback_data="nav_setting")]]),
                                    parse_mode=ParseMode.MARKDOWN)

# --- ADD CHAT FLOW ---
async def add_chat_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("⚠️ *အရင်ဆုံး Bot ကို အဲဒီ Chat မှာ Admin အဖြစ်အရင်ခန့်ပေးပါ။*\n\nပြီးရင် Chat ရဲ့ Username (@name) ဒါမှမဟုတ် Link ကို ပို့ပေးပါ -", parse_mode=ParseMode.MARKDOWN)
    return WAITING_CHAT_LINK

async def add_chat_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inp = update.message.text.split('/')[-1].replace('@', '')
    try:
        chat = await context.bot.get_chat(f"@{inp}" if not (inp.startswith('-') or inp.isdigit()) else inp)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO chats VALUES (?,?,?)", (str(chat.id), chat.title, chat.username))
        conn.execute("INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)", (str(chat.id),))
        conn.commit(); conn.close()
        await update.message.reply_text(get_t("chat_added"), reply_markup=get_main_menu())
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}\n\nBot ကို Admin ခန့်ထားတာ သေချာပါသလား? ပြန်စမ်းကြည့်ပါ (သို့မဟုတ် /cancel)")
        return WAITING_CHAT_LINK

if __name__ == '__main__':
    init_db()
    threading.Thread(target=start_web_server, daemon=True).start()
    
    app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start_cmd))
    
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_chat_init, "^add_chat_start$")],
        states={WAITING_CHAT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_chat_finish)]},
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    ))
    
    app.add_handler(CallbackQueryHandler(main_callback))
    
    logger.info("Admin Bot (Light) updated with FULL Burmese Dictionary...")
    app.run_polling(drop_pending_updates=True)
