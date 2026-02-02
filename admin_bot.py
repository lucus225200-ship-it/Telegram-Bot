import os
import sqlite3
import datetime
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode

# Database Path
DB_FILE = "master_bot.db"

# --- ADMIN PANEL LOGIC ---

async def get_admin_main_menu(get_text_func):
    """Admin ရဲ့ Main Menu Keyboard ကို ထုတ်ပေးခြင်း"""
    keyboard = [
        [InlineKeyboardButton(get_text_func('ch_btn'), callback_data="list_channels"),
         InlineKeyboardButton(get_text_func('gp_btn'), callback_data="list_groups")],
        [InlineKeyboardButton(get_text_func('post_btn'), callback_data="auto_post_start"),
         InlineKeyboardButton(get_text_func('stats_btn'), callback_data="view_stats")],
        [InlineKeyboardButton(get_text_func('close'), callback_data="close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_chat_list(chat_type):
    """Channel သို့မဟုတ် Group စာရင်းကို DB မှ ဆွဲထုတ်ခြင်း"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM chats WHERE type=?", (chat_type,))
        return cursor.fetchall()

async def generate_admin_stats():
    """Admin ကြည့်ရန် စာရင်းဇယား Graph ထုတ်ပေးခြင်း"""
    metrics = ["Daily Joined", "Daily Active Members", "Daily Message Deletes"]
    dates = [(datetime.date.today() - datetime.timedelta(days=i)) for i in range(7)]
    dates.reverse()
    date_str = [d.strftime("%m-%d") for d in dates]
    
    fig, axes = plt.subplots(len(metrics), 1, figsize=(10, 15))
    
    with sqlite3.connect(DB_FILE) as conn:
        for i, metric in enumerate(metrics):
            y_values = []
            for d in dates:
                res = conn.execute("SELECT SUM(count) FROM stats WHERE date=? AND metric=?", (d, metric)).fetchone()
                y_values.append(res[0] if res and res[0] else 0)
            
            axes[i].plot(date_str, y_values, marker='o', color='tab:blue', linewidth=2)
            axes[i].set_title(f"Metric: {metric}", fontsize=12, fontweight='bold')
            axes[i].grid(True, linestyle='--', alpha=0.7)
            
    plt.tight_layout()
    graph_path = "admin_stats_graph.png"
    plt.savefig(graph_path)
    plt.close()
    return graph_path

def save_scheduled_post(chat_id, content_type, content_data, caption, post_time, delete_time):
    """Auto Post ကို DB ထဲ သိမ်းဆည်းခြင်း"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO scheduled_posts (chat_id, content_type, content_data, caption, post_time, delete_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (chat_id, content_type, content_data, caption, post_time, delete_time))
        conn.commit()

def update_chat_setting(chat_id, setting_key, value):
    """Channel/Group တစ်ခုချင်းစီ၏ Setting ကို Update လုပ်ခြင်း"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO chat_settings (chat_id, key, value)
            VALUES (?, ?, ?)
        """, (chat_id, setting_key, value))
        conn.commit()

def get_all_channels():
    """Bot ရှိနေသော Channel အားလုံးကို ယူခြင်း (Auto Post အတွက်)"""
    with sqlite3.connect(DB_FILE) as conn:
        return [row[0] for row in conn.execute("SELECT id FROM chats WHERE type='channel'").fetchall()]

# --- END OF ADMIN LOGIC ---
