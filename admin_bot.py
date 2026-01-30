import os
import sqlite3
import logging
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# --- CONFIG ---
# Admin Bot Token
ADMIN_BOT_TOKEN = "8324982217:AAEQ85YcMran1X0UEirIISV831FR1jrzXG4"
ALLOWED_ADMINS = [8324982217]  

# Logging setting
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_PATH = "storage/stats.db"

# --- DATABASE SETUP ---
def init_db():
    os.makedirs("storage", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, title TEXT, link TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats (type TEXT PRIMARY KEY, count INTEGER DEFAULT 0)''')
    
    default_settings = [
        ('language', 'my'),
        ('bot_status', 'ON'),
        ('ch_chat', 'ON'), ('gp_chat', 'ON'),           
        ('ch_comment', 'ON'), ('gp_comment', 'ON'),     
        ('ch_reaction', 'ON'), ('gp_reaction', 'ON'),   
        ('ch_protect', 'OFF'), ('gp_protect', 'OFF')
    ]
    for key, val in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
    
    conn.commit()
    conn.close()

def get_setting(key):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        res = c.fetchone()
        conn.close()
        return res[0] if res else "OFF"
    except Exception as e:
        logger.error(f"Error getting setting {key}: {e}")
        return "OFF"

def toggle_db_setting(key):
    current = get_setting(key)
    new_val = "OFF" if current == "ON" else "ON"
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE settings SET value=? WHERE key=?", (new_val, key))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error toggling setting {key}: {e}")
    return new_val

# --- MENU BUILDERS ---
def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Channel Settings", callback_data="menu_ch"),
         InlineKeyboardButton("👥 Group Settings", callback_data="menu_gp")],
        [InlineKeyboardButton("🌍 Language: " + get_setting('language').upper(), callback_data="toggle_lang")],
        [InlineKeyboardButton("🤖 Bot Status: " + get_setting('bot_status'), callback_data="tog_bot_status")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def get_channel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Chat: {get_setting('ch_chat')}", callback_data="tog_ch_chat"),
         InlineKeyboardButton(f"Comment: {get_setting('ch_comment')}", callback_data="tog_ch_comment")],
        [InlineKeyboardButton(f"Reaction: {get_setting('ch_reaction')}", callback_data="tog_ch_reaction"),
         InlineKeyboardButton(f"Protect: {get_setting('ch_protect')}", callback_data="tog_ch_protect")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
    ])

def get_group_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Chat: {get_setting('gp_chat')}", callback_data="tog_gp_chat"),
         InlineKeyboardButton(f"Comment: {get_setting('gp_comment')}", callback_data="tog_gp_comment")],
        [InlineKeyboardButton(f"Reaction: {get_setting('gp_reaction')}", callback_data="tog_gp_reaction"),
         InlineKeyboardButton(f"Protect: {get_setting('gp_protect')}", callback_data="tog_gp_protect")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
    ])

# --- COMMAND HANDLERS ---
async def admin_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    await update.message.reply_text("⚙️ *Admin Control Panel*", 
                                   reply_markup=get_main_keyboard(), parse_mode='Markdown')

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    await update.message.reply_text("📊 *Statistics:* (အချက်အလက်များကို ဤနေရာတွင် ပြသမည်)")

async def admin_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_ADMINS: return
    await update.message.reply_text("📝 *Post Creator:* ပို့စ်အသစ်တင်ရန် ပြင်ဆင်ပါ")

# --- ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error_msg = str(context.error)
    if "Conflict" in error_msg:
        logger.warning("Another instance is running. Attempting to take over...")
    else:
        logger.error(f"Update {update} caused error: {context.error}")

# --- CALLBACK HANDLER ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    
    if data == "menu_ch":
        await query.edit_message_text("📢 *Channel Individual Settings*", reply_markup=get_channel_keyboard(), parse_mode='Markdown')
    elif data == "menu_gp":
        await query.edit_message_text("👥 *Group Individual Settings*", reply_markup=get_group_keyboard(), parse_mode='Markdown')
    elif data == "admin_main":
        await query.edit_message_text("⚙️ *Admin Control Panel*", reply_markup=get_main_keyboard(), parse_mode='Markdown')
    elif data.startswith("tog_"):
        key = data.replace("tog_", "")
        toggle_db_setting(key)
        if key.startswith("ch_"):
            await query.edit_message_reply_markup(reply_markup=get_channel_keyboard())
        elif key.startswith("gp_"):
            await query.edit_message_reply_markup(reply_markup=get_group_keyboard())
        elif key == "bot_status":
            await query.edit_message_reply_markup(reply_markup=get_main_keyboard())
    elif data == "toggle_lang":
        curr = get_setting('language')
        new_lang = "en" if curr == "my" else "my"
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE settings SET value=? WHERE key='language'", (new_lang,))
            conn.commit()
            conn.close()
        except: pass
        await query.edit_message_reply_markup(reply_markup=get_main_keyboard())
    elif data == "close":
        await query.delete_message()

# --- SETUP COMMAND MENU ---
async def setup_commands(application):
    commands = [
        BotCommand("start", "Bot ကိုစတင်ရန်"),
        BotCommand("setting", "Admin Control Panel ဖွင့်ရန်"),
        BotCommand("post", "Channel သို့ ပို့စ်တင်ရန်"),
        BotCommand("stats", "စာရင်းဇယားများကြည့်ရန်"),
        BotCommand("chat", "Chat settings များကြည့်ရန်"),
        BotCommand("data", "Database အချက်အလက်များ")
    ]
    await application.bot.set_my_commands(commands)

if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    
    # Register Commands
    application.add_handler(CommandHandler('start', admin_setting))
    application.add_handler(CommandHandler('setting', admin_setting))
    application.add_handler(CommandHandler('post', admin_post))
    application.add_handler(CommandHandler('stats', admin_stats))
    application.add_handler(CallbackQueryHandler(handle_callbacks))
    application.add_error_handler(error_handler)
    
    # Command Menu ကို Bot ထဲမှာ Register လုပ်ခြင်း
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_commands(application))
    
    print("Admin Bot is active and running with Menu...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
