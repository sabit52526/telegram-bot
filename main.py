import os
import sqlite3
import logging
from flask import Flask
from threading import Thread
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

# ---------------------------------------------------------
# 1. CONFIGURATION & CONSTANTS
# ---------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
ADMIN_ID = 8808647263  # Fixed Hardcoded Admin ID
OFFICIAL_CHANNEL = "@YourChannelUsername"  # ⚠️ এখানে আপনার চ্যানেলের Username দিন (যেমন: @clickearn_updates)

# Multi-language text templates
MESSAGES = {
    'en': {
        'welcome': "👋 Welcome to ClickEarn Pro!\nComplete simple tasks and earn money daily.",
        'must_join': "⚠️ You MUST join our Official Channel to use this bot!\n\n👉 Join Here: {channel}\n\nAfter joining, send /start again.",
        'balance': "💰 Your Current Balance: ${balance:.4f}",
        'referral': "👥 Your Referral Link:\nhttps://t.me/{bot_username}?start={user_id}\n\nEarn bonus for each active referral!",
        'profile': "👤 Profile Info:\nID: {user_id}\nLanguage: {lang}\nBalance: ${balance:.4f}",
        'support': "📞 For support and assistance, please contact our official team: @YourSupportUsername",
        'cancelled': "❌ Action cancelled. Returning to main menu.",
        'enter_bonus_id': "🎁 Enter the User ID to give bonus:",
        'enter_bonus_amount': "💵 Enter the bonus amount ($):",
        'bonus_success': "✅ Successfully sent ${amount} bonus to User ID {target_id}!",
        'select_lang': "🌐 Select your preferred language:"
    },
    'bn': {
        'welcome': "👋 ClickEarn Pro-এ আপনাকে স্বাগতম!\nসহজ কাজ সম্পন্ন করে প্রতিদিন ইনকাম করুন।",
        'must_join': "⚠️ বটটি ব্যবহার করতে অবশ্যই আমাদের অফিশিয়াল চ্যানেলে জয়েন থাকতে হবে!\n\n👉 চ্যানেল লিংক: {channel}\n\nজয়েন করার পর আবার /start চাপুন।",
        'balance': "💰 আপনার বর্তমান ব্যালেন্স: ${balance:.4f}",
        'referral': "👥 আপনার রেফারেল লিঙ্ক:\nhttps://t.me/{bot_username}?start={user_id}\n\nপ্রতিটি অ্যাক্টিভ রেফারেলে বোনাস পান!",
        'profile': "👤 প্রোফাইল তথ্য:\nআইডি: {user_id}\nভাষা: {lang}\nব্যালেন্স: ${balance:.4f}",
        'support': "📞 যেকোনো সমস্যায় সাহায্য ও সাপোর্টের জন্য আমাদের অফিশিয়াল টিমে যোগাযোগ করুন: @YourSupportUsername",
        'cancelled': "❌ কাজ বাতিল করা হয়েছে। মূল মেনুতে ফিরে যাওয়া হচ্ছে।",
        'enter_bonus_id': "🎁 যাকে বোনাস দিতে চান তার User ID লিখুন:",
        'enter_bonus_amount': "💵 বোনাসের পরিমাণ লিখুন ($):",
        'bonus_success': "✅ সফলভাবে User ID {target_id}-কে ${amount} বোনাস দেওয়া হয়েছে!",
        'select_lang': "🌐 আপনার পছন্দের ভাষা নির্বাচন করুন:"
    }
}

# ---------------------------------------------------------
# 2. FLASK DUMMY SERVER (FOR 24/7 UPTIME ON RENDER)
# ---------------------------------------------------------
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "ClickEarn Pro Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

# ---------------------------------------------------------
# 3. DATABASE SETUP (SQLITE)
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect("clickearn.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            language TEXT DEFAULT 'en',
            is_blocked INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("clickearn.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, balance, language, is_blocked FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, balance, language) VALUES (?, 0.0, 'en')", (user_id,))
        conn.commit()
        user = (user_id, 0.0, 'en', 0)
    conn.close()
    return user

def update_user_lang(user_id, lang):
    conn = sqlite3.connect("clickearn.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def add_user_balance(user_id, amount):
    conn = sqlite3.connect("clickearn.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# Helper function to check channel membership
async def is_user_subscribed(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    if OFFICIAL_CHANNEL == "@YourChannelUsername":
        return True  # Skip check if channel username isn't configured yet
    try:
        member = await context.bot.get_chat_member(chat_id=OFFICIAL_CHANNEL, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        logging.error(f"Channel Check Error: {e}")
        return True

# ---------------------------------------------------------
# 4. KEYBOARD MENUS SETUP
# ---------------------------------------------------------
def get_user_keyboard():
    keyboard = [
        ["💰 Balance", "📋 Tasks"],
        ["📤 Withdraw", "👤 Profile"],
        ["👥 My Referrals", "🌐 Language"],
        ["📞 Support"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        ["➕ Add Task", "📊 View Users"],
        ["🎁 Give Bonus", "⚠️ Suspicious Users"],
        ["🚫 Block User", "🟢 Unblock User"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)

def get_withdraw_keyboard():
    keyboard = [
        ["bKash ($1.00)", "Binance ($0.20)"],
        ["USDT (BEP-20)"],
        ["❌ Cancel"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_language_keyboard():
    keyboard = [
        ["English 🇬🇧", "বাংলা 🇧🇩"],
        ["❌ Cancel"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ---------------------------------------------------------
# 5. BOT HANDLERS & LOGIC
# ---------------------------------------------------------
BONUS_ID, BONUS_AMOUNT = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = user[2] if user[2] in MESSAGES else 'en'
    
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "⚙️ **Welcome to ClickEarn Pro Admin Panel**",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )
        return

    # Check Channel Subscription
    subscribed = await is_user_subscribed(context, user_id)
    if not subscribed:
        msg = MESSAGES[lang]['must_join'].format(channel=OFFICIAL_CHANNEL)
        await update.message.reply_text(msg)
        return

    text = MESSAGES[lang]['welcome']
    await update.message.reply_text(
        text,
        reply_markup=get_user_keyboard()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = user[2] if user[2] in MESSAGES else 'en'
    
    # Non-admin channel check
    if user_id != ADMIN_ID:
        subscribed = await is_user_subscribed(context, user_id)
        if not subscribed:
            msg = MESSAGES[lang]['must_join'].format(channel=OFFICIAL_CHANNEL)
            await update.message.reply_text(msg)
            return

    # ❌ Cancel Pressed at Main Level
    if text == "❌ Cancel":
        if user_id == ADMIN_ID:
            await update.message.reply_text("Main Admin Menu:", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("Main Menu:", reply_markup=get_user_keyboard())
        return

    # User Navigation
    if text == "💰 Balance":
        balance_msg = MESSAGES[lang]['balance'].format(balance=user[1])
        await update.message.reply_text(balance_msg, reply_markup=get_user_keyboard())
        
    elif text == "📋 Tasks":
        await update.message.reply_text("📋 Available Tasks:\n\n1. Join Telegram Channel - $0.05\n2. Visit Website - $0.02", reply_markup=get_cancel_keyboard())
        
    elif text == "📤 Withdraw":
        await update.message.reply_text("💳 Select payment method:", reply_markup=get_withdraw_keyboard())
        
    elif text == "👤 Profile":
        profile_msg = MESSAGES[lang]['profile'].format(user_id=user_id, lang=lang.upper(), balance=user[1])
        await update.message.reply_text(profile_msg, reply_markup=get_user_keyboard())
        
    elif text == "👥 My Referrals":
        bot_username = (await context.bot.get_me()).username
        ref_msg = MESSAGES[lang]['referral'].format(bot_username=bot_username, user_id=user_id)
        await update.message.reply_text(ref_msg, reply_markup=get_user_keyboard())
        
    elif text == "🌐 Language":
        lang_msg = MESSAGES[lang]['select_lang']
        await update.message.reply_text(lang_msg, reply_markup=get_language_keyboard())

    elif text == "📞 Support":
        support_msg = MESSAGES[lang]['support']
        await update.message.reply_text(support_msg, reply_markup=get_user_keyboard())
        
    elif text == "English 🇬🇧":
        update_user_lang(user_id, 'en')
        await update.message.reply_text("Language changed to English!", reply_markup=get_user_keyboard())
        
    elif text == "বাংলা 🇧🇩":
        update_user_lang(user_id, 'bn')
        await update.message.reply_text("ভাষা বাংলায় পরিবর্তন করা হয়েছে!", reply_markup=get_user_keyboard())
        
    # Admin Handlers
    elif user_id == ADMIN_ID:
        if text == "📊 View Users":
            conn = sqlite3.connect("clickearn.db")
            count = conn.cursor().execute("SELECT COUNT(*) FROM users").fetchone()[0]
            conn.close()
            await update.message.reply_text(f"📊 Total Registered Users: {count}", reply_markup=get_admin_keyboard())
            
        elif text == "➕ Add Task":
            await update.message.reply_text("➕ Send task details format:\nTitle | URL | Reward", reply_markup=get_cancel_keyboard())
            
        elif text in ["⚠️ Suspicious Users", "🚫 Block User", "🟢 Unblock User"]:
            await update.message.reply_text(f"⚙️ Selected: {text}", reply_markup=get_cancel_keyboard())

# ---------------------------------------------------------
# 6. CONVERSATION HANDLER FOR ADMIN "GIVE BONUS"
# ---------------------------------------------------------
async def give_bonus_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("🎁 Enter the User ID to receive the bonus:", reply_markup=get_cancel_keyboard())
    return BONUS_ID

async def bonus_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Cancel":
        await update.message.reply_text("Action cancelled.", reply_markup=get_admin_keyboard())
        return ConversationHandler.END
    try:
        context.user_data['target_user_id'] = int(text)
        await update.message.reply_text("💵 Enter bonus amount ($):", reply_markup=get_cancel_keyboard())
        return BONUS_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Invalid User ID. Enter numbers only or press ❌ Cancel.")
        return BONUS_ID

async def bonus_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Cancel":
        await update.message.reply_text("Action cancelled.", reply_markup=get_admin_keyboard())
        return ConversationHandler.END
    try:
        amount = float(text)
        target_id = context.user_data['target_user_id']
        add_user_balance(target_id, amount)
        
        # Notify target user
        try:
            await context.bot.send_message(
                chat_id=target_id, 
                text=f"🎁 **Bonus Received!**\nYou received ${amount:.4f} bonus from Admin!"
            )
        except Exception:
            pass
            
        await update.message.reply_text(
            f"✅ Successfully sent ${amount:.4f} bonus to User ID `{target_id}`!",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Enter numbers only (e.g., 0.50) or press ❌ Cancel.")
        return BONUS_AMOUNT

async def bonus_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Action cancelled.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# ---------------------------------------------------------
# 7. MAIN FUNCTION
# ---------------------------------------------------------
def main():
    init_db()
    
    # Run Flask in background thread
    Thread(target=run_flask, daemon=True).start()
    
    # Initialize Telegram Application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Bonus Conversation Handler
    bonus_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎁 Give Bonus$"), give_bonus_start)],
        states={
            BONUS_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, bonus_id_received)],
            BONUS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bonus_amount_received)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), bonus_cancel)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(bonus_conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logging.basicConfig(level=logging.INFO)
    print("Bot started with Persistent Reply Keyboard Menu...")
    app.run_polling()

if __name__ == "__main__":
    main()
def main():
    init_db()
    
    # Run Flask in background thread for Render
    Thread(target=run_flask, daemon=True).start()
    
    # Initialize Telegram Application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Bonus Conversation Handler
    bonus_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎁 Give Bonus$"), give_bonus_start)],
        states={
            BONUS_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, bonus_id_received)],
            BONUS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bonus_amount_received)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), bonus_cancel)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(bonus_conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logging.basicConfig(level=logging.INFO)
    print("Bot started successfully...")
    
    # Run polling cleanly without conflicts
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
