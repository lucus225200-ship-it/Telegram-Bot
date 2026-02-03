import os
import sqlite3
import logging
import datetime
import calendar
import threading
import io
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- REQUIRED LIBRARIES ---
import nest_asyncio
import matplotlib.pyplot as plt
import numpy as np
# Apply nest_asyncio to allow nested event loops in server environments
nest_asyncio.apply()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, 
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler,
    ChatMemberHandler
)
from telegram.constants import ChatMemberStatus, ParseMode

# --- CONFIG ---
# Replace with your actual token or use environment variable
ADMIN_BOT_TOKEN = "8324982217:AAEQ85YcMran1X0UEirIISV831FR1jrzXG4" 
ALLOWED_ADMINS = [8346273059]
DB_PATH = "storage/stats_v2.db"

# --- STATES FOR CONVERSATIONS ---
(
    WAITING_CHAT_LINK,
    WAITING_BANNED_WORD,
    WAITING_POST_CONTENT,
    WAITING_POST_TIME,
    WAITING_POST_DELETE
) = range(5)

# --- LOGGING SETUP ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- WEB SERVER FOR KEEP-ALIVE ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Admin Bot is Active and Running!")
    def log_message(self, format, *args): return 

def start_web_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logger.info(f"Web server started on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start web server: {e}")

def keep_alive():
    t = threading.Thread(target=start_web_server)
    t.daemon = True
    t.start()

# --- MULTI-LANGUAGE DICTIONARY ---
LANG_TEXT = {
    "my": {
        "welcome": "👋 *အက်ဒမင် ထိန်းချုပ်ရေးစင်တာ* မှ ကြိုဆိုပါတယ်။",
        "menu_setting": "⚙️ ဆက်တင်များ", "menu_graph": "📊 စာရင်းဇယား", "menu_post": "🤖 အော်တိုပို့စ်", "menu_lang": "🌍 ဘာသာစကား",
        "add_chat": "➕ ချတ်အသစ်ထည့်", "back": "🔙 နောက်သို့",
        "stats_select": "📈 စာရင်းကြည့်လိုသော ချတ်ကို ရွေးပါ -",
        "month_select": "📅 လ (Month) ရွေးပါ -", "day_select": "📆 ရက်စွဲ (Day) ရွေးပါ -",
        "metric_select": "🔎 အမျိုးအစား ရွေးပါ -", "graph_gen": "⏳ တွက်ချက်နေပါသည်...",
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

# --- DATABASE MANAGEMENT ---
def init_db():
    os.makedirs("storage", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT, type TEXT, username TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings (chat_id TEXT PRIMARY KEY, comment TEXT DEFAULT 'ON', chat TEXT DEFAULT 'ON', reaction TEXT DEFAULT 'ON', protect TEXT DEFAULT 'OFF', ss TEXT DEFAULT 'ON', rc TEXT DEFAULT 'OFF', banned_active TEXT DEFAULT 'OFF', spam_filter TEXT DEFAULT 'OFF')''')
    c.execute('''CREATE TABLE IF NOT EXISTS banned_words (chat_id TEXT, word TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats_data (chat_id TEXT, metric TEXT, date TEXT, count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, metric, date))''')
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

def set_current_lang(lang_code):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE settings SET value=? WHERE key='language'", (lang_code,))
    conn.commit()
    conn.close()

def get_t(key):
    lang = get_current_lang()
    return LANG_TEXT.get(lang, LANG_TEXT['en']).get(key, key)

def get_chat_setting(chat_id, key):
    conn = sqlite3.connect(DB_PATH)
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

# --- STATS TRACKING ---
def record_stat(chat_id, metric, count=1):
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO stats_data (chat_id, metric, date, count) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id, metric, date) 
            DO UPDATE SET count = count + ?
        """, (str(chat_id), metric, today, count, count))
        conn.commit()
    except: pass
    conn.close()

# --- GRAPH GENERATION ---
def create_graph(dates, counts, title):
    plt.figure(figsize=(10, 5))
    plt.plot(dates, counts, marker='o', linestyle='-', color='#007bff', linewidth=2)
    plt.title(title, fontsize=14)
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Count', fontsize=12)
    plt.xticks(rotation=45)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

async def generate_stats_text(chat_id, metric_name, date_filter, context):
    if any(k in metric_name for k in ["Followers", "Total", "总粉丝"]):
        try:
            member_count = await context.bot.get_chat_member_count(chat_id)
            return f"📊 *{metric_name}*\n\n💎 *Live Followers:* `{member_count}`", None
        except: return "❌ Error fetching member count.", None

    conn = sqlite3.connect(DB_PATH)
    db_key = "Joined"
    if any(k in metric_name for k in ["Left", "ထွက်", "离开"]): db_key = "Left"
    
    if len(date_filter.split('-')) == 3: # Specific day
        query = "SELECT date, count FROM stats_data WHERE chat_id=? AND metric LIKE ? AND date = ?"
        param = (str(chat_id), f"%{db_key}%", date_filter)
    else: # Month range
        query = "SELECT date, count FROM stats_data WHERE chat_id=? AND metric LIKE ? AND date LIKE ? ORDER BY date"
        param = (str(chat_id), f"%{db_key}%", f"{date_filter}%")

    data = conn.execute(query, param).fetchall()
    conn.close()
    
    if not data:
        return f"❌ No data recorded for *{metric_name}* in `{date_filter}`.", None

    dates = [d[0] for d in data]
    counts = [d[1] for d in data]
    total = sum(counts)
    
    graph_buf = None
    if len(dates) > 1:
        graph_buf = create_graph(dates, counts, f"{metric_name} Stats ({date_filter})")

    txt = f"📊 *{metric_name}*\n📅 *Period:* `{date_filter}`\n\n💎 *Total Count:* `{total}`"
    return txt, graph_buf

# --- CORE HANDLERS ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ALLOWED_ADMINS:
        await update.message.reply_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_t("menu_setting"), callback_data="nav_setting")],
        [InlineKeyboardButton(get_t("menu_graph"), callback_data="nav_graph_list")],
        [InlineKeyboardButton(get_t("menu_post"), callback_data="nav_post_start")],
        [InlineKeyboardButton(get_t("menu_lang"), callback_data="nav_lang")]
    ])

def get_settings_kb(cid):
    lang = get_current_lang()
    labels = LANG_TEXT[lang]['settings_labels']
    def btn(l, k): return InlineKeyboardButton(f"{l} {'✅' if get_chat_setting(cid, k) == 'ON' else '❌'}", callback_data=f"t_{k}_{cid}")
    return InlineKeyboardMarkup([
        [btn(labels["comment"], "comment"), btn(labels["chat"], "chat")],
        [btn(labels["reaction"], "reaction"), btn(labels["protect"], "protect")],
        [btn(labels["ss"], "ss"), btn(labels["rc"], "rc")],
        [btn(labels["ban"], "banned_active"), btn(labels["spam"], "spam_filter")],
        [InlineKeyboardButton(get_t("back"), callback_data="nav_setting")]
    ])

# --- TRACKING MEMBER STATUS ---
async def track_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.chat_member: return
    chat_id = update.chat_member.chat.id
    status_map = {ChatMemberStatus.LEFT: "Left", ChatMemberStatus.BANNED: "Left", 
                  ChatMemberStatus.MEMBER: "Joined", ChatMemberStatus.ADMINISTRATOR: "Joined"}
    old = status_map.get(update.chat_member.old_chat_member.status)
    new = status_map.get(update.chat_member.new_chat_member.status)
    if old != new:
        if new == "Joined": record_stat(chat_id, "Joined")
        elif new == "Left": record_stat(chat_id, "Left")

# --- CALLBACK QUERY DISPATCHER ---
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
        await query.edit_message_text("Choose Language / ဘာသာစကားရွေးချယ်ပါ -", reply_markup=InlineKeyboardMarkup(kb))
    
    elif data.startswith("sl_"):
        set_current_lang(data[3:])
        await query.edit_message_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)
    
    elif data == "nav_setting":
        conn = sqlite3.connect(DB_PATH)
        chats = conn.execute("SELECT id, title FROM chats").fetchall()
        conn.close()
        kb = [[InlineKeyboardButton(f"⚙️ {c[1]}", callback_data=f"manage_{c[0]}")] for c in chats]
        kb.append([InlineKeyboardButton(get_t("add_chat"), callback_data="add_chat_start")])
        kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
        await query.edit_message_text("Select Chat for Settings:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif data.startswith("manage_"):
        cid = data[7:]
        await query.edit_message_text(f"⚙️ Managing Chat ID: `{cid}`", reply_markup=get_settings_kb(cid), parse_mode=ParseMode.MARKDOWN)
    
    elif data.startswith("t_"):
        _, k, cid = data.split("_")
        toggle_chat_setting(cid, k)
        await query.edit_message_text(f"⚙️ Managing Chat ID: `{cid}`", reply_markup=get_settings_kb(cid), parse_mode=ParseMode.MARKDOWN)

    elif data == "nav_graph_list":
        conn = sqlite3.connect(DB_PATH)
        chats = conn.execute("SELECT id, title FROM chats").fetchall()
        conn.close()
        kb = [[InlineKeyboardButton(f"📊 {c[1]}", callback_data=f"gmonth_{c[0]}")] for c in chats]
        kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
        await query.edit_message_text(get_t("stats_select"), reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("gmonth_"):
        cid = data[7:]
        now = datetime.datetime.now()
        kb = []
        months = get_t("months")
        for i, m in enumerate(months):
            kb.append(InlineKeyboardButton(m, callback_data=f"gday_{cid}_{now.year}-{i+1:02d}"))
        grid = [kb[i:i+4] for i in range(0, len(kb), 4)]
        grid.append([InlineKeyboardButton(get_t("back"), callback_data="nav_graph_list")])
        await query.edit_message_text(get_t("month_select"), reply_markup=InlineKeyboardMarkup(grid))

    elif data.startswith("gday_"):
        _, cid, ym = data.split("_")
        year, month = map(int, ym.split('-'))
        days = calendar.monthrange(year, month)[1]
        kb = [[InlineKeyboardButton("View All Month (Graph)", callback_data=f"gmet_{cid}_{ym}")]]
        row = []
        for d in range(1, days+1):
            row.append(InlineKeyboardButton(str(d), callback_data=f"gmet_{cid}_{ym}-{d:02d}"))
            if len(row) == 7:
                kb.append(row); row = []
        if row: kb.append(row)
        kb.append([InlineKeyboardButton(get_t("back"), callback_data=f"gmonth_{cid}")])
        await query.edit_message_text(get_t("day_select"), reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("gmet_"):
        _, cid, df = data.split("_")
        kb = [[InlineKeyboardButton(m, callback_data=f"fin_{cid}|{df}|{m}")] for m in get_t("metrics")]
        kb.append([InlineKeyboardButton(get_t("back"), callback_data=f"gday_{cid}_{df[:7]}")])
        await query.edit_message_text(get_t("metric_select"), reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("fin_"):
        _, p = data.split("_")
        cid, df, met = p.split("|")
        txt, graph = await generate_stats_text(cid, met, df, context)
        if graph:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=graph, caption=txt, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_t("back"), callback_data=f"gmet_{cid}_{df}")]]), parse_mode=ParseMode.MARKDOWN)

# --- ADD CHAT CONVERSATION ---
async def add_chat_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("🔗 Please send the Chat Username or Invite Link:")
    return WAITING_CHAT_LINK

async def add_chat_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_input = update.message.text.split('/')[-1].replace('@', '')
    try:
        chat = await context.bot.get_chat(chat_input)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO chats VALUES (?,?,?,?)", (str(chat.id), chat.title, chat.type, chat.username))
        conn.execute("INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)", (str(chat.id),))
        conn.commit(); conn.close()
        await update.message.reply_text(get_t("chat_added"), reply_markup=get_main_menu())
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}. Try again or /cancel")
        return WAITING_CHAT_LINK

# --- AUTO POST CONVERSATION ---
async def post_init(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    chats = conn.execute("SELECT id, title FROM chats").fetchall()
    conn.close()
    if not chats:
        await update.callback_query.answer("No chats added yet!", show_alert=True)
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(c[1], callback_data=f"ps_{c[0]}")] for c in chats]
    await update.callback_query.edit_message_text("📢 Select destination chat for Auto Post:", reply_markup=InlineKeyboardMarkup(kb))
    return WAITING_POST_CONTENT

async def post_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        context.user_data['target_cid'] = update.callback_query.data[3:]
        await update.callback_query.edit_message_text(get_t("post_send"))
        return WAITING_POST_CONTENT
    
    context.user_data['post_msg'] = update.message
    await update.message.reply_text(get_t("post_time"))
    return WAITING_POST_TIME

async def post_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_time'] = update.message.text
    await update.message.reply_text(get_t("post_del"))
    return WAITING_POST_DELETE

async def post_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This is a simplified scheduling simulation
    await update.message.reply_text(get_t("post_success"), reply_markup=get_main_menu())
    return ConversationHandler.END

# --- APP START ---
if __name__ == '__main__':
    init_db()
    keep_alive()
    
    app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler('start', start_cmd))
    app.add_handler(ChatMemberHandler(track_chat_member, ChatMemberHandler.CHAT_MEMBER))
    
    # Add Chat Conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_chat_init, "^add_chat_start$")],
        states={WAITING_CHAT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_chat_finish)]},
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    ))
    
    # Auto Post Conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(post_init, "^nav_post_start$")],
        states={
            WAITING_POST_CONTENT: [CallbackQueryHandler(post_content, "^ps_"), MessageHandler(filters.ALL & ~filters.COMMAND, post_content)],
            WAITING_POST_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_time)],
            WAITING_POST_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_final)]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    ) )
    
    app.add_handler(CallbackQueryHandler(main_callback))
    
    logger.info("Bot is starting...")
    app.run_polling()
