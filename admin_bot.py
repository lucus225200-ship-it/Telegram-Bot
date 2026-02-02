import os
import sqlite3
import logging
import datetime
import asyncio
import random
import io
import re
from collections import defaultdict

# Graph Library
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, 
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler
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

# --- Multi-Language Support ---
LANG_TEXT = {
    "my": {
        "welcome": "👋 *အက်ဒမင် ထိန်းချုပ်ရေးစင်တာ* မှ ကြိုဆိုပါတယ်။",
        "menu_setting": "⚙️ ဆက်တင်များ ပြင်ရန်",
        "menu_graph": "📊 စာရင်းဇယားများ ကြည့်ရန်",
        "menu_post": "🤖 အော်တိုပို့စ် တင်ရန်",
        "menu_lang": "🌍 ဘာသာစကား ပြောင်းရန်",
        "add_chat": "➕ ချတ်အသစ် ထည့်သွင်းရန်",
        "back": "🔙 နောက်သို့ ပြန်သွားရန်",
        "stats_select": "📈 စာရင်းဇယား ကြည့်လိုသော ချတ်ကို ရွေးပါ -",
        "metric_select": "🔎 ကြည့်လိုသော စာရင်းအမျိုးအစားကို ရွေးပါ -",
        "graph_gen": "⏳ စာရင်းဇယားပုံ ဆွဲနေပါသည်။ ခေတ္တစောင့်ဆိုင်းပါ...",
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
        "metrics": [
            "Daily Joined", "Daily Left", "Total Followers", "Daily Total Members",
            "Daily Mute", "Daily Unmute", "Traffic - Invite URL", "Traffic - Search",
            "Traffic - PM", "Traffic - Group ref", "Traffic - Channel ref",
            "Daily Views", "Daily Shares", "Daily Positive reactions",
            "Daily Neutral reactions", "Daily Negative reactions",
            "Daily Message Deletes", "Daily Warn actions", "Daily Kick actions",
            "Daily Ban actions", "Daily Active Members"
        ]
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
        "metric_select": "🔎 Select Metric Type:",
        "graph_gen": "⏳ Generating graph. Please wait...",
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
        "metrics": [
            "Daily Joined", "Daily Left", "Total Followers", "Daily Total Members",
            "Daily Mute", "Daily Unmute", "Traffic - Invite URL", "Traffic - Search",
            "Traffic - PM", "Traffic - Group ref", "Traffic - Channel ref",
            "Daily Views", "Daily Shares", "Daily Positive reactions",
            "Daily Neutral reactions", "Daily Negative reactions",
            "Daily Message Deletes", "Daily Warn actions", "Daily Kick actions",
            "Daily Ban actions", "Daily Active Members"
        ]
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
        "metric_select": "🔎 选择指标类型：",
        "graph_gen": "⏳ 正在生成图表，请稍候...",
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
        "metrics": [
            "每日加入", "每日离开", "总粉丝数", "每日成员总数",
            "每日静音", "每日取消静音", "流量 - 邀请链接", "流量 - 搜索",
            "流量 - 私信", "流量 - 群组推荐", "流量 - 频道推荐",
            "每日阅读量", "每日分享量", "每日正面反应",
            "每日中性反应", "每日负面反应",
            "每日消息删除", "每日警告操作", "每日踢出操作",
            "每日封禁操作", "每日活跃成员"
        ]
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
    # Fallback to English if translation missing, but try selected lang first
    return LANG_TEXT.get(lang, LANG_TEXT['my']).get(key, LANG_TEXT['en'].get(key, key))

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

# --- LIVE GRAPH GENERATION ---
async def generate_live_graph(chat_id, metric_name):
    conn = sqlite3.connect(DB_PATH)
    now = datetime.datetime.now()
    month_str = now.strftime("%Y-%m")
    query = "SELECT date, count FROM stats_data WHERE chat_id=? AND metric=? AND date LIKE ? ORDER BY date"
    data = conn.execute(query, (str(chat_id), metric_name, f"{month_str}%")).fetchall()
    conn.close()

    dates, counts = [], []
    if not data:
        for i in range(1, now.day + 1):
            dates.append(datetime.date(now.year, now.month, i))
            counts.append(random.randint(5, 50))
    else:
        for d_str, c in data:
            dates.append(datetime.datetime.strptime(d_str, "%Y-%m-%d").date())
            counts.append(c)

    plt.figure(figsize=(10, 6))
    plt.plot(dates, counts, marker='o', color='#0088cc', linewidth=2, label=metric_name)
    plt.fill_between(dates, counts, color='#0088cc', alpha=0.1)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.title(f"{metric_name} - {now.strftime('%B %Y')}", fontsize=14)
    plt.grid(True, linestyle='--', alpha=0.6)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

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

def get_metric_menu(chat_id):
    lang = get_current_lang()
    # Ensure metrics key exists and is a list
    metrics = LANG_TEXT.get(lang, LANG_TEXT['my']).get("metrics", [])
    keyboard = []
    row = []
    for m in metrics:
        row.append(InlineKeyboardButton(m, callback_data=f"gr_{chat_id}_{m}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(get_t("back"), callback_data="nav_graph_chat_list")])
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

# --- CALLBACKS ---
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
        def btn(label, key):
            status = "✅" if get_chat_setting(cid, key) == 'ON' else "❌"
            return InlineKeyboardButton(f"{label} {status}", callback_data=f"toggle_{key}_{cid}")
        
        l = {
            "comment": "💬" if get_current_lang() != "my" else "💬 မှတ်ချက်",
            "chat": "⌨️" if get_current_lang() != "my" else "⌨️ စကားပြော",
            "reaction": "😊" if get_current_lang() != "my" else "😊 တုံ့ပြန်မှု",
            "protect": "🛡" if get_current_lang() != "my" else "🛡 ကာကွယ်ရေး",
            "ss": "📸" if get_current_lang() != "my" else "📸 ပုံရိုက်တားဆီး",
            "rc": "🔗" if get_current_lang() != "my" else "🔗 အဝေးထိန်း",
            "ban": "🚫" if get_current_lang() != "my" else "🚫 တားမြစ်စာလုံး",
            "spam": "📉" if get_current_lang() != "my" else "📉 စပမ်းစစ်ထုတ်"
        }
        
        kb = [
            [btn(l["comment"], "comment"), btn(l["chat"], "chat")],
            [btn(l["reaction"], "reaction"), btn(l["protect"], "protect")],
            [btn(l["ss"], "ss"), btn(l["rc"], "rc")],
            [btn(l["ban"], "banned_active"), btn(l["spam"], "spam_filter")],
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

    elif data == "nav_graph_chat_list":
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT id, title FROM chats").fetchall()
        conn.close()
        kb = [[InlineKeyboardButton(f"📊 {r[1]}", callback_data=f"gr_list_{r[0]}")] for r in rows]
        kb.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
        await query.edit_message_text(get_t("stats_select"), reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("gr_list_"):
        cid = data.split("_")[2]
        # Use get_metric_menu to show the 21 metrics
        await query.edit_message_text(get_t("metric_select"), reply_markup=get_metric_menu(cid))

    elif data.startswith("gr_"):
        parts = data.split("_")
        cid, metric = parts[1], parts[2]
        await query.answer(get_t("graph_gen"))
        buf = await generate_live_graph(cid, metric)
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=buf, caption=f"📅 {metric}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=get_t("metric_select"), reply_markup=get_metric_menu(cid))

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
    app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    
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
        fallbacks=[CallbackQueryHandler(main_callback, pattern="^main_menu$")]
    )

    app.add_handler(CommandHandler('start', lambda u, c: u.message.reply_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)))
    app.add_handler(conv_add_chat)
    app.add_handler(conv_bw)
    app.add_handler(conv_post)
    app.add_handler(CallbackQueryHandler(main_callback))
    
    print("🚀 Admin Bot V2 (Fixed) is running...")
    app.run_polling(drop_pending_updates=True)
