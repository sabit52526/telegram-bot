import os
import sqlite3
import logging
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler
)

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [123456789]  # আপনার Telegram User ID এখানে দিন (ইচ্ছা হলে)

# Flask Server for Render Keep-Alive
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=10000)

# Database Setup
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        balance REAL DEFAULT 0.0,
                        is_suspicious INTEGER DEFAULT 0,
                        is_blocked INTEGER DEFAULT 0
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        reward REAL,
                        link TEXT
                    )''')
    conn.commit()
    conn.close()

# States for Conversation
BONUS_ID, BONUS_AMOUNT = range(2)
TASK_TITLE, TASK_REWARD, TASK_LINK = range(2, 5)

# --- Admin Keyboards ---
def get_admin_keyboard():
    keyboard = [
        [KeyboardButton("➕ Add Task"), KeyboardButton("📊 View Users")],
        [KeyboardButton("🎁 Give Bonus"), KeyboardButton("⚠️ Suspicious Users")],
        [KeyboardButton("🚫 Block User"), KeyboardButton("✅ Unblock User")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                   (user.id, user.username, user.first_name))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\nWelcome to ClickEarn Pro.",
        reply_markup=get_admin_keyboard()
    )

# --- View Users Function ---
async def view_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, username, balance FROM users")
    users = cursor.fetchall()
    conn.close()

    if not users:
        await update.message.reply_text("❌ No registered users found.")
        return

    msg = f"📊 **Registered Users ({len(users)}):**\n\n"
    for u_id, fname, uname, bal in users:
        username_str = f"@{uname}" if uname else "No Username"
        msg += f"👤 **Name:** {fname}\n🆔 **ID:** `{u_id}`\n🔗 **User:** {username_str}\n💰 **Balance:** ${bal:.2f}\n--------------------\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# --- View Suspicious Users Function ---
async def suspicious_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, username FROM users WHERE is_suspicious = 1")
    users = cursor.fetchall()
    conn.close()

    if not users:
        await update.message.reply_text("✅ No suspicious users detected at the moment.")
        return

    msg = "⚠️ **Suspicious Users List:**\n\n"
    for u_id, fname, uname in users:
        username_str = f"@{uname}" if uname else "N/A"
        msg += f"👤 **Name:** {fname}\n🆔 **ID:** `{u_id}`\n🔗 {username_str}\n--------------------\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# --- Add Task Handlers ---
async def add_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Enter the **Task Title** (e.g., Join Telegram Channel):")
    return TASK_TITLE

async def add_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['task_title'] = update.message.text
    await update.message.reply_text("💰 Enter the **Reward Amount** in USD (e.g., 0.05):")
    return TASK_REWARD

async def add_task_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reward = float(update.message.text)
        context.user_data['task_reward'] = reward
        await update.message.reply_text("🔗 Enter the **Task Link / URL**:")
        return TASK_LINK
    except ValueError:
        await update.message.reply_text("❌ Invalid amount! Please enter a number (e.g., 0.05):")
        return TASK_REWARD

async def add_task_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    title = context.user_data['task_title']
    reward = context.user_data['task_reward']

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (title, reward, link) VALUES (?, ?, ?)", (title, reward, link))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ **Task Added Successfully!**\n\n📌 **Title:** {title}\n💰 **Reward:** ${reward}\n🔗 **Link:** {link}",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    return ConversationHandler.END

# --- Give Bonus Handlers ---
async def give_bonus_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👤 Enter the **User ID** to receive the bonus:")
    return BONUS_ID

async def bonus_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text)
        context.user_data['bonus_user_id'] = user_id
        await update.message.reply_text("💰 Enter the **Bonus Amount** ($):")
        return BONUS_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Invalid User ID! Please enter a valid numerical ID.")
        return BONUS_ID

async def bonus_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        user_id = context.user_data['bonus_user_id']

        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"🎉 Successfully added **${amount:.2f}** bonus to User `{user_id}`!", parse_mode="Markdown", reply_markup=get_admin_keyboard())
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Enter a valid number.")
        return BONUS_AMOUNT

async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Action cancelled.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# --- Main Application ---
def main():
    init_db()
    
    # Start Flask background thread
    Thread(target=run_flask, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()

    # Bonus Conversation Handler
    bonus_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎁 Give Bonus$"), give_bonus_start)],
        states={
            BONUS_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, bonus_id_received)],
            BONUS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bonus_amount_received)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), cancel_action)]
    )

    # Add Task Conversation Handler
    task_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Add Task$"), add_task_start)],
        states={
            TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_title)],
            TASK_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_reward)],
            TASK_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_link)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), cancel_action)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(bonus_handler)
    app.add_handler(task_handler)
    app.add_handler(MessageHandler(filters.Regex("^📊 View Users$"), view_users))
    app.add_handler(MessageHandler(filters.Regex("^⚠️ Suspicious Users$"), suspicious_users))

    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
