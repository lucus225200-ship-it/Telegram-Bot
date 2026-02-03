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

# --- LANG DICT ---
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
    except Exception as e:
        logger.error(f"DB Error: {e}")
    conn.close()

# --- STATS GENERATION (LIVE DATA) ---
async def generate_stats_text(chat_id, metric_name, date_filter, context):
    if "Total Followers" in metric_name or "Followers" in metric_name or "粉丝" in metric_name:
        try:
            member_count = await context.bot.get_chat_member_count(chat_id)
            return f"📊 *{metric_name}*\n\n💎 *Current Live Count:* `{member_count}`"
        except Exception as e:
            return f"❌ Error fetching live count: {e}"

    conn = sqlite3.connect(DB_PATH)
    
    db_metric_key = "Joined" 
    if "Left" in metric_name or "ထွက်" in metric_name or "离开" in metric_name: db_metric_key = "Left"
    elif "Joined" in metric_name or "ဝင်" in metric_name or "加入" in metric_name: db_metric_key = "Joined"
    elif "Mute" in metric_name: db_metric_key = "Mute"
    elif "Unmute" in metric_name: db_metric_key = "Unmute"
    elif "Deletes" in metric_name: db_metric_key = "Msg Deletes"
    elif "Bans" in metric_name: db_metric_key = "Bans"
    
    if len(date_filter.split('-')) == 3: 
        query = "SELECT date, count FROM stats_data WHERE chat_id=? AND metric LIKE ? AND date = ?"
        param = (str(chat_id), f"%{db_metric_key}%", date_filter)
        period_label = date_filter
    else: 
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
    
    if len(date_filter.split('-')) == 2:
        text += "*🗓 Daily Breakdown:*\n"
        for date_key, count in sorted(stats_map.items()):
            day_only = date_key.split('-')[2]
            text += f"▪️ Day {day_only}:  `{count}`\n"
            
    return text

# --- TRACKING EVENTS HANDLER ---
async def track_chat_member_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.chat_member: return
    
    chat_id = update.chat_member.chat.id
    old_status = update.chat_member.old_chat_member.status
    new_status = update.chat_member.new_chat_member.status
    
    if old_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED] and \
       new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        record_stat(chat_id, "Joined")
        
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

# --- HANDLERS & COMMANDS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    await update.message.reply_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

async def setting_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, title FROM chats").fetchall()
    conn.close()
    kb = [[InlineKeyboardButton(f"⚙️ {r[1]}", callback_data=f"manage_{r[0]}")] for r in rows]
    kb.append([InlineKeyboardButton(get_t("add_chat"), callback_data="add_chat_start")])
    kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
    await update.message.reply_text("Select Chat:", reply_markup=InlineKeyboardMarkup(kb))

async def graph_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, title FROM chats").fetchall()
    conn.close()
    kb = [[InlineKeyboardButton(f"📊 {r[1]}", callback_data=f"sel_month_{r[0]}")] for r in rows]
    kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
    await update.message.reply_text(get_t("stats_select"), reply_markup=InlineKeyboardMarkup(kb))

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
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        send_msg = query.edit_message_text
    else:
        # Command case
        send_msg = update.message.reply_text
        
    conn = sqlite3.connect(DB_PATH)
    chats = conn.execute("SELECT id, title FROM chats").fetchall()
    conn.close()
    if not chats: 
        await send_msg("❌ No chats found.", reply_markup=get_main_menu())
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(c[1], callback_data=f"psel_{c[0]}")] for c in chats]
    kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
    await send_msg("📢 Select Chat:", reply_markup=InlineKeyboardMarkup(kb))
    return WAITING_POST_CONTENT

async def post_chat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['post_chat_id'] = query.data.split("_")[1]
    await query.edit_message_text(get_t("post_send"))
    return WAITING_POST_CONTENT

async def post_content_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['post_type'] = 'photo'
        context.user_data['post_content'] = {'file_id': update.message.photo[-1].file_id, 'caption': update.message.caption}
    elif update.message.video:
        context.user_data['post_type'] = 'video'
        context.user_data['post_content'] = {'file_id': update.message.video.file_id, 'caption': update.message.caption}
    else:
        context.user_data['post_type'] = 'text'
        context.user_data['post_content'] = update.message.text
    await update.message.reply_text(get_t("post_time"))
    return WAITING_POST_TIME

def parse_time(t):
    if t.lower() == 'now': return 1
    m = re.search(r'(\d+)([mh])', t.lower())
    if m:
        val, unit = int(m.group(1)), m.group(2)
        return val * 60 if unit == 'm' else val * 3600
    return 0

async def post_time_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post_delay'] = parse_time(update.message.text)
    await update.message.reply_text(get_t("post_del"))
    return WAITING_POST_DELETE

async def job_send_post(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data 
    chat_id, content, msg_type, del_delay = data['chat_id'], data['content'], data['type'], data['delete_delay']
    try:
        sent = None
        if msg_type == 'text':
            sent = await context.bot.send_message(chat_id=chat_id, text=content)
        elif msg_type == 'photo':
            sent = await context.bot.send_photo(chat_id=chat_id, photo=content['file_id'], caption=content.get('caption', ''))
        elif msg_type == 'video':
            sent = await context.bot.send_video(chat_id=chat_id, video=content['file_id'], caption=content.get('caption', ''))
        
        if sent and del_delay:
            context.job_queue.run_once(job_delete_post, del_delay, data={'chat_id': chat_id, 'msg_id': sent.message_id})
    except Exception as e:
        logger.error(f"Post Job Error: {e}")

async def job_delete_post(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.delete_message(chat_id=data['chat_id'], message_id=data['msg_id'])
    except Exception as e:
        logger.error(f"Delete Job Error: {e}")

async def post_delete_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    del_delay = None if update.message.text.lower() == 'no' else parse_time(update.message.text)
    
    context.job_queue.run_once(
        job_send_post, 
        context.user_data['post_delay'], 
        data={
            'chat_id': context.user_data['post_chat_id'],
            'content': context.user_data['post_content'],
            'type': context.user_data['post_type'],
            'delete_delay': del_delay
        }
    )
    await update.message.reply_text(get_t("post_success"), reply_markup=get_main_menu())
    return ConversationHandler.END

async def main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "main_menu":
        await query.edit_message_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)
    
    elif data == "nav_lang":
        await query.edit_message_text("Language:", reply_markup=get_lang_menu())
    
    elif data.startswith("set_lang_"):
        set_current_lang(data.split("_")[2])
        await query.answer("Updated!")
        await query.edit_message_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

    elif data == "nav_setting":
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT id, title FROM chats").fetchall()
        conn.close()
        kb = [[InlineKeyboardButton(f"⚙️ {r[1]}", callback_data=f"manage_{r[0]}")] for r in rows]
        kb.append([InlineKeyboardButton(get_t("add_chat"), callback_data="add_chat_start")])
        kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
        await query.edit_message_text("Select Chat:", reply_markup=InlineKeyboardMarkup(kb))
    
    elif data.startswith("manage_"):
        cid = data.split("_")[1]
        lang = get_current_lang()
        labels = LANG_TEXT.get(lang, LANG_TEXT['en']).get('settings_labels', LANG_TEXT['en']['settings_labels'])
        
        def btn(label, key):
            status = "✅" if get_chat_setting(cid, key) == 'ON' else "❌"
            return InlineKeyboardButton(f"{label} {status}", callback_data=f"toggle_{key}_{cid}")
        
        kb = [
            [btn(labels["comment"], "comment"), btn(labels["chat"], "chat")],
            [btn(labels["reaction"], "reaction"), btn(labels["protect"], "protect")],
            [btn(labels["ss"], "ss"), btn(labels["rc"], "rc")],
            [btn(labels["ban"], "banned_active"), btn(labels["spam"], "spam_filter")],
            [InlineKeyboardButton("➕ Add Ban Word", callback_data=f"bw_add_{cid}"),
             InlineKeyboardButton("👁️ List Ban Words", callback_data=f"bw_view_{cid}")],
            [InlineKeyboardButton(get_t("back"), callback_data="nav_setting")]
        ]
        await query.edit_message_text(f"⚙️ ID: {cid}", reply_markup=InlineKeyboardMarkup(kb))
        
    elif data.startswith("toggle_"):
        parts = data.split("_")
        cid = parts[2]
        toggle_chat_setting(cid, parts[1])
        await query.answer("Updated!")
        
        # Manually Re-render Menu (Avoids Infinite Recursion)
        lang = get_current_lang()
        labels = LANG_TEXT.get(lang, LANG_TEXT['en']).get('settings_labels', LANG_TEXT['en']['settings_labels'])
        def btn(label, key):
            status = "✅" if get_chat_setting(cid, key) == 'ON' else "❌"
            return InlineKeyboardButton(f"{label} {status}", callback_data=f"toggle_{key}_{cid}")
        kb = [
            [btn(labels["comment"], "comment"), btn(labels["chat"], "chat")],
            [btn(labels["reaction"], "reaction"), btn(labels["protect"], "protect")],
            [btn(labels["ss"], "ss"), btn(labels["rc"], "rc")],
            [btn(labels["ban"], "banned_active"), btn(labels["spam"], "spam_filter")],
            [InlineKeyboardButton("➕ Add Ban Word", callback_data=f"bw_add_{cid}"),
             InlineKeyboardButton("👁️ List Ban Words", callback_data=f"bw_view_{cid}")],
            [InlineKeyboardButton(get_t("back"), callback_data="nav_setting")]
        ]
        await query.edit_message_text(f"⚙️ ID: {cid}", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "add_chat_start":
        return # Handled by Conversation

    elif data.startswith("bw_add_"):
        return # Handled by Conversation
    
    elif data.startswith("bw_view_"):
        await bw_view_list(update, context)

    elif data == "nav_graph_chat_list":
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT id, title FROM chats").fetchall()
        conn.close()
        kb = [[InlineKeyboardButton(f"📊 {r[1]}", callback_data=f"sel_month_{r[0]}")] for r in rows]
        kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
        await query.edit_message_text(get_t("stats_select"), reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("sel_month_"):
        await query.edit_message_text(get_t("month_select"), reply_markup=get_month_menu(data.split("_")[2]))

    elif data.startswith("sel_day_"):
        parts = data.split("_")
        await query.edit_message_text(get_t("day_select"), reply_markup=get_day_menu(parts[2], parts[3]))

    elif data.startswith("sel_met_"):
        parts = data.split("_")
        await query.edit_message_text(get_t("metric_select"), reply_markup=get_metric_menu(parts[2], parts[3]))

    elif data.startswith("fin_"):
        try:
            _, payload = data.split("_", 1)
            cid, date_filter, metric = payload.split("|")
            await query.answer(get_t("graph_gen"))
            report_text = await generate_stats_text(cid, metric, date_filter, context) 
            await query.edit_message_text(
                text=report_text, 
                reply_markup=get_metric_menu(cid, date_filter),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Stats Error: {e}")
            await query.answer("Error.")

    elif data == "nav_post":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Create Post", callback_data="post_create")],
            [InlineKeyboardButton(get_t("back"), callback_data="main_menu")]
        ])
        await query.edit_message_text("Auto Post:", reply_markup=kb)

if __name__ == '__main__':
    init_db()
    keep_alive()
    
    app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('setting', setting_command))
    app.add_handler(CommandHandler('graph', graph_command))
    # Note: /post is handled by the conversation entry point below
    
    # Conversations
    conv_add_chat = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_chat_start, pattern="^add_chat_start$")],
        states={WAITING_CHAT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_chat_save)]},
        fallbacks=[CallbackQueryHandler(main_callback, pattern="^main_menu$")]
    )
    conv_bw = ConversationHandler(
        entry_points=[CallbackQueryHandler(bw_start, pattern="^bw_add_")],
        states={WAITING_BANNED_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, bw_save)]},
        fallbacks=[CallbackQueryHandler(main_callback, pattern="^main_menu$")]
    )
    conv_post = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(post_start, pattern="^post_create$"),
            CommandHandler('post', post_start)
        ],
        states={
            WAITING_POST_CONTENT: [CallbackQueryHandler(post_chat_selected, pattern="^psel_"), MessageHandler(filters.ALL & ~filters.COMMAND, post_content_rcv)],
            WAITING_POST_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_time_rcv)],
            WAITING_POST_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_delete_rcv)]
        },
        fallbacks=[CallbackQueryHandler(main_callback, pattern="^main_menu$")],
        allow_reentry=True
    )

    app.add_handler(conv_add_chat)
    app.add_handler(conv_bw)
    app.add_handler(conv_post)
    
    # Main Callback & Tracker
    app.add_handler(CallbackQueryHandler(main_callback))
    app.add_handler(ChatMemberHandler(track_chat_member_updates, ChatMemberHandler.CHAT_MEMBER))

    print("🚀
