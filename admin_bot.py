import os
import sqlite3
import logging
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# --- CONFIG ---
ADMIN_BOT_TOKEN = "8324982217:AAEQ85YcMran1X0UEirIISV831FR1jrzXG4"
ALLOWED_ADMINS = [8324982217]  

logging.basicConfig(level=logging.INFO)
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
    
    # ပုံသေ Setting များ (Chat, Comment, Reaction, Protect အားလုံးပါဝင်သည်)
    default_settings = [
        ('language', 'my'),
        ('bot_status', 'ON'),
        ('banned_words', '[]'),
        ('ch_chat', 'ON'), ('gp_chat', 'ON'),           
        ('ch_comment', 'ON'), ('gp_comment', 'ON'),     
        ('ch_reaction', 'ON'), ('gp_reaction', 'ON'),   
        ('ch_protect', 'OFF'), ('gp_protect', 'OFF')    # SS/RC/Copy/FW Protect
    ]
    for key, val in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
    
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else "OFF"

def toggle_db_setting(key):
    current = get_setting(key)
    new_val = "OFF" if current == "ON" else "ON"
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE settings SET value=? WHERE key=?", (new_val, key))
    conn.commit()
    conn.close()
    return new_val

# --- MENU ICON SETUP ---
async def set_commands(application):
    commands = [
        BotCommand("start", "ပင်မစာမျက်နှာ"),
        BotCommand("setting", "Control Panel (ဖွင့်/ပိတ်/ဘာသာစကား)"),
        BotCommand("data", "Real-time Statistics (21 Graphs)"),
        BotCommand("chat", "Manage Groups/Channels (Link +)"),
        BotCommand("post", "Post Scheduler (Auto-delete/Forever)")
    ]
    await application.bot.set_my_commands(commands)

# --- COMMAND HANDLERS ---

async def admin_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setting - Main Menu"""
    if update.effective_user.id not in ALLOWED_ADMINS: return
    
    keyboard = [
        [InlineKeyboardButton("📢 Channel Settings", callback_data="menu_ch"),
         InlineKeyboardButton("👥 Group Settings", callback_data="menu_gp")],
        [InlineKeyboardButton("🌍 Change Language", callback_data="set_lang_menu")],
        [InlineKeyboardButton("🚫 Banned Words (+/-)", callback_data="manage_banned")],
        [InlineKeyboardButton("🤖 Bot Status: " + get_setting('bot_status'), callback_data="toggle_bot_main")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ]
    await update.message.reply_text("⚙️ *Professional Admin Dashboard*\n\nပြုပြင်လိုသည့် ကဏ္ဍကို ရွေးချယ်ပါ။", 
                                   reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/data - 21 Statistics List"""
    if update.effective_user.id not in ALLOWED_ADMINS: return
    metrics = [
        "Daily Joined", "Daily Left", "Total Followers", "Daily Total Members",
        "Daily Mute", "Daily Unmute", "Traffic-Invite", "Traffic-Search",
        "Traffic-PM", "Traffic-Group", "Traffic-Channel", "Daily Views",
        "Daily Shares", "Daily Positive", "Daily Neutral", "Daily Negative",
        "Daily Deletes", "Daily Warns", "Daily Kicks", "Daily Bans", "Active Members"
    ]
    text = "📊 *Live Real-time Data (21 Metrics)*\n" + "—"*15 + "\n"
    for m in metrics: text += f"• {m}: `0`\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def admin_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/chat - Manage Links"""
    if update.effective_user.id not in ALLOWED_ADMINS: return
    keyboard = [[InlineKeyboardButton("➕ Add New Group/Channel Link", callback_data="add_chat")]]
    await update.message.reply_text("💬 *Group & Channel Management*\n\nလက်ရှိချိတ်ဆက်ထားသော စာရင်းများ...", 
                                   reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/post - Schedule Options"""
    if update.effective_user.id not in ALLOWED_ADMINS: return
    keyboard = [
        [InlineKeyboardButton("⏰ Set Time", callback_data="set_time")],
        [InlineKeyboardButton("✅ Keep Forever", callback_data="mode_forever"),
         InlineKeyboardButton("🗑 Auto Delete", callback_data="mode_delete")]
    ]
    await update.message.reply_text("📝 *Post & Movie Scheduler*\n\nတင်မည့်ပုံစံကို ရွေးချယ်ပါ။", 
                                   reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- CALLBACK HANDLER ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    
    if data == "menu_ch":
        kb = [
            [InlineKeyboardButton(f"Chat: {get_setting('ch_chat')}", callback_data="tog_ch_chat"),
             InlineKeyboardButton(f"Comment: {get_setting('ch_comment')}", callback_data="tog_ch_comment")],
            [InlineKeyboardButton(f"Reaction: {get_setting('ch_reaction')}", callback_data="tog_ch_reaction"),
             InlineKeyboardButton(f"Protect (SS/RC/FW): {get_setting('ch_protect')}", callback_data="tog_ch_protect")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ]
        await query.edit_message_text("📢 *Channel Individual Settings*", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data == "menu_gp":
        kb = [
            [InlineKeyboardButton(f"Chat: {get_setting('gp_chat')}", callback_data="tog_gp_chat"),
             InlineKeyboardButton(f"Comment: {get_setting('gp_comment')}", callback_data="tog_gp_comment")],
            [InlineKeyboardButton(f"Reaction: {get_setting('gp_reaction')}", callback_data="tog_gp_reaction"),
             InlineKeyboardButton(f"Protect (SS/RC/FW): {get_setting('gp_protect')}", callback_data="tog_gp_protect")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ]
        await query.edit_message_text("👥 *Group Individual Settings*", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data == "admin_main":
        keyboard = [
            [InlineKeyboardButton("📢 Channel Settings", callback_data="menu_ch"),
             InlineKeyboardButton("👥 Group Settings", callback_data="menu_gp")],
            [InlineKeyboardButton("🌍 Change Language", callback_data="set_lang_menu")],
            [InlineKeyboardButton("🚫 Banned Words (+/-)", callback_data="manage_banned")],
            [InlineKeyboardButton("🤖 Bot Status: " + get_setting('bot_status'), callback_data="toggle_bot_main")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ]
        await query.edit_message_text("⚙️ *Professional Admin Dashboard*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("tog_"):
        key = data.replace("tog_", "")
        toggle_db_setting(key)
        # Refresh current menu
        if "ch_" in key: await handle_callbacks(update, context) # Recursive call to refresh channel menu
        else: await handle_callbacks(update, context)

    elif data == "close": await query.delete_message()

if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
    
    # Register Commands
    application.add_handler(CommandHandler('setting', admin_setting))
    application.add_handler(CommandHandler('data', admin_data))
    application.add_handler(CommandHandler('chat', admin_chat))
    application.add_handler(CommandHandler('post', admin_post))
    application.add_handler(CommandHandler('start', admin_setting))
    
    application.add_handler(CallbackQueryHandler(handle_callbacks))
    
    # Set Menu Icon Commands
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(set_commands(application))
    except: pass

    print("Admin Bot is fully operational...")
    application.run_polling(drop_pending_updates=True)
