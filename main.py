import os
import sqlite3
import logging
from threading import Thread
from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# --- LOGGING SETUP ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- FLASK KEEP-ALIVE SERVER (Render 24/7 Uptime) ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "ClickEarn Pro Bot is running 24/7!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
ADMIN_ID = 8808647263
OFFICIAL_CHANNEL = "@ClickEarnProOfficial"
SUPPORT_PHONE = "01720616501"
SUPPORT_URL = f"https://t.me/+8801720616501"
DOLLAR_RATE = 120.0  # 120 BDT per 1 USD
WITHDRAW_FEE = 0.02   # $0.02
REFERRAL_REWARD_ON_WITHDRAW = 0.01 # $0.01

# --- CONVERSATION STATES ---
AWAITING_PAYMENT_ADDRESS = 1

# --- MULTI-LANGUAGE DICTIONARY ---
LANG_TEXTS = {
    'bn': {
        'welcome': "👋 'ClickEarn Pro'-এ স্বাগতম!\nকাজ সম্পন্ন করে প্রতিদিন ইনকাম করুন।\n\n⚠️ অবশই আমাদের অফিসিয়াল চ্যানেলে জয়েন থাকতে হবে।",
        'tasks': "📋 **উপলব্ধ টাস্কসমূহ:**\nনিচের চ্যানেলগুলোতে জয়েন করুন এবং রিওয়ার্ড দাবী করুন।",
        'balance': "💰 **আপনার ব্যালেন্স বিবরণী:**\n\nবর্তমান ব্যালেন্স: `${balance:.4f}` USD (~{bdt:.2f} BDT)",
        'withdraw_select': "💳 **উইথড্র অপশন:**\nপদ্ধতি সিলেক্ট করুন:\n• Binance (Min $0.20)\n• bKash (Min $1.00 - Rate: 120 BDT/$)",
        'referral': "👥 **রেফারাল প্রোগ্রাম:**\nআপনার লিংক দিয়ে কাউকে ইনভাইট করুন। রেফার করা ইউজার ১ম বার উইথড্র করলে আপনি পাবেন `${reward}` ইনস্ট্যান্ট বোনাস!\n\n🔗 রেফার লিংক:\n`https://t.me/{bot_username}?start={user_id}`",
        'lang_select': "🌐 **ভাষা পরিবর্তন করুন / Choose Language:**",
        'must_join': "⚠️ বটের সকল ফিচার ব্যবহার করতে প্রথমে আমাদের অফিসিয়াল চ্যানেলে জয়েন করুন!",
        'joined_btn': "✅ Check / Verify",
        'join_channel_btn': "📢 Join Channel",
        'cancel_btn': "❌ Cancel",
        'support_btn': "📞 Support",
        'cancelled': "🏠 মূল মেনুতে ফিরে আসা হয়েছে।",
        'no_tasks': "❌ এই মুহূর্তে কোনো নতুন টাস্ক খালি নেই। পরে আবার চেষ্টা করুন।",
        'task_claimed': "🎉 অভিনন্দন! আপনি `${reward}` পেয়ে গেছেন।",
        'task_not_joined': "❌ আপনি এখনও এই চ্যানেলে জয়েন করেননি! আগে জয়েন করুন।",
        'penalty_alert': "🚨 **উইথড্র বাতিল করা হয়েছে!**\n\nআপনি পূর্বে সম্পন্ন করা চ্যানেল থেকে লিভ নিয়েছেন:\n• চ্যানেল: {channel}\n• জরিমানা কাটা হয়েছে: `${reward}`\n\nসবগুলো চ্যানেলে জয়েন থাকা বাধ্যতামূলক!",
        'min_withdraw_err': "❌ অপর্যাপ্ত ব্যালেন্স! সর্বনিম্ন উইথড্র অ্যামাউন্ট: `${min_amt}` (ফি: `${fee}`)",
        'enter_address': "📝 আপনার {method} অ্যাকাউন্ট তথ্য (Address/Phone Number) প্রদান করুন:",
        'withdraw_success': "✅ উইথড্র রিকোয়েস্ট সফলভাবে পাঠানো হয়েছে!\n\nপরিমাণ: `${net:.4f}`\nফি: `${fee}`\nঅ্যাকাউন্ট: `{address}`",
        'blocked_msg': "🚫 আপনার অ্যাকাউন্ট সাময়িকভাবে স্থগিত করা হয়েছে। আপিলের জন্য সাপোর্টে যোগাযোগ করুন।"
    },
    'en': {
        'welcome': "👋 Welcome to 'ClickEarn Pro'!\nComplete simple tasks and earn daily.\n\n⚠️ You must remain joined in our Official Channel.",
        'tasks': "📋 **Available Tasks:**\nJoin the channels below and claim your reward.",
        'balance': "💰 **Your Balance:**\n\nCurrent Balance: `${balance:.4f}` USD (~{bdt:.2f} BDT)",
        'withdraw_select': "💳 **Withdraw Options:**\nChoose payment method:\n• Binance (Min $0.20)\n• bKash (Min $1.00 - Rate: 120 BDT/$)",
        'referral': "👥 **Referral Program:**\nInvite friends using your referral link. Earn `${reward}` bonus when your referral makes their first withdrawal!\n\n🔗 Referral Link:\n`https://t.me/{bot_username}?start={user_id}`",
        'lang_select': "🌐 **Choose Language:**",
        'must_join': "⚠️ You must join our official channel to use the bot!",
        'joined_btn': "✅ Check / Verify",
        'join_channel_btn': "📢 Join Channel",
        'cancel_btn': "❌ Cancel",
        'support_btn': "📞 Support",
        'cancelled': "🏠 Returned to main menu.",
        'no_tasks': "❌ No tasks available right now. Please check back later.",
        'task_claimed': "🎉 Congratulations! You received `${reward}`.",
        'task_not_joined': "❌ You haven't joined this channel yet! Please join first.",
        'penalty_alert': "🚨 **Withdrawal Rejected!**\n\nYou left previously joined channel:\n• Channel: {channel}\n• Penalty Deducted: `${reward}`\n\nYou must remain joined in all completed channels!",
        'min_withdraw_err': "❌ Insufficient balance! Minimum withdrawal: `${min_amt}` (Fee: `${fee}`)",
        'enter_address': "📝 Enter your {method} account details (Address/Phone Number):",
        'withdraw_success': "✅ Withdrawal request submitted successfully!\n\nAmount: `${net:.4f}`\nFee: `${fee}`\nAccount: `{address}`",
        'blocked_msg': "🚫 Your account is suspended. Contact support to appeal."
    }
}

# --- DATABASE MANAGEMENT ---
DB_FILE = "earning_bot.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            referred_by INTEGER DEFAULT 0,
            lang TEXT DEFAULT 'bn',
            is_blocked INTEGER DEFAULT 0
        )
    ''')
    
    # Tasks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT,
            reward REAL,
            channel_id TEXT
        )
    ''')
    
    # User completed tasks tracking
    c.execute('''
        CREATE TABLE IF NOT EXISTS completed_tasks (
            user_id INTEGER,
            task_id INTEGER,
            PRIMARY KEY (user_id, task_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# --- HELPER FUNCTIONS ---
def get_user_lang(user_id: int) -> str:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row['lang'] if row else 'bn'

def is_user_blocked(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row['is_blocked']) if row else False

def get_text(user_id: int, key: str, **kwargs) -> str:
    lang = get_user_lang(user_id)
    lang_dict = LANG_TEXTS.get(lang, LANG_TEXTS['bn'])
    text = lang_dict.get(key, LANG_TEXTS['en'].get(key, ''))
    return text.format(**kwargs) if kwargs else text

async def check_channel_member(bot, user_id: int, channel_id: str) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking chat member for {user_id} in {channel_id}: {e}")
        return False

def build_main_keyboard(user_id: int):
    keyboard = [
        [InlineKeyboardButton("📋 Tasks", callback_data="nav_tasks"), InlineKeyboardButton("💰 My Balance", callback_data="nav_balance")],
        [InlineKeyboardButton("💳 Withdraw", callback_data="nav_withdraw"), InlineKeyboardButton("👥 Referral", callback_data="nav_referral")],
        [InlineKeyboardButton("🌐 Language", callback_data="nav_lang"), InlineKeyboardButton("📞 Support", url=SUPPORT_URL)],
        [InlineKeyboardButton(get_text(user_id, 'cancel_btn'), callback_data="nav_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- MANDATORY JOIN CHECK INTERCEPTOR ---
async def enforce_channel_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    # Skip check for admin
    if user.id == ADMIN_ID:
        return True

    # Check Block status
    if is_user_blocked(user.id):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(user.id, 'support_btn'), url=SUPPORT_URL)]])
        msg_text = get_text(user.id, 'blocked_msg')
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(msg_text, reply_markup=keyboard)
        elif update.message:
            await update.message.reply_text(msg_text, reply_markup=keyboard)
        return False

    is_joined = await check_channel_member(context.bot, user.id, OFFICIAL_CHANNEL)
    if not is_joined:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_text(user.id, 'join_channel_btn'), url=f"https://t.me/{OFFICIAL_CHANNEL.replace('@', '')}")],
            [InlineKeyboardButton(get_text(user.id, 'joined_btn'), callback_data="verify_channel_join")]
        ])
        text = get_text(user.id, 'must_join')
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=keyboard)
        elif update.message:
            await update.message.reply_text(text, reply_markup=keyboard)
        return False
    return True

# --- COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()
    c = conn.cursor()
    
    # Register user if not exists
    c.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
    if not c.fetchone():
        ref_id = 0
        if context.args and context.args[0].isdigit():
            possible_ref = int(context.args[0])
            if possible_ref != user.id:
                ref_id = possible_ref
        c.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
                  (user.id, user.username or "", ref_id))
        conn.commit()
    conn.close()

    if await enforce_channel_join(update, context):
        text = get_text(user.id, 'welcome')
        await update.message.reply_text(text, reply_markup=build_main_keyboard(user.id), parse_mode="Markdown")

# --- UI NAVIGATION CALLBACKS ---
async def navigation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "verify_channel_join":
        if await enforce_channel_join(update, context):
            text = get_text(user_id, 'welcome')
            await query.edit_message_text(text, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")
        return

    if not await enforce_channel_join(update, context):
        return

    if data == "nav_cancel":
        await query.edit_message_text(get_text(user_id, 'cancelled'), reply_markup=build_main_keyboard(user_id))
    
    elif data == "nav_balance":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = c.fetchone()['balance']
        conn.close()
        bdt_val = bal * DOLLAR_RATE
        text = get_text(user_id, 'balance', balance=bal, bdt=bdt_val)
        await query.edit_message_text(text, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")

    elif data == "nav_referral":
        bot_obj = await context.bot.get_me()
        text = get_text(user_id, 'referral', reward=REFERRAL_REWARD_ON_WITHDRAW, bot_username=bot_obj.username, user_id=user_id)
        await query.edit_message_text(text, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")

    elif data == "nav_lang":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="setlang_bn"), InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")],
            [InlineKeyboardButton(get_text(user_id, 'cancel_btn'), callback_data="nav_cancel")]
        ])
        await query.edit_message_text(get_text(user_id, 'lang_select'), reply_markup=keyboard)

    elif data.startswith("setlang_"):
        new_lang = data.split("_")[1]
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET lang = ? WHERE user_id = ?", (new_lang, user_id))
        conn.commit()
        conn.close()
        await query.edit_message_text(get_text(user_id, 'welcome'), reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")

    elif data == "nav_tasks":
        await display_tasks(update, context)

    elif data.startswith("claim_task_"):
        task_id = int(data.split("_")[2])
        await process_task_claim(update, context, task_id)

    elif data == "nav_withdraw":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟡 Binance (Min $0.20)", callback_data="wmethod_binance")],
            [InlineKeyboardButton("🇧🇩 bKash (Min $1.00)", callback_data="wmethod_bkash")],
            [InlineKeyboardButton(get_text(user_id, 'cancel_btn'), callback_data="nav_cancel")]
        ])
        await query.edit_message_text(get_text(user_id, 'withdraw_select'), reply_markup=keyboard, parse_mode="Markdown")

# --- TASK SYSTEM & ZERO-LOSS AUTO-VERIFY ---
async def display_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT t.* FROM tasks t 
        LEFT JOIN completed_tasks ct ON t.task_id = ct.task_id AND ct.user_id = ? 
        WHERE ct.task_id IS NULL
    """, (user_id,))
    available_tasks = c.fetchall()
    conn.close()

    if not available_tasks:
        await query.edit_message_text(get_text(user_id, 'no_tasks'), reply_markup=build_main_keyboard(user_id))
        return

    buttons = []
    for task in available_tasks:
        btn_text = f"📢 {task['title']} (${task['reward']:.4f})"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"claim_task_{task['task_id']}")])
    
    buttons.append([InlineKeyboardButton(get_text(user_id, 'cancel_btn'), callback_data="nav_cancel")])
    await query.edit_message_text(get_text(user_id, 'tasks'), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

async def process_task_claim(update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: int):
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    task = c.fetchone()

    if not task:
        conn.close()
        await query.edit_message_text("❌ Task not found.", reply_markup=build_main_keyboard(user_id))
        return

    is_joined = await check_channel_member(context.bot, user_id, task['channel_id'])
    
    if not is_joined:
        conn.close()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=task['link'])],
            [InlineKeyboardButton("✅ Verify Join", callback_data=f"claim_task_{task_id}")],
            [InlineKeyboardButton(get_text(user_id, 'cancel_btn'), callback_data="nav_cancel")]
        ])
        await query.edit_message_text(get_text(user_id, 'task_not_joined'), reply_markup=keyboard)
        return

    # User joined successfully -> Credit Balance
    c.execute("INSERT INTO completed_tasks (user_id, task_id) VALUES (?, ?)", (user_id, task_id))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (task['reward'], user_id))
    conn.commit()
    conn.close()

    await query.edit_message_text(get_text(user_id, 'task_claimed', reward=f"{task['reward']:.4f}"), reply_markup=build_main_keyboard(user_id))

# --- WITHDRAWAL CONVERSATION & STRICT ZERO-LOSS PENALTY SCAN ---
async def start_withdrawal_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    method = query.data.split("_")[1]

    min_required = 0.20 if method == "binance" else 1.00

    conn = get_db()
    c = conn.cursor()
    
    # 1. STRICT ZERO-LOSS RE-VERIFICATION SCAN
    c.execute("""
        SELECT t.task_id, t.title, t.reward, t.channel_id 
        FROM completed_tasks ct 
        JOIN tasks t ON ct.task_id = t.task_id 
        WHERE ct.user_id = ?
    """, (user_id,))
    completed = c.fetchall()

    for item in completed:
        still_member = await check_channel_member(context.bot, user_id, item['channel_id'])
        if not still_member:
            # PENALTY: Deduct reward & Remove completed entry
            c.execute("UPDATE users SET balance = MAX(0.0, balance - ?) WHERE user_id = ?", (item['reward'], user_id))
            c.execute("DELETE FROM completed_tasks WHERE user_id = ? AND task_id = ?", (user_id, item['task_id']))
            conn.commit()
            conn.close()
            
            alert = get_text(user_id, 'penalty_alert', channel=item['title'], reward=f"{item['reward']:.4f}")
            await query.edit_message_text(alert, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")
            return ConversationHandler.END

    # 2. Balance Check
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = c.fetchone()['balance']
    conn.close()

    if balance < min_required:
        await query.edit_message_text(
            get_text(user_id, 'min_withdraw_err', min_amt=f"{min_required:.2f}", fee=f"{WITHDRAW_FEE:.2f}"),
            reply_markup=build_main_keyboard(user_id)
        )
        return ConversationHandler.END

    context.user_data['withdraw_method'] = method
    context.user_data['withdraw_amount'] = balance

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(user_id, 'cancel_btn'), callback_data="nav_cancel")]])
    await query.edit_message_text(get_text(user_id, 'enter_address', method=method.capitalize()), reply_markup=keyboard)
    return AWAITING_PAYMENT_ADDRESS

async def process_withdrawal_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    address = update.message.text
    method = context.user_data.get('withdraw_method')
    amount = context.user_data.get('withdraw_amount', 0.0)

    net_amount = amount - WITHDRAW_FEE

    conn = get_db()
    c = conn.cursor()
    
    # Deduct balance
    c.execute("UPDATE users SET balance = 0.0 WHERE user_id = ?", (user_id,))
    
    # Process Referral Bonus for Referrer
    c.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row and row['referred_by'] > 0:
        referrer_id = row['referred_by']
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REFERRAL_REWARD_ON_WITHDRAW, referrer_id))
        c.execute("UPDATE users SET referred_by = 0 WHERE user_id = ?", (user_id,)) # Reward once per referred user
    
    conn.commit()
    conn.close()

    # Notify Admin
    admin_msg = (
        f"🚨 **NEW WITHDRAWAL REQUEST**\n\n"
        f"👤 User: [{user_id}](tg://user?id={user_id})\n"
        f"💳 Method: {method.upper()}\n"
        f"💰 Total: ${amount:.4f}\n"
        f"🔻 Fee: ${WITHDRAW_FEE:.2f}\n"
        f"💵 Net Pay: ${net_amount:.4f}\n"
        f"📝 Address: `{address}`"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown")

    # Reply User
    success_text = get_text(user_id, 'withdraw_success', net=net_amount, fee=WITHDRAW_FEE, address=address)
    await update.message.reply_text(success_text, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(get_text(user_id, 'cancelled'), reply_markup=build_main_keyboard(user_id))
    else:
        await update.message.reply_text(get_text(user_id, 'cancelled'), reply_markup=build_main_keyboard(user_id))
    return ConversationHandler.END

# --- ADMIN COMMANDS ---
async def admin_add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        raw_text = " ".join(context.args)
        title, link, reward, channel_id = [x.strip() for x in raw_text.split("|")]
        
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO tasks (title, link, reward, channel_id) VALUES (?, ?, ?, ?)",
                  (title, link, float(reward), channel_id))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"✅ Task Added Successfully!\nTitle: {title}\nReward: ${reward}")
    except Exception as e:
        await update.message.reply_text("❌ Usage: `/addtask Title | Link | Reward | @channel_id`", parse_mode="Markdown")

async def admin_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, balance, is_blocked FROM users")
    users = c.fetchall()
    conn.close()

    msg = f"📊 **TOTAL USERS: {len(users)}**\n\n"
    for u in users[:50]: # First 50
        status = "🔴 Blocked" if u['is_blocked'] else "🟢 Active"
        msg += f"• [{u['user_id']}](tg://user?id={u['user_id']}) | @{u['username']} | `${u['balance']:.2f}` | {status}\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def admin_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args:
        return
    
    target_id = int(context.args[0])
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🚫 User {target_id} blocked successfully.")

async def admin_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args:
        return
    
    target_id = int(context.args[0])
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_blocked = 0 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ User {target_id} unblocked successfully.")

# --- MAIN BOT INITIALIZATION ---
def main():
    init_db()
    keep_alive() # Run Flask Keep-alive server for Render uptime

    app = Application.builder().token(BOT_TOKEN).build()

    # Withdrawal Conversation Handler
    withdraw_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_withdrawal_flow, pattern="^wmethod_")],
        states={
            AWAITING_PAYMENT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal_address)]
        },
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^nav_cancel$")]
    )

    # Register Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("addtask", admin_add_task))
    app.add_handler(CommandHandler("allusers", admin_all_users))
    app.add_handler(CommandHandler("block", admin_block))
    app.add_handler(CommandHandler("unblock", admin_unblock))
    
    app.add_handler(withdraw_handler)
    app.add_handler(CallbackQueryHandler(navigation_handler))

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
