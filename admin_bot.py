
import os
import sqlite3
import logging
import datetime
import asyncio
import random
import io
import re
import calendar
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ChatMember, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, 
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler,
    PicklePersistence, ChatMemberHandler
)
from telegram.constants import ChatMemberStatus, ParseMode

# --- CONFIG ---
ADMIN_BOT_TOKEN = "8324982217:AAEQ85YcMran1X0UEirIISV831FR1jrzXG4" 
ALLOWED_ADMINS = [8346273059]
DB_PATH = "storage/stats_v2.db"

# --- STATES ---
(
    WAITING_CHAT_LINK,
    WAITING_BANNED_WORD,
    WAITING_POST_CONTENT,
    WAITING_POST_TIME,
    WAITING_POST_DELETE
) = range(5)

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- KEEP ALIVE SERVER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(b"Admin Bot is Running!")
    def log_message(self, format, *args): return 

def start_web_server():
    try:
        server = HTTPServer(('0.0.0.0', 8080), HealthCheckHandler)
        server.serve_forever()
    except: pass

def keep_alive():
    t = threading.Thread(target=start_web_server)
    t.daemon = True
    t.start()

# --- LANG DICT (FULL VERSION) ---
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
        "enter_word": "🚫 တားမြစ်လိုသော စာလုံးကို ပေးပို့ပါ:",
        "bw_added": "✅ '{}' ကို တားမြစ်စာရင်းထဲ ထည့်လိုက်ပါပြီ။",
        "bw_list_title": "📜 *တားမြစ်ထားသော စာလုံးများ:*",
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
        "post_send": "📝 Send your post content (Text/Photo):",
        "post_time": "🕒 When to post? (e.g., now, 10m, 1h)",
        "post_del": "🗑 When to delete? (e.g., no, 1h, 24h)",
        "post_success": "✅ Post scheduled successfully.",
        "chat_added": "✅ Chat added successfully!",
        "enter_word": "🚫 Send the word to ban:",
        "bw_added": "✅ '{}' added to banned words.",
        "bw_list_title": "📜 *Banned Words List:*",
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
        "add_chat": "➕ 添加新聊天", "back": "🔙 返回",
        "stats_select": "📈 选择要查看统计的聊天：",
        "month_select": "📅 选择月份：", "day_select": "📆 选择日期 或 点击 All 查看整月：",
        "metric_select": "🔎 选择指标类型：", "graph_gen": "⏳ 正在获取统计数据...",
        "post_send": "📝 发送帖子内容（文字/图片）：",
        "post_time": "🕒 什么时候发布？(例如: now, 10m, 1h)",
        "post_del": "🗑 什么时候删除？(例如: no, 1h, 24h)",
        "post_success": "✅ 帖子已成功排期。",
        "chat_added": "✅ 聊天添加成功！",
        "enter_word": "🚫 发送要禁止的词：",
        "bw_added": "✅ '{}' 已添加到违禁词列表。",
        "bw_list_title": "📜 *违禁词列表:*",
        "metrics": ["加入 (Joined)", "离开 (Left)", "总粉丝数 (Followers)", "静音 (Mute)", "取消静音 (Unmute)", "消息删除 (Msg Deletes)", "封禁 (Bans)"],
        "months": ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"],
        "settings_labels": {
            "comment": "💬 评论", "chat": "⌨️ 聊天", "reaction": "😊 反应",
            "protect": "🛡 防护", "ss": "📸 防截屏", "rc": "🔗 远程",
            "ban": "🚫 违禁词", "spam": "📉 防刷屏"
        }
    }
}

# --- DATABASE ---
def init_db():
    os.makedirs("storage", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT, type TEXT, username TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings (chat_id TEXT PRIMARY KEY, comment TEXT DEFAULT 'ON', chat TEXT DEFAULT 'ON', reaction TEXT DEFAULT 'ON', protect TEXT DEFAULT 'OFF', ss TEXT DEFAULT 'ON', rc TEXT DEFAULT 'OFF', banned_active TEXT DEFAULT 'OFF', spam_filter TEXT DEFAULT 'OFF')''')
    c.execute('''CREATE TABLE IF NOT EXISTS banned_words (chat_id TEXT, word TEXT)''')
    # Stats Data Table
    c.execute('''CREATE TABLE IF NOT EXISTS stats_data (chat_id TEXT, metric TEXT, date TEXT, count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, metric, date))''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('language', 'my')")
    conn.commit()
    conn.close()

def get_current_lang():
    conn = sqlite3.connect(DB_PATH)
    res = conn.execute("SELECT value FROM settings WHERE key='language'").fetchone()
    conn.close()
    return res[0] if res else 'my'

def set_current_lang(lang_code):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE settings SET value=? WHERE key='language'", (lang_code,))
    conn.commit()
    conn.close()

def get_t(key):
    lang = get_current_lang()
    # Fallback logic simplified
    d = LANG_TEXT.get(lang, LANG_TEXT['en'])
    return d.get(key, key)

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

# --- REAL STATS TRACKING ---
def record_stat(chat_id, metric, count=1):
    today = datetime.date.today().isoformat() # YYYY-MM-DD
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO stats_data (chat_id, metric, date, count) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id, metric, date) 
            DO UPDATE SET count = count + ?
        """, (str(chat_id), metric, today, count, count))
        conn.commit()
    except Exception as e:
        logger.error(f"DB Error: {e}")
    conn.close()

# --- STATS GENERATION (LIVE DATA) ---
async def generate_stats_text(chat_id, metric_name, date_filter, context):
    # Special Case: Total Followers (LIVE FETCH)
    if "Total Followers" in metric_name or "Followers" in metric_name or "粉丝" in metric_name:
        try:
            member_count = await context.bot.get_chat_member_count(chat_id)
            return f"📊 *{metric_name}*\n\n💎 *Current Live Count:* `{member_count}`"
        except Exception as e:
            return f"❌ Error fetching live count: {e}"

    # For other metrics, fetch from DB (No Mock Data)
    conn = sqlite3.connect(DB_PATH)
    
    # Simple mapping to handle different languages for DB Query
    # DB stores keys like "Joined", "Left". But User sees "ဝင် (Joined)" etc.
    # We will search using English keywords if present in the metric name
    db_metric_key = "Joined" # Default fallback
    if "Left" in metric_name or "ထွက်" in metric_name or "离开" in metric_name: db_metric_key = "Left"
    elif "Joined" in metric_name or "ဝင်" in metric_name or "加入" in metric_name: db_metric_key = "Joined"
    elif "Mute" in metric_name: db_metric_key = "Mute"
    elif "Unmute" in metric_name: db_metric_key = "Unmute"
    elif "Deletes" in metric_name: db_metric_key = "Msg Deletes"
    elif "Bans" in metric_name: db_metric_key = "Bans"
    
    if len(date_filter.split('-')) == 3: # Specific Day
        query = "SELECT date, count FROM stats_data WHERE chat_id=? AND metric LIKE ? AND date = ?"
        param = (str(chat_id), f"%{db_metric_key}%", date_filter)
        period_label = date_filter
    else: # Whole Month
        query = "SELECT date, count FROM stats_data WHERE chat_id=? AND metric LIKE ? AND date LIKE ? ORDER BY date"
        param = (str(chat_id), f"%{db_metric_key}%", f"{date_filter}%")
        period_label = f"Month: {date_filter}"

    data = conn.execute(query, param).fetchall()
    conn.close()

    total_val = 0
    stats_map = {}
    
    if not data:
        return f"📊 *{metric_name}*\n📅 Period: *{period_label}*\n\n💎 *Total:* `0`\n\n(No data recorded yet for this period)"

    for d_str, c in data:
        stats_map[d_str] = c
        total_val += c

    text = f"📊 *{metric_name}*\n"
    text += f"📅 Period: *{period_label}*\n\n"
    text += f"💎 *Total:* `{total_val}`\n\n"
    
    if len(date_filter.split('-')) == 2: # Show daily breakdown for Month view
        text += "*🗓 Daily Breakdown:*\n"
        for date_key, count in sorted(stats_map.items()):
            day_only = date_key.split('-')[2]
            text += f"▪️ Day {day_only}:  `{count}`\n"
            
    return text

# --- TRACKING EVENTS HANDLER ---
async def track_chat_member_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This function records Joined/Left events in real-time
    if not update.chat_member: return
    
    chat_id = update.chat_member.chat.id
    old_status = update.chat_member.old_chat_member.status
    new_status = update.chat_member.new_chat_member.status
    
    # Joined
    if old_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED] and \
       new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        record_stat(chat_id, "Joined")
        
    # Left
    elif old_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR] and \
         new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
        record_stat(chat_id, "Left")

# --- MENUS ---
def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_t("menu_setting"), callback_data="nav_setting")],
        [InlineKeyboardButton(get_t("menu_graph"), callback_data="nav_graph_chat_list")],
        [InlineKeyboardButton(get_t("menu_post"), callback_data="nav_post")],
        [InlineKeyboardButton(get_t("menu_lang"), callback_data="nav_lang")]
    ])

def get_lang_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇲🇲 မြန်မာ (Burmese)", callback_data="set_lang_my")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")],
        [InlineKeyboardButton("🇨🇳 中文 (Chinese)", callback_data="set_lang_zh")],
        [InlineKeyboardButton(get_t("back"), callback_data="main_menu")]
    ])

def get_month_menu(chat_id):
    now = datetime.datetime.now()
    year = now.year
    months = get_t("months")
    keyboard = []
    row = []
    for i, m_name in enumerate(months):
        date_str = f"{year}-{i+1:02d}"
        row.append(InlineKeyboardButton(m_name, callback_data=f"sel_day_{chat_id}_{date_str}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(get_t("back"), callback_data="nav_graph_chat_list")])
    return InlineKeyboardMarkup(keyboard)

def get_day_menu(chat_id, year_month):
    year, month = map(int, year_month.split('-'))
    days_in_month = calendar.monthrange(year, month)[1]
    keyboard = []
    keyboard.append([InlineKeyboardButton("All Month", callback_data=f"sel_met_{chat_id}_{year_month}")])
    row = []
    for day in range(1, days_in_month + 1):
        date_str = f"{year_month}-{day:02d}"
        row.append(InlineKeyboardButton(str(day), callback_data=f"sel_met_{chat_id}_{date_str}"))
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(get_t("back"), callback_data=f"sel_month_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

def get_metric_menu(chat_id, date_filter):
    metrics = get_t("metrics")
    keyboard = []
    row = []
    for m in metrics:
        row.append(InlineKeyboardButton(m, callback_data=f"fin_{chat_id}|{date_filter}|{m}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    back_cb = f"sel_day_{chat_id}_{date_filter.rsplit('-', 1)[0]}" if len(date_filter.split('-')) == 3 else f"sel_month_{chat_id}"
    keyboard.append([InlineKeyboardButton(get_t("back"), callback_data=back_cb)])
    return InlineKeyboardMarkup(keyboard)

# --- HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    await update.message.reply_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

# --- CONVERSATION: ADD CHAT ---
async def add_chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔗 Send Chat Link or Username:")
    return WAITING_CHAT_LINK

async def add_chat_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    match = re.search(r"(?:t\.me\/|@)(\w+)", text)
    if not match:
        await update.message.reply_text("❌ Invalid format. Please send @username or t.me/link")
        return WAITING_CHAT_LINK
    
    username = f"@{match.group(1)}"
    try:
        chat = await context.bot.get_chat(username)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO chats (id, title, type, username) VALUES (?, ?, ?, ?)", 
                     (str(chat.id), chat.title, chat.type, username))
        conn.execute("INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)", (str(chat.id),))
        conn.commit()
        conn.close()
        
        kb = [[InlineKeyboardButton(get_t("back"), callback_data="nav_setting")]]
        await update.message.reply_text(get_t("chat_added"), reply_markup=InlineKeyboardMarkup(kb))
        return ConversationHandler.END
    except Exception as e:
        kb = [[InlineKeyboardButton(get_t("back"), callback_data="nav_setting")]]
        await update.message.reply_text("❌ Error: " + str(e), reply_markup=InlineKeyboardMarkup(kb))
        return ConversationHandler.END

# --- CONVERSATION: BANNED WORDS ---
async def bw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = query.data.split("_")[2]
    context.user_data['bw_chat_id'] = cid
    await query.edit_message_text(get_t("enter_word"))
    return WAITING_BANNED_WORD

async def bw_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word = update.message.text
    cid = context.user_data.get('bw_chat_id')
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO banned_words (chat_id, word) VALUES (?, ?)", (cid, word))
    conn.commit()
    conn.close()
    
    kb = [[InlineKeyboardButton(get_t("back"), callback_data=f"manage_{cid}")]]
    await update.message.reply_text(get_t("bw_added").format(word), reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

async def bw_view_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = query.data.split("_")[2]
    
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT word FROM banned_words WHERE chat_id=?", (cid,)).fetchall()
    conn.close()
    
    msg = get_t("bw_list_title") + "\n" + ("\n".join([f"• {r[0]}" for r in rows]) if rows else "Empty")
    kb = [[InlineKeyboardButton(get_t("back"), callback_data=f"manage_{cid}")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

# --- AUTO POST ---
async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = sqlite3.connect(DB_PATH)
    chats = conn.execute("SELECT id, title FROM chats").fetchall()
    conn.close()
    if not chats: 
        await query.edit_message_text("❌ No chats found.", reply_markup=get_main_menu())
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(c[1], callback_data=f"psel_{c[0]}")] for c in chats]
    kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
    await query.edit_message_text("📢 Select Chat:", reply_markup=InlineKeyboardMarkup(kb))
    return WAITING_POST_CONTENT

async def post_chat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['post_chat_id'] = query.data.split("_")[1]
    await query.edit_message_text(get_t("post_send"))
    return WAITING_POST_CONTENT

async def post_content_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE
