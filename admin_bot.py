import os
import sqlite3
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# --- CONFIG ---
# သင်ပေးပို့ထားသော Admin Token အသစ် (သေချာစွာ စစ်ဆေးပါ)
ADMIN_BOT_TOKEN = "8324982217:AAGnEnHz-n6XV6ef0MBE-rMyWqVbbblQBEk"

# Admin အဖြစ်အသုံးပြုခွင့်ရှိသူများ၏ Telegram ID
# (သင့် ID 8324982217 ကိုလည်း ထည့်သွင်းထားပါသည်)
ALLOWED_ADMINS = [8324982217, 12345678]  

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_PATH = "storage/stats.db"

def init_db():
    """Database နှင့် Table များကို အလိုအလျောက် တည်ဆောက်ပေးခြင်း"""
    os.makedirs("storage", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # ၁။ Entities Table
    c.execute('''CREATE TABLE IF NOT EXISTS entities (
                    chat_id TEXT PRIMARY KEY,
                    title TEXT,
                    member_count INTEGER,
                    type TEXT,
                    status TEXT DEFAULT 'active')''')
    
    # ၂။ Stats Table
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    type TEXT,
                    count INTEGER DEFAULT 0)''')
    
    # ၃။ Admin Settings Table
    c.execute('''CREATE TABLE IF NOT EXISTS admin_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT)''')
    
    conn.commit()
    conn.close()

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin Dashboard ပင်မစာမျက်နှာ"""
    user_id = update.effective_user.id
    if user_id not in ALLOWED_ADMINS:
        logger.warning(f"Unauthorized access attempt by ID: {user_id}")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Live Statistics (21 Graphs)", callback_data='show_stats')],
        [InlineKeyboardButton("🔗 Import Channel/Group", callback_data='import_chat')],
        [InlineKeyboardButton("⚙️ Toggle Settings", callback_data='toggle_settings')]
    ]
    
    await update.message.reply_text(
        "👑 *Professional Admin Dashboard*\n\n"
        "စနစ်တစ်ခုလုံးကို စီမံခန့်ခွဲရန် ခလုတ်များကို အသုံးပြုပါ။",
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """စာရင်းဇယား (၂၁) မျိုးကို ပြသပေးခြင်း"""
    query = update.callback_query
    await query.answer()
    
    # တောင်းဆိုထားသော စာရင်းဇယား ၂၁ မျိုး
    metrics = [
        "Daily Joined", "Daily Left", "Total Followers", "Daily Total Members",
        "Daily Mute", "Daily Unmute", "Traffic-Invite", "Traffic-Search",
        "Traffic-PM", "Traffic-Group", "Traffic-Channel", "Daily Views",
        "Daily Shares", "Daily Positive", "Daily Neutral", "Daily Negative",
        "Daily Deletes", "Daily Warns", "Daily Kicks", "Daily Bans", "Active Members"
    ]
    
    stats_text = "📈 *LIVE TELEGRAM REAL-TIME DATA*\n" + "—" * 15 + "\n"
    
    # DB ထဲမှ Data များ ဖတ်ရန် (လက်ရှိတွင် 0 အဖြစ် ပြထားသည်)
    for m in metrics:
        stats_text += f"• {m}: `0` \n"
        
    back_keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data='admin_main')]]
    
    await query.edit_message_text(
        stats_text, 
        parse_mode='Markdown', 
        reply_markup=InlineKeyboardMarkup(back_keyboard)
    )

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Back ခလုတ်နှိပ်လျှင် ပင်မ Menu သို့ ပြန်သွားခြင်း"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📊 Live Statistics (21 Graphs)", callback_data='show_stats')],
        [InlineKeyboardButton("🔗 Import Channel/Group", callback_data='import_chat')],
        [InlineKeyboardButton("⚙️ Toggle Settings", callback_data='toggle_settings')]
    ]
    
    await query.edit_message_text(
        "👑 *Professional Admin Dashboard*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

if __name__ == '__main__':
    # ၁။ Database စတင်တည်ဆောက်မည်
    init_db()
    
    # ၂။ Bot ကို Run မည်
    try:
        application = ApplicationBuilder().token(ADMIN_BOT_TOKEN).build()
        
        # Handlers များ ထည့်သွင်းမည်
        application.add_handler(CommandHandler('start', admin_start))
        application.add_handler(CallbackQueryHandler(stats_handler, pattern='show_stats'))
        application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='admin_main'))
        
        print("Admin Bot is running with the specified token...")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
