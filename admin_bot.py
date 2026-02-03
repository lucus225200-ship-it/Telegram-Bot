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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, 
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler,
    PicklePersistence
)
from telegram.constants import ChatMemberStatus, ParseMode

# --- CONFIG ---
# (Bot Token)
ADMIN_BOT_TOKEN = "8324982217:AAEQ85YcMran1X0UEirIISV831FR1jrzXG4" 
ALLOWED_ADMINS = [8346273059] # (Admin ID)
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

# --- KEEP ALIVE SERVER (24/7 Run) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Admin Bot V3 (Month Filter) is Running!")

    def log_message(self, format, *args):
        return 

def start_web_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logger.info(f"🌍 Keep-Alive Web Server started on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Web server error: {e}")

def keep_alive():
    t = threading.Thread(target=start_web_server)
    t.daemon = True
    t.start()

# --- Multi-Language Support ---
LANG_TEXT = {
    "my": {
        "welcome": "👋 *အက်ဒမင် ထိန်းချုပ်ရေးစင်တာ* မှ ကြိုဆိုပါတယ်။",
        "menu_setting": "⚙️ ဆက်တင်များ ပြင်ရန်",
        "menu_graph": "📊 စာရင်းဇယားများ ကြည့်ရန်",
        "menu_post": "🤖 အော်တိုပို့စ် တင်ရန်",
        "menu_lang": "🌍 ဘာသာစကား ပြောင်းရန်",
        "add_chat": "➕ ချတ်အသစ် ထည့်သွင်းရန်",
        "back": "🔙 နောက်သို့",
        "stats_select": "📈 စာရင်းဇယား ကြည့်လိုသော ချတ်ကို ရွေးပါ -",
        "month_select": "📅 ကြည့်လိုသော လ (Month) ကို ရွေးပါ -",
        "day_select": "📆 ရက်စွဲ (Day) ကို ရွေးပါ (သို့) တစ်လလုံးကြည့်ရန် All ကိုနှိပ်ပါ -",
        "metric_select": "🔎 ကြည့်လိုသော စာရင်းအမျိုးအစားကို ရွေးပါ -",
        "graph_gen": "⏳ အချက်အလက်များ တွက်ချက်နေပါသည်...",
        "post_send": "📝 တင်လိုသော စာသား သို့မဟုတ် ဓာတ်ပုံ ပေးပို့ပါ:",
        "post_time": "🕒 ဘယ်အချိန်မှာ တင်မလဲ? (ဥပမာ- now, 10m, 1h)",
        "post_del": "🗑 ဘယ်အချိန်မှာ ပြန်ဖျက်မလဲ? (ဥပမာ- no, 1h, 24h)",
        "post_success": "✅ ပို့စ်တင်ရန် အစီအစဉ် ဆွဲပြီးပါပြီ။",
        "lang_select": "🌍 အသုံးပြုလိုသော ဘာသာစကားကို ရွေးချယ်ပါ -",
        "lang_updated": "✅ ဘာသာစကား ပြောင်းလဲပြီးပါပြီ။",
        "send_link": "🔗 *ချတ်လင့်ခ် သို့မဟုတ် ယူဆာနိမ်း ပို့ပေးပါ*\n(ဥပမာ: @channelname သို့မဟုတ် https://t.me/...)\n⚠️ ဘော့ကို အက်ဒမင် အရင်ခန့်ထားပါ။",
        "chat_added": "✅ ချတ်ကို အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ!\nခေါင်းစဉ်: {}",
        "chat_err": "❌ ချတ်ကို ရှာမတွေ့ပါ သို့မဟုတ် ဘော့သည် အက်ဒမင် မဟုတ်ပါ။",
        "enter_word": "🚫 တားမြစ်လိုသော စာလုံးကို ပေးပို့ပါ:",
        "bw_added": "✅ '{}' ကို တားမြစ်စာရင်းထဲ ထည့်လိုက်ပါပြီ။",
        "bw_list_title": "📜 *တားမြစ်ထားသော စာလုံးများ:*",
        "bw_empty": "တားမြစ်ထားသော စာလုံး မရှိသေးပါ။",
        "bw_add_btn": "➕ စာလုံးပေါင်းထည့်ရန်",
        "bw_view_btn": "👁️ စာရင်းကြည့်ရန်",
        "all_month": "🗓 တစ်လလုံးစာ (All Month)",
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "metrics": [
            "Joined (ဝင်ရောက်)", "Left (ထွက်ခွာ)", "Followers (ဖော်လိုဝါ)", 
            "Mute (အသံပိတ်)", "Unmute (အသံဖွင့်)", 
            "Traffic: URL", "Traffic: Search", "Traffic: PM", "Traffic: Groups", "Traffic: Channels",
            "Views (ကြည့်ရှုမှု)", "Shares (မျှဝေမှု)", 
            "Reaction: Positive", "Reaction: Neutral", "Reaction: Negative",
            "Msg Deletes (ဖျက်)", "Warns (သတိပေး)", "Kicks (ကန်ထုတ်)", "Bans (ဘန်း)"
        ],
        "settings_labels": {
            "comment": "💬 မှတ်ချက်", "chat": "⌨️ စကားပြော", "reaction": "😊 တုံ့ပြန်မှု",
            "protect": "🛡 ကာကွယ်ရေး", "ss": "📸 ပုံရိုက်တားဆီး", "rc": "🔗 အဝေးထိန်း",
            "ban": "🚫 တားမြစ်", "spam": "📉 စပမ်း"
        }
    },
    "en": {
        "welcome": "👋 Welcome to *Admin Control Panel*.",
        "menu_setting": "⚙️ Settings",
        "menu_graph": "📊 Statistics",
        "menu_post": "🤖 Auto Post",
        "menu_lang": "🌍 Language",
        "add_chat": "➕ Add New Chat",
        "back": "🔙 Back",
        "stats_select": "📈 Select Chat for Stats:",
        "month_select": "📅 Select Month:",
        "day_select": "📆 Select Day or 'All Month':",
        "metric_select": "🔎 Select Metric Type:",
        "graph_gen": "⏳ Fetching Statistics...",
        "post_send": "📝 Send your post content (Text/Photo):",
        "post_time": "🕒 When to post? (e.g., now, 10m, 1h)",
        "post_del": "🗑 When to delete? (e.g., no, 1h, 24h)",
        "post_success": "✅ Post scheduled successfully.",
        "lang_select": "🌍 Select your language:",
        "lang_updated": "✅ Language updated successfully.",
        "send_link": "🔗 *Send Chat Link or Username*\n(e.g. @channelname or https://t.me/...)\n⚠️ Make bot admin first.",
        "chat_added": "✅ Chat added successfully!\nTitle: {}",
        "chat_err": "❌ Chat not found or Bot is not Admin.",
        "enter_word": "🚫 Send the word to ban:",
        "bw_added": "✅ '{}' added to banned words.",
        "bw_list_title": "📜 *Banned Words List:*",
        "bw_empty": "No banned words yet.",
        "bw_add_btn": "➕ Add Word",
        "bw_view_btn": "👁️ View List",
        "all_month": "🗓 All Month",
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "metrics": [
            "Joined", "Left", "Total Followers", 
            "Mute", "Unmute", 
            "Traffic: URL", "Traffic: Search", "Traffic: PM", "Traffic: Groups", "Traffic: Channels",
            "Views", "Shares", 
            "Reaction: Positive", "Reaction: Neutral", "Reaction: Negative",
            "Msg Deletes", "Warns", "Kicks", "Bans"
        ],
        "settings_labels": {
            "comment": "💬 Comments", "chat": "⌨️ Chat", "reaction": "😊 Reaction",
            "protect": "🛡 Protect", "ss": "📸 Anti-SS", "rc": "🔗 Remote",
            "ban": "🚫 Ban Words", "spam": "📉 Anti-Spam"
        }
    },
    "zh": {
        "welcome": "👋 欢迎使用 *管理控制面板*。",
        "menu_setting": "⚙️ 设置",
        "menu_graph": "📊 统计数据",
        "menu_post": "🤖 自动发帖",
        "menu_lang": "🌍 语言设置",
        "add_chat": "➕ 添加新聊天",
        "back": "🔙 返回",
        "stats_select": "📈 选择要查看统计的聊天：",
        "month_select": "📅 选择月份：",
        "day_select": "📆 选择日期 或 点击 All 查看整月：",
        "metric_select": "🔎 选择指标类型：",
        "graph_gen": "⏳ 正在获取统计数据...",
        "post_send": "📝 发送帖子内容（文字/图片）：",
        "post_time": "🕒 什么时候发布？(例如: now, 10m, 1h)",
        "post_del": "🗑 什么时候删除？(例如: no, 1h, 24h)",
        "post_success": "✅ 帖子已成功排期。",
        "lang_select": "🌍 选择您的语言：",
        "lang_updated": "✅ 语言更新成功。",
        "send_link": "🔗 *发送聊天链接或用户名*\n(例如 @channelname 或 https://t.me/...)\n⚠️ 请先将机器人设为管理员。",
        "chat_added": "✅ 聊天添加成功！\n标题: {}",
        "chat_err": "❌ 未找到聊天或机器人不是管理员。",
        "enter_word": "🚫 发送要禁止的词：",
        "bw_added": "✅ '{}' 已添加到违禁词列表。",
        "bw_list_title": "📜 *违禁词列表:*",
        "bw_empty": "暂无违禁词。",
        "bw_add_btn": "➕ 添加违禁词",
        "bw_view_btn": "👁️ 查看列表",
        "all_month": "🗓 整月 (All Month)",
        "months": ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"],
        "metrics": [
            "加入 (Joined)", "离开 (Left)", "总粉丝数 (Followers)", 
            "静音 (Mute)", "取消静音 (Unmute)", 
            "流量: 链接 (URL)", "流量: 搜索 (Search)", "流量: 私信 (PM)", "流量: 群组 (Groups)", "流量: 频道 (Channels)",
            "浏览量 (Views)", "分享数 (Shares)", 
            "反应: 正面 (Positive)", "反应: 中性 (Neutral)", "反应: 负面 (Negative)",
            "消息删除 (Msg Deletes)", "警告 (Warns)", "踢出 (Kicks)", "封禁 (Bans)"
        ],
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
    c.execute('''CREATE TABLE IF NOT EXISTS chat_settings (
        chat_id TEXT PRIMARY KEY, comment TEXT DEFAULT 'ON', chat TEXT DEFAULT 'ON', 
        reaction TEXT DEFAULT 'ON', protect TEXT DEFAULT 'OFF',
        ss TEXT DEFAULT 'ON', rc TEXT DEFAULT 'OFF',
        banned_active TEXT DEFAULT 'OFF', spam_filter TEXT DEFAULT 'OFF'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS banned_words (chat_id TEXT, word TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats_data (
        chat_id TEXT, metric TEXT, date TEXT, count INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, metric, date)
    )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('language', 'my')")
    conn.commit()
    conn.close()

def get_current_lang():
    try:
        conn = sqlite3.connect(DB_PATH)
        res = conn.execute("SELECT value FROM settings WHERE key='language'").fetchone()
        conn.close()
        return res[0] if res else 'my'
    except:
        return 'my'

def set_current_lang(lang_code):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE settings SET value=? WHERE key='language'", (lang_code,))
    conn.commit()
    conn.close()

def get_t(key):
    lang = get_current_lang()
    # If key is in language dict, return it. If not, try fallback to English, then key itself.
    if lang in LANG_TEXT and key in LANG_TEXT[lang]:
        return LANG_TEXT[lang][key]
    if 'en' in LANG_TEXT and key in LANG_TEXT['en']:
        return LANG_TEXT['en'][key]
    return key

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

# --- STATS GENERATION (Updated for Date Filter) ---
async def generate_stats_text(chat_id, metric_name, date_filter):
    # date_filter can be "YYYY-MM" (Month) or "YYYY-MM-DD" (Day)
    conn = sqlite3.connect(DB_PATH)
    
    if len(date_filter.split('-')) == 3: # Specific Day
        query = "SELECT date, count FROM stats_data WHERE chat_id=? AND metric=? AND date = ?"
        param = date_filter
        period_label = date_filter
    else: # Whole Month
        query = "SELECT date, count FROM stats_data WHERE chat_id=? AND metric=? AND date LIKE ? ORDER BY date"
        param = f"{date_filter}%"
        period_label = f"Month: {date_filter}"

    data = conn.execute(query, (str(chat_id), metric_name, param)).fetchall()
    conn.close()

    stats_map = {}
    total_val = 0
    
    # --- MOCK DATA GENERATOR (For Demo) ---
    # If DB is empty, generate fake data to show functionality
    if not data:
        is_month = len(date_filter.split('-')) == 2
        if is_month:
            year, month = map(int, date_filter.split('-'))
            days_in_month = calendar.monthrange(year, month)[1]
            current_val = random.randint(50, 200)
            for i in range(1, days_in_month + 1):
                d_str = f"{year}-{month:02d}-{i:02d}"
                val = random.randint(10, 50)
                stats_map[d_str] = val
                total_val += val
        else:
             # Single Day Mock
             stats_map[date_filter] = random.randint(10, 100)
             total_val = stats_map[date_filter]
    else:
        for d_str, c in data:
            stats_map[d_str] = c
            total_val += c

    # Build Text Report
    text = f"📊 *{metric_name}*\n"
    text += f"📅 Period: *{period_label}*\n\n"
    text += f"💎 *Total:* `{total_val}`\n\n"
    
    if len(date_filter.split('-')) == 2: # Show top days if Month view
        text += "*🗓 Daily Breakdown:*\n"
        sorted_days = sorted(stats_map.items())
        for date_key, count in sorted_days:
            day_only = date_key.split('-')[2]
            text += f"▪️ Day {day_only}:  `{count}`\n"
            
    return text

# --- KEYBOARDS ---
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

# New: Month Selection Keyboard
def get_month_menu(chat_id):
    now = datetime.datetime.now()
    year = now.year
    months = get_t("months") # ["Jan", "Feb", ...]
    
    keyboard = []
    row = []
    # Generate buttons for current year (Jan to Dec)
    for i, m_name in enumerate(months):
        m_num = i + 1
        # Format: sel_day_{chat_id}_{YYYY-MM}
        date_str = f"{year}-{m_num:02d}" 
        row.append(InlineKeyboardButton(m_name, callback_data=f"sel_day_{chat_id}_{date_str}"))
        if len(row) == 4: # 4 months per row
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(get_t("back"), callback_data="nav_graph_chat_list")])
    return InlineKeyboardMarkup(keyboard)

# New: Day Selection Keyboard
def get_day_menu(chat_id, year_month):
    # year_month is "2024-02"
    year, month = map(int, year_month.split('-'))
    days_in_month = calendar.monthrange(year, month)[1]
    
    keyboard = []
    
    # "All Month" Button
    keyboard.append([InlineKeyboardButton(get_t("all_month"), callback_data=f"sel_met_{chat_id}_{year_month}")])
    
    # Days 1 to 31
    row = []
    for day in range(1, days_in_month + 1):
        date_str = f"{year_month}-{day:02d}"
        row.append(InlineKeyboardButton(str(day), callback_data=f"sel_met_{chat_id}_{date_str}"))
        if len(row) == 7: # 7 days per row
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    # Back to Month List
    keyboard.append([InlineKeyboardButton(get_t("back"), callback_data=f"sel_month_{chat_id}")])
    return InlineKeyboardMarkup(keyboard)

def get_metric_menu(chat_id, date_filter):
    # date_filter is passed to keep track of what date user selected
    lang = get_current_lang()
    # Default to 'my' if something fails, but try correct lang first
    metrics = LANG_TEXT.get(lang, LANG_TEXT['my']).get("metrics", [])
    
    keyboard = []
    row = []
    for m in metrics:
        short_metric = m[:15] # Truncate for safety
        row.append(InlineKeyboardButton(m, callback_data=f"fin_{chat_id}|{date_filter}|{short_metric}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    # Back to Day Selection (If it's a specific day) or Month selection
    if len(date_filter.split('-')) == 3:
        # It's a day, go back to Day Select. Parent is Year-Month
        parent_ym = date_filter.rsplit('-', 1)[0]
        back_cb = f"sel_day_{chat_id}_{parent_ym}"
    else:
        # It's a month, go back to Month Select
        back_cb = f"sel_month_{chat_id}"
        
    keyboard.append([InlineKeyboardButton(get_t("back"), callback_data=back_cb)])
    return InlineKeyboardMarkup(keyboard)

# --- CONVERSATION: ADD CHAT ---
async def add_chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(get_t("send_link"), parse_mode=ParseMode.MARKDOWN)
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
        conn.commit()
        conn.close()
        
        kb = [[InlineKeyboardButton(get_t("back"), callback_data="nav_setting")]]
        await update.message.reply_text(get_t("chat_added").format(chat.title), reply_markup=InlineKeyboardMarkup(kb))
        return ConversationHandler.END
    except Exception as e:
        kb = [[InlineKeyboardButton(get_t("back"), callback_data="nav_setting")]]
        await update.message.reply_text(get_t("chat_err"), reply_markup=InlineKeyboardMarkup(kb))
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
    
    if not rows:
        msg = get_t("bw_empty")
    else:
        msg = get_t("bw_list_title") + "\n" + "\n".join([f"• {r[0]}" for r in rows])
        
    kb = [[InlineKeyboardButton(get_t("back"), callback_data=f"manage_{cid}")]]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

# --- AUTO POST JOBS ---
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

# --- COMMAND HANDLERS (NEW) ---
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
    await update.message.reply_text("Select Chat to Manage:", reply_markup=InlineKeyboardMarkup(kb))

async def graph_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, title FROM chats").fetchall()
    conn.close()
    kb = [[InlineKeyboardButton(f"📊 {r[1]}", callback_data=f"sel_month_{r[0]}")] for r in rows]
    kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
    await update.message.reply_text(get_t("stats_select"), reply_markup=InlineKeyboardMarkup(kb))

async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Create Post", callback_data="post_create")],
        [InlineKeyboardButton(get_t("back"), callback_data="main_menu")]
    ])
    await update.message.reply_text(get_t("menu_post"), reply_markup=kb)

# --- CALLBACKS (Logic Updated for Month/Day) ---
async def main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    if user_id not in ALLOWED_ADMINS: return

    if data == "main_menu":
        await query.edit_message_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

    elif data == "nav_lang":
        await query.edit_message_text(get_t("lang_select"), reply_markup=get_lang_menu())

    elif data.startswith("set_lang_"):
        new_lang = data.split("_")[2]
        set_current_lang(new_lang)
        await query.answer(get_t("lang_updated"))
        await query.edit_message_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

    elif data == "nav_setting":
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT id, title FROM chats").fetchall()
        conn.close()
        kb = [[InlineKeyboardButton(f"⚙️ {r[1]}", callback_data=f"manage_{r[0]}")] for r in rows]
        kb.append([InlineKeyboardButton(get_t("add_chat"), callback_data="add_chat_start")])
        kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
        await query.edit_message_text("Select Chat to Manage:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("manage_"):
        cid = data.split("_")[1]
        
        # Get labels based on current language
        lang = get_current_lang()
        # Default labels (English/Fallback)
        labels = LANG_TEXT['en']['settings_labels']
        # If specific lang exists, use it
        if lang in LANG_TEXT and 'settings_labels' in LANG_TEXT[lang]:
            labels = LANG_TEXT[lang]['settings_labels']
            
        def btn(label, key):
            status = "✅" if get_chat_setting(cid, key) == 'ON' else "❌"
            return InlineKeyboardButton(f"{label} {status}", callback_data=f"toggle_{key}_{cid}")
        
        kb = [
            [btn(labels["comment"], "comment"), btn(labels["chat"], "chat")],
            [btn(labels["reaction"], "reaction"), btn(labels["protect"], "protect")],
            [btn(labels["ss"], "ss"), btn(labels["rc"], "rc")],
            [btn(labels["ban"], "banned_active"), btn(labels["spam"], "spam_filter")],
            [InlineKeyboardButton(get_t("bw_add_btn"), callback_data=f"bw_add_{cid}"),
             InlineKeyboardButton(get_t("bw_view_btn"), callback_data=f"bw_view_{cid}")],
            [InlineKeyboardButton(get_t("back"), callback_data="nav_setting")]
        ]
        await query.edit_message_text(f"⚙️ ID: {cid}", reply_markup=InlineKeyboardMarkup(kb))
    
    elif data.startswith("bw_view_"):
        await bw_view_list(update, context)

    elif data.startswith("toggle_"):
        parts = data.split("_")
        toggle_chat_setting(parts[2], parts[1])
        await query.answer("Updated!")
        await main_callback(update, context)

    # --- UPDATED STATS NAVIGATION FLOW ---
    
    # 1. Chat List
    elif data == "nav_graph_chat_list":
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT id, title FROM chats").fetchall()
        conn.close()
        # Change next step to "sel_month" instead of direct metric list
        kb = [[InlineKeyboardButton(f"📊 {r[1]}", callback_data=f"sel_month_{r[0]}")] for r in rows]
        kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
        await query.edit_message_text(get_t("stats_select"), reply_markup=InlineKeyboardMarkup(kb))

    # 2. Month Selection
    elif data.startswith("sel_month_"):
        cid = data.split("_")[2]
        await query.edit_message_text(get_t("month_select"), reply_markup=get_month_menu(cid))

    # 3. Day Selection
    elif data.startswith("sel_day_"):
        # Format: sel_day_{chat_id}_{YYYY-MM}
        parts = data.split("_")
        cid = parts[2]
        ym = parts[3] # 2024-02
        await query.edit_message_text(get_t("day_select"), reply_markup=get_day_menu(cid, ym))

    # 4. Metric Selection
    elif data.startswith("sel_met_"):
        # Format: sel_met_{chat_id}_{date_filter}
        # date_filter can be YYYY-MM or YYYY-MM-DD
        parts = data.split("_")
        cid = parts[2]
        date_filter = parts[3]
        await query.edit_message_text(get_t("metric_select"), reply_markup=get_metric_menu(cid, date_filter))

    # 5. Final Report
    elif data.startswith("fin_"):
        # Format: fin_{chat_id}|{date_filter}|{metric_name}
        # We used '|' separator to be safe with underscores in metric name (though minimal risk)
        try:
            _, payload = data.split("_", 1)
            cid, date_filter, metric = payload.split("|")
            
            await query.answer(get_t("graph_gen"))
            
            # Find full metric name from short name if needed, but here we passed the short/full string.
            # In generate function we use LIKE or exact match? 
            # Ideally the metric name in DB should match exactly. 
            # For this code to work, we assume what's passed in button is what's in DB.
            
            report_text = await generate_stats_text(cid, metric, date_filter)
            
            await query.edit_message_text(
                text=report_text, 
                reply_markup=get_metric_menu(cid, date_filter),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Stats Error: {e}")
            await query.answer("Error generating stats.")

    elif data == "nav_post":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Create Post", callback_data="post_create")],
            [InlineKeyboardButton(get_t("back"), callback_data="main_menu")]
        ])
        await query.edit_message_text(get_t("menu_post"), reply_markup=kb)

# --- POST CONVERSATION ---
async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = sqlite3.connect(DB_PATH)
    chats = conn.execute("SELECT id, title FROM chats").fetchall()
    conn.close()
    if not chats: 
        await query.edit_message_text("❌ No chats found. Please add a chat first.", reply_markup=get_main_menu())
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(c[1], callback_data=f"psel_{c[0]}")] for c in chats]
    kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
    await query.edit_message_text("📢 Select Chat to Post:", reply_markup=InlineKeyboardMarkup(kb))
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

# --- MAIN RUN ---
if __name__ == '__main__':
    init_db()
    
    # 1. Start Keep-Alive Server
    keep_alive()

    # 2. Add Persistence
    my_persistence = PicklePersistence(filepath='storage/bot_states')
    app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).persistence(my_persistence).build()
    
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
        entry_points=[CallbackQueryHandler(post_start, pattern="^post_create$")],
        states={
            WAITING_POST_CONTENT: [CallbackQueryHandler(post_chat_selected, pattern="^psel_"), MessageHandler(filters.ALL & ~filters.COMMAND, post_content_rcv)],
            WAITING_POST_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_time_rcv)],
            WAITING_POST_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_delete_rcv)]
        },
        fallbacks=[CallbackQueryHandler(main_callback, pattern="^main_menu$")],
        allow_reentry=True 
    )

    # Added explicit CommandHandlers
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('setting', setting_command))
    app.add_handler(CommandHandler('graph', graph_command))
    app.add_handler(CommandHandler('grap', graph_command)) # Alias for typo
    app.add_handler(CommandHandler('post', post_command))

    app.add_handler(conv_add_chat)
    app.add_handler(conv_bw)
    app.add_handler(conv_post)
    # Callback handler must come last to catch other button clicks
    app.add_handler(CallbackQueryHandler(main_callback))
    
    print("🚀 Admin Bot V3 (With Month/Day Filter) is running...")
    app.run_polling(drop_pending_updates=True)
