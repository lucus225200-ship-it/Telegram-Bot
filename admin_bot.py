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
# လူကြီးမင်း၏ Bot Token နှင့် Admin ID ကို ဤနေရာတွင် ထည့်ပါ
ADMIN_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" 
ALLOWED_ADMINS = [8346273059] # Admin ID များထည့်ပါ
DB_PATH = "storage/stats_v2.db"

# --- STATES FOR CONVERSATIONS ---
# For Adding Chat
WAITING_CHAT_LINK = 1

# For Banned Words
WAITING_BANNED_WORD = 2

# For Auto Post
WAITING_POST_CONTENT = 3
WAITING_POST_TIME = 4
WAITING_POST_DELETE = 5

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- LANGUAGE DICTIONARY ---
LANG_TEXT = {
    "my": {
        "welcome": "👋 *Admin Control Panel* မှ ကြိုဆိုပါတယ်။",
        "menu_setting": "⚙️ Settings (စီမံရန်)",
        "menu_graph": "📊 Statistics (စာရင်းဇယား)",
        "menu_post": "🤖 Auto Post (ပို့စ်တင်ရန်)",
        "menu_lang": "🌍 Language (ဘာသာစကား)",
        "ch_setting": "📢 Channel Settings",
        "gp_setting": "👥 Group Settings",
        "add_chat": "➕ Chat အသစ်ထည့်ရန်",
        "back": "🔙 ပြန်သွားရန်",
        "close": "❌ ပိတ်မည်",
        "no_chats": "❌ ချိတ်ဆက်ထားသော Channel/Group မရှိသေးပါ။\n'Chat အသစ်ထည့်ရန်' ကိုနှိပ်ပြီး ထည့်သွင်းပါ။",
        "send_link": "🔗 *Chat Link (သို့) Username ပေးပို့ပါ*\n(ဥပမာ: https://t.me/mychannel သို့မဟုတ် @mychannel)\n\n⚠️ Bot ကို ထို Channel/Group တွင် Admin အရင်ပေးထားပါ။",
        "chat_added": "✅ Chat ကို အောင်မြင်စွာ ထည့်သွင်းပြီးပါပြီ!\nTitle: {}",
        "chat_err": "❌ Chat ကို ရှာမတွေ့ပါ (သို့) Bot သည် Admin မဟုတ်ပါ။",
        "banned_title": "🚫 တားမြစ်စာလုံး ပေါင်းထည့်ရန်",
        "graph_menu_title": "📊 *ကြည့်ရှုလိုသော စာရင်းဇယားကို ရွေးချယ်ပါ*",
        "post_title": "🤖 *Auto Post & Delete စနစ်*",
        "post_send": "📝 တင်လိုသော စာ (Text/Photo) ကို ပေးပို့ပါ:",
        "post_time": "🕒 *ဘယ်အချိန်တင်မလဲ?*\n(Format: 'now' သို့မဟုတ် မိနစ်ပိုင်းခြားရန် '10m', '1h')",
        "post_del": "🗑 *ဘယ်အချိန် ပြန်ဖျက်မလဲ?*\n(Format: 'no' မဖျက်ရန်၊ သို့မဟုတ် '30m', '24h')",
        "post_success": "✅ Post ကို အချိန်ဇယားဆွဲပြီးပါပြီ။",
        "lang_select": "🌍 ဘာသာစကား ရွေးချယ်ပါ:",
        "enter_word": "🚫 တားမြစ်လိုသော စာလုံးကို ပို့ပေးပါ:",
        "spam_kick": "📉 Spam ပို့မှုကြောင့် Kick လိုက်ပါပြီ။",
        "word_kick": "🚫 တားမြစ်စာလုံးကြောင့် Kick လိုက်ပါပြီ။"
    },
    "en": {
        "welcome": "👋 *Welcome to Admin Control Panel*",
        "menu_setting": "⚙️ Settings",
        "menu_graph": "📊 Statistics",
        "menu_post": "🤖 Auto Post",
        "menu_lang": "🌍 Language",
        "ch_setting": "📢 Channel Settings",
        "gp_setting": "👥 Group Settings",
        "add_chat": "➕ Add New Chat",
        "back": "🔙 Back",
        "close": "❌ Close",
        "no_chats": "❌ No connected chats found.\nClick 'Add New Chat' to add one.",
        "send_link": "🔗 *Send Chat Link or Username*\n(e.g., https://t.me/mychannel or @mychannel)\n\n⚠️ Make sure Bot is Admin there first.",
        "chat_added": "✅ Chat added successfully!\nTitle: {}",
        "chat_err": "❌ Chat not found or Bot is not Admin.",
        "banned_title": "🚫 Add Banned Word",
        "graph_menu_title": "📊 *Select Metric to View*",
        "post_title": "🤖 *Auto Post & Delete System*",
        "post_send": "📝 Send content to post (Text/Photo):",
        "post_time": "🕒 *When to post?*\n(Format: 'now' or delay '10m', '1h')",
        "post_del": "🗑 *Delete after?*\n(Format: 'no' or '30m', '24h')",
        "post_success": "✅ Post scheduled successfully.",
        "lang_select": "🌍 Select Language:",
        "enter_word": "🚫 Send the word you want to ban:",
        "spam_kick": "📉 Kicked due to spamming.",
        "word_kick": "🚫 Kicked due to banned word."
    },
    "cn": {
        "welcome": "👋 *欢迎使用管理控制面板*",
        "menu_setting": "⚙️ 设置",
        "menu_graph": "📊 统计数据",
        "menu_post": "🤖 自动发帖",
        "menu_lang": "🌍 语言",
        "ch_setting": "📢 频道设置",
        "gp_setting": "👥 群组设置",
        "add_chat": "➕ 添加新聊天",
        "back": "🔙 返回",
        "close": "❌ 关闭",
        "no_chats": "❌ 暂无连接的聊天。\n请点击“添加新聊天”。",
        "send_link": "🔗 *发送聊天链接或用户名*\n(例如: https://t.me/mychannel 或 @mychannel)\n\n⚠️ 请先确保机器人是管理员。",
        "chat_added": "✅ 聊天添加成功！\n标题: {}",
        "chat_err": "❌ 未找到聊天或机器人不是管理员。",
        "banned_title": "🚫 添加违禁词",
        "graph_menu_title": "📊 *选择要查看的指标*",
        "post_title": "🤖 *自动发布和删除系统*",
        "post_send": "📝 发送要发布的内容 (文本/图片):",
        "post_time": "🕒 *发布时间?*\n(格式: 'now' 或 '10m', '1h')",
        "post_del": "🗑 *多久后删除?*\n(格式: 'no' 或 '30m', '24h')",
        "post_success": "✅ 帖子已安排。",
        "lang_select": "🌍 选择语言:",
        "enter_word": "🚫 发送您要禁止的关键词:",
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
    # chats table now stores type (channel/supergroup)
    c.execute('''CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT, type TEXT, username TEXT)''')
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

def get_t(key, context_or_user_id=None):
    # Retrieve language from DB
    try:
        conn = sqlite3.connect(DB_PATH)
        res = conn.execute("SELECT value FROM settings WHERE key='language'").fetchone()
        conn.close()
        lang = res[0] if res else 'my'
    except:
        lang = 'my'
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

# --- SPAM TRACKER ---
user_messages = defaultdict(list)

async def monitor_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Monitors for Banned Words and Spam"""
    if not update.effective_chat or not update.message: return
    
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    
    # Check if features are ON
    is_banned_active = get_chat_setting(chat_id, 'banned_active') == 'ON'
    is_spam_active = get_chat_setting(chat_id, 'spam_filter') == 'ON'

    if not is_banned_active and not is_spam_active:
        return

    # Skip Admins
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]: return
    except: pass

    # 1. Banned Words
    if is_banned_active:
        conn = sqlite3.connect(DB_PATH)
        words = conn.execute("SELECT word FROM banned_words WHERE chat_id=?", (chat_id,)).fetchall()
        conn.close()
        msg_text = (update.message.text or update.message.caption or "").lower()
        
        for (w,) in words:
            if w.lower() in msg_text:
                try:
                    await update.message.delete()
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await context.bot.send_message(chat_id, f"{get_t('word_kick')} (User: {user_id})")
                except Exception as e:
                    logger.error(f"Failed to ban/delete: {e}")
                return

    # 2. Spam Filter (5 messages in 5 seconds)
    if is_spam_active:
        now = datetime.datetime.now()
        # Clean old timestamps
        user_messages[user_id] = [m for m in user_messages[user_id] if (now - m).total_seconds() < 5]
        user_messages[user_id].append(now)
        
        if len(user_messages[user_id]) > 5:
            try:
                await update.message.delete()
                await context.bot.ban_chat_member(chat_id, user_id)
                await context.bot.send_message(chat_id, f"{get_t('spam_kick')} (User: {user_id})")
                # Reset spam count
                user_messages[user_id] = []
            except Exception as e:
                logger.error(f"Failed to spam ban: {e}")

# --- GRAPH GENERATION (INDIVIDUAL) ---

async def generate_single_graph(metric_name):
    """Generates a clean, separate graph for a single metric"""
    plt.figure(figsize=(10, 5))
    
    # Fake Data Generation
    days = list(range(1, 31))
    y_values = [random.randint(5, 50) + (i * random.randint(-1, 2)) for i in days]
    # Ensure no negative values
    y_values = [max(0, y) for y in y_values]

    plt.plot(days, y_values, marker='o', linestyle='-', linewidth=2, color='#1f77b4', label=metric_name)
    plt.fill_between(days, y_values, color='#1f77b4', alpha=0.1)
    
    plt.title(f"{metric_name} Activity (Last 30 Days)", fontsize=14, fontweight='bold')
    plt.xlabel("Day of Month")
    plt.ylabel("Count")
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend()
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()
    return buf

# --- AUTO POST JOBS ---

async def job_send_post(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data # {'chat_id': ..., 'content': ..., 'type': ..., 'delete_delay': ...}
    
    chat_id = data['chat_id']
    content = data['content']
    msg_type = data['type'] # 'text' or 'photo'
    
    try:
        sent_msg = None
        if msg_type == 'text':
            sent_msg = await context.bot.send_message(chat_id=chat_id, text=content)
        elif msg_type == 'photo':
            sent_msg = await context.bot.send_photo(chat_id=chat_id, photo=content['file_id'], caption=content.get('caption', ''))
            
        # Schedule deletion if needed
        if sent_msg and data.get('delete_delay'):
            context.job_queue.run_once(
                job_delete_post, 
                data['delete_delay'], 
                data={'chat_id': chat_id, 'message_id': sent_msg.message_id}
            )
    except Exception as e:
        logger.error(f"Post Job Failed: {e}")

async def job_delete_post(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = job.data
    try:
        await context.bot.delete_message(chat_id=data['chat_id'], message_id=data['message_id'])
    except Exception as e:
        logger.error(f"Delete Job Failed: {e}")

# --- KEYBOARDS ---

def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_t("menu_setting"), callback_data="nav_setting")],
        [InlineKeyboardButton(get_t("menu_graph"), callback_data="nav_graph")],
        [InlineKeyboardButton(get_t("menu_post"), callback_data="nav_post")],
        [InlineKeyboardButton(get_t("menu_lang"), callback_data="nav_lang")]
    ])

def get_graph_menu():
    # 21 Metrics separated
    metrics = [
        "Users", "Views", "Joins", "Leaves", 
        "Chats", "Reactions", "Shares", "Links",
        "Photos", "Videos", "Files", "Voice", 
        "Polls", "Comments", "Bans", "Kicks",
        "Reports", "Spams", "Deleted", "Edits", "Stickers"
    ]
    # Create rows of 3
    keyboard = []
    row = []
    for m in metrics:
        row.append(InlineKeyboardButton(m, callback_data=f"show_graph_{m}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(get_t("back"), callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_setting_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_t("ch_setting"), callback_data="list_chats_channel"),
         InlineKeyboardButton(get_t("gp_setting"), callback_data="list_chats_group")],
        [InlineKeyboardButton(get_t("add_chat"), callback_data="add_chat_start")],
        [InlineKeyboardButton(get_t("back"), callback_data="main_menu")]
    ])

def get_chat_control_panel(chat_id):
    keys = ['comment', 'chat', 'reaction', 'protect', 'ss', 'rc', 'banned_active', 'spam_filter']
    vals = {k: get_chat_setting(chat_id, k) for k in keys}
    
    def btn(label, key):
        status = "✅" if vals[key] == 'ON' else "❌"
        return InlineKeyboardButton(f"{label} {status}", callback_data=f"toggle_{key}_{chat_id}")

    kb = [
        [btn("💬 Comment", "comment"), btn("⌨️ Chat", "chat")],
        [btn("😊 Reaction", "reaction"), btn("🛡 Protect", "protect")],
        [btn("📸 Block SS", "ss"), btn("🔗 Remote", "rc")],
        [btn("🚫 Banned Words", "banned_active"), btn("📉 Spam Filter", "spam_filter")],
        [InlineKeyboardButton(get_t("banned_title"), callback_data=f"add_ban_word_{chat_id}")],
        [InlineKeyboardButton(get_t("back"), callback_data="nav_setting")]
    ]
    return InlineKeyboardMarkup(kb)

# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ALLOWED_ADMINS: return
    
    # Update Bot Menu Commands
    commands = [
        BotCommand("start", "Open Control Panel"),
        BotCommand("graph", "View Statistics"),
        BotCommand("setting", "Settings"),
        BotCommand("post", "Auto Post")
    ]
    await context.bot.set_my_commands(commands)
    
    await update.message.reply_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

async def menu_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /setting, /graph, /post, /language"""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_ADMINS: return
    
    cmd = update.message.text.replace("/", "")
    
    if cmd == "setting":
        await update.message.reply_text(get_t("menu_setting"), reply_markup=get_setting_menu())
    elif cmd == "graph":
        await update.message.reply_text(get_t("graph_menu_title"), reply_markup=get_graph_menu(), parse_mode=ParseMode.MARKDOWN)
    elif cmd == "post":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Create New Post", callback_data="post_create")],
            [InlineKeyboardButton(get_t("back"), callback_data="main_menu")]
        ])
        await update.message.reply_text(get_t("post_title"), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    elif cmd == "language":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="lang_set_my")],
            [InlineKeyboardButton("🇺🇸 English", callback_data="lang_set_en")],
            [InlineKeyboardButton("🇨🇳 中文", callback_data="lang_set_cn")],
            [InlineKeyboardButton(get_t("back"), callback_data="main_menu")]
        ])
        await update.message.reply_text(get_t("lang_select"), reply_markup=kb)

# --- CONVERSATION: ADD CHAT ---

async def add_chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(get_t("send_link"), parse_mode=ParseMode.MARKDOWN)
    return WAITING_CHAT_LINK

async def add_chat_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # Extract username using regex
    match = re.search(r"(?:t\.me\/|@)(\w+)", text)
    
    if not match:
        await update.message.reply_text("❌ Invalid Link format.")
        return WAITING_CHAT_LINK
        
    username = f"@{match.group(1)}"
    
    try:
        chat = await context.bot.get_chat(username)
        # Verify Bot is admin (optional, but good practice)
        # Save to DB
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO chats (id, title, type, username) VALUES (?, ?, ?, ?)", 
                     (str(chat.id), chat.title, chat.type, username))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(get_t("chat_added").format(chat.title), reply_markup=get_setting_menu())
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error adding chat: {e}")
        await update.message.reply_text(get_t("chat_err"), reply_markup=get_setting_menu())
        return ConversationHandler.END

# --- CONVERSATION: AUTO POST ---

async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Check if chats exist first
    conn = sqlite3.connect(DB_PATH)
    chats = conn.execute("SELECT id, title FROM chats").fetchall()
    conn.close()
    
    if not chats:
        await query.edit_message_text(get_t("no_chats"))
        return ConversationHandler.END
        
    # Ask for chat selection
    kb = []
    for c in chats:
        kb.append([InlineKeyboardButton(c[1], callback_data=f"post_sel_chat_{c[0]}")])
    kb.append([InlineKeyboardButton(get_t("close"), callback_data="main_menu")])
    
    await query.edit_message_text("📢 Select Chat to Post:", reply_markup=InlineKeyboardMarkup(kb))
    return WAITING_POST_CONTENT # Actually we intercept callback first

async def post_chat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.data.split("_")[3]
    context.user_data['post_chat_id'] = chat_id
    
    await query.edit_message_text(get_t("post_send"))
    return WAITING_POST_CONTENT

async def post_content_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Store content
    if update.message.photo:
        context.user_data['post_type'] = 'photo'
        context.user_data['post_content'] = {
            'file_id': update.message.photo[-1].file_id,
            'caption': update.message.caption
        }
    else:
        context.user_data['post_type'] = 'text'
        context.user_data['post_content'] = update.message.text
        
    await update.message.reply_text(get_t("post_time"), parse_mode=ParseMode.MARKDOWN)
    return WAITING_POST_TIME

def parse_time_delay(text):
    if text.lower() == 'now': return 1 # 1 second delay
    val = int(re.search(r'\d+', text).group())
    if 'm' in text: return val * 60
    if 'h' in text: return val * 3600
    return 0

async def post_time_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    try:
        delay = parse_time_delay(text)
        context.user_data['post_delay'] = delay
        await update.message.reply_text(get_t("post_del"), parse_mode=ParseMode.MARKDOWN)
        return WAITING_POST_DELETE
    except:
        await update.message.reply_text("❌ Invalid format. Try 'now', '10m', '1h'.")
        return WAITING_POST_TIME

async def post_delete_rcv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    delete_delay = None
    if text.lower() != 'no':
        try:
            delete_delay = parse_time_delay(text)
        except:
            await update.message.reply_text("❌ Invalid. Try 'no', '1h', '24h'.")
            return WAITING_POST_DELETE
            
    # Schedule Job
    chat_id = context.user_data['post_chat_id']
    content = context.user_data['post_content']
    p_type = context.user_data['post_type']
    start_delay = context.user_data['post_delay']
    
    context.job_queue.run_once(
        job_send_post, 
        start_delay, 
        data={'chat_id': chat_id, 'content': content, 'type': p_type, 'delete_delay': delete_delay}
    )
    
    await update.message.reply_text(get_t("post_success"), reply_markup=get_main_menu())
    return ConversationHandler.END

# --- CONVERSATION: BANNED WORDS ---

async def bw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.data.split("_")[3]
    context.user_data['bw_chat_id'] = chat_id
    
    await query.edit_message_text(get_t("enter_word"))
    return WAITING_BANNED_WORD

async def bw_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word = update.message.text
    chat_id = context.user_data.get('bw_chat_id')
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO banned_words (chat_id, word) VALUES (?, ?)", (chat_id, word))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Banned: {word}", reply_markup=get_chat_control_panel(chat_id))
    return ConversationHandler.END

# --- MAIN CALLBACK ROUTER ---

async def main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "main_menu":
        await query.edit_message_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)
        
    elif data == "nav_setting":
        await query.edit_message_text(get_t("menu_setting"), reply_markup=get_setting_menu())
        
    elif data == "nav_graph":
        await query.edit_message_text(get_t("graph_menu_title"), reply_markup=get_graph_menu(), parse_mode=ParseMode.MARKDOWN)
        
    elif data == "nav_post":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Create New Post", callback_data="post_create")],
            [InlineKeyboardButton(get_t("back"), callback_data="main_menu")]
        ])
        await query.edit_message_text(get_t("post_title"), reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        
    elif data == "nav_lang":
         kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data="lang_set_my")],
            [InlineKeyboardButton("🇺🇸 English", callback_data="lang_set_en")],
            [InlineKeyboardButton("🇨🇳 中文", callback_data="lang_set_cn")],
            [InlineKeyboardButton(get_t("back"), callback_data="main_menu")]
        ])
         await query.edit_message_text(get_t("lang_select"), reply_markup=kb)

    # --- Language Setting ---
    elif data.startswith("lang_set_"):
        l = data.split("_")[2]
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE settings SET value=? WHERE key='language'", (l,))
        conn.commit()
        conn.close()
        await query.answer(f"Language set to {l}")
        await query.edit_message_text(get_t("welcome"), reply_markup=get_main_menu(), parse_mode=ParseMode.MARKDOWN)

    # --- Chat Listings ---
    elif data == "list_chats_channel" or data == "list_chats_group":
        conn = sqlite3.connect(DB_PATH)
        # Filter mostly by what we added. Telegram types: 'channel', 'supergroup', 'group'
        rows = conn.execute("SELECT id, title FROM chats").fetchall()
        conn.close()
        
        if not rows:
            await query.answer("No chats found", show_alert=True)
            await query.edit_message_text(get_t("no_chats"), reply_markup=get_setting_menu())
            return
            
        kb = [[InlineKeyboardButton(f"📍 {r[1]}", callback_data=f"manage_{r[0]}")] for r in rows]
        kb.append([InlineKeyboardButton(get_t("back"), callback_data="nav_setting")])
        await query.edit_message_text("Select Chat:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("manage_"):
        cid = data.split("_")[1]
        await query.edit_message_text(f"⚙️ Managing: {cid}", reply_markup=get_chat_control_panel(cid))

    elif data.startswith("toggle_"):
        parts = data.split("_")
        key = parts[1]
        cid = parts[2]
        toggle_chat_setting(cid, key)
        await query.edit_message_reply_markup(reply_markup=get_chat_control_panel(cid))

    # --- Graph Gen ---
    elif data.startswith("show_graph_"):
        metric = data.split("_")[2]
        await query.answer("Generating Graph...")
        
        # Edit text to show loading
        await query.edit_message_text(f"📊 Generating graph for: *{metric}*...", parse_mode=ParseMode.MARKDOWN)
        
        # Gen Image
        buf = await generate_single_graph(metric)
        
        # Send Photo
        await context.bot.send_photo(
            chat_id=update.effective_chat.id, 
            photo=buf, 
            caption=f"📈 *{metric} Analysis*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Show Menu again
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=get_t("graph_menu_title"), 
            reply_markup=get_graph_menu(),
            parse_mode=ParseMode.MARKDOWN
        )


if __name__ == '__main__':
    init_db()
    app = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    
    # 1. Add Chat Conversation
    conv_add_chat = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_chat_start, pattern="^add_chat_start$")],
        states={WAITING_CHAT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_chat_save)]},
        fallbacks=[CallbackQueryHandler(main_callback, pattern="^main_menu$")]
    )
    
    # 2. Add Banned Word Conversation
    conv_bw = ConversationHandler(
        entry_points=[CallbackQueryHandler(bw_start, pattern="^add_ban_word_")],
        states={WAITING_BANNED_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, bw_save)]},
        fallbacks=[CallbackQueryHandler(main_callback, pattern="^main_menu$")]
    )
    
    # 3. Auto Post Conversation
    conv_post = ConversationHandler(
        entry_points=[CallbackQueryHandler(post_start, pattern="^post_create$")],
        states={
            WAITING_POST_CONTENT: [
                CallbackQueryHandler(post_chat_selected, pattern="^post_sel_chat_"),
                MessageHandler(filters.ALL & ~filters.COMMAND, post_content_rcv)
            ],
            WAITING_POST_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_time_rcv)],
            WAITING_POST_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_delete_rcv)]
        },
        fallbacks=[CallbackQueryHandler(main_callback, pattern="^main_menu$")]
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('setting', menu_command_handler))
    app.add_handler(CommandHandler('graph', menu_command_handler))
    app.add_handler(CommandHandler('post', menu_command_handler))
    app.add_handler(CommandHandler('language', menu_command_handler))
    
    app.add_handler(conv_add_chat)
    app.add_handler(conv_bw)
    app.add_handler(conv_post)
    
    app.add_handler(CallbackQueryHandler(main_callback))
    
    # Monitor Handler (Must be last to not block convos)
    app.add_handler(MessageHandler(filters.ALL, monitor_messages))

    print("🚀 Admin Bot V2 is running...")
    app.run_polling(drop_pending_updates=True)
