import os
import sqlite3
import time
import logging
from threading import Thread
import telebot
from telebot import types

# ================= CONFIGURATION =================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Apnar BotFather Token ekhane din
ADMIN_ID = 8808647263                # Apnar Telegram Numeric User ID ekhane din
OFFICIAL_CHANNEL = "@ClickEarnProOfficial" # Apnar official channel username ekhane din
MIN_WITHDRAW = 0.20
WITHDRAW_FEE = 0.02
TEN_DAYS_SEC = 10 * 86400  # 10 days in seconds

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
logging.basicConfig(level=logging.INFO)

USER_STATES = {}  # In-memory input state tracker

# ================= DATABASE SETUP =================
def get_db():
    conn = sqlite3.connect("bot.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            pending_balance REAL DEFAULT 0.0,
            referrer_id INTEGER,
            lang TEXT DEFAULT 'bn',
            is_banned INTEGER DEFAULT 0,
            has_withdrawn_once INTEGER DEFAULT 0,
            joined_at INTEGER
        )
    ''')
    
    # Tasks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_bn TEXT,
            title_en TEXT,
            reward REAL,
            link TEXT,
            task_type TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # User completed tasks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            reward REAL,
            matures_at INTEGER,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # Withdrawals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            method TEXT,
            address TEXT,
            amount REAL,
            fee REAL,
            net_amount REAL,
            status TEXT DEFAULT 'pending',
            created_at INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ================= BILINGUAL DICTIONARY (BN & EN) =================
TEXTS = {
    'bn': {
        'welcome': "👋 **স্বাগতম!**\n\nসহজ কাজ করে টাকা আয় করুন। বোটে কাজ শুরু করতে প্রথমে আমাদের অফিশিয়াল চ্যানেলে জয়েন করুন।",
        'must_join': "⚠️ বোটে কাজ করতে আমাদের অফিশিয়াল চ্যানেলে জয়েন করা বাধ্যতামূলক!",
        'btn_join': "📢 অফিশিয়াল চ্যানেল",
        'btn_verify': "✅ ভেরিফাই করুন",
        'verified_success': "🎉 আপনাকে ধন্যবাদ! ভেরিফিকেশন সফল হয়েছে।",
        'not_joined': "❌ আপনি এখনও চ্যানেলে জয়েন করেননি! জয়েন করে ভেরিফাই বাটনে চাপুন।",
        'btn_balance': "💰 ব্যালেন্স",
        'btn_tasks': "📋 কাজ",
        'btn_withdraw': "📥 উত্তোলন",
        'btn_profile': "👤 প্রোফাইল",
        'btn_referrals': "👥 আমার রেফারেল",
        'btn_lang': "🌐 ভাষা / Language",
        'btn_cancel': "❌ Cancel",
        'action_cancelled': "👍 কাজ বাতিল করা হয়েছে।",
        'balance_info': "💰 **আপনার ওয়ালেট বিবরণ:**\n\nMain Balance: `${balance:.4f}`\nPending Balance: `${pending:.4f}`\n\n*(১০ দিন পেন্ডিং থাকার পর জয়েন টাস্কের টাকা মেইন ব্যালেন্সে যুক্ত হবে)*",
        'profile_info': "👤 **আপনার প্রোফাইল:**\n\n🆔 User ID: `{user_id}`\n🌐 বর্তমান ভাষা: {lang_name}\n📅 জয়েন তারিখ: {date}",
        'referral_info': "👥 **রেফারেল প্রোগ্রাম:**\n\n🔗 **আপনার রেফারেল লিংক:**\n`https://t.me/{bot_username}?start={user_id}`\n\n📊 মোট রেফারেল: {ref_count} জন\n\n💡 **নিয়ম:** আপনি যাকে রেফার করবেন, সে ১ম বার উইথড্র দিলে কেটে নেওয়া $0.02 ফি সরাসরি আপনার ব্যালেন্সে যোগ হবে!",
        'lang_select': "🌐 **আপনার পছন্দের ভাষা নির্বাচন করুন / Select Language:**",
        'lang_changed': "✅ ভাষা পরিবর্তন করা হয়েছে।",
        'tasks_title': "📋 **এভেলেবল কাজসমূহ:**",
        'no_tasks': "❌ বর্তমানে কোনো কাজ নেই! নতুন কাজ আসলে জানিয়ে দেওয়া হবে।",
        'withdraw_select_method': "📥 **উইথড্র মেথড সিলেক্ট করুন:**",
        'withdraw_min_error': "❌ সর্বনিম্ন উইথড্র অ্যামাউন্ট ${min:.2f}। আপনার ব্যালেন্স: ${bal:.4f}",
        'withdraw_enter_addr': "🔹 আপনার {method} ওয়ালেট এড্রেসটি লিখে পাঠান:",
        'withdraw_enter_amount': "🔹 কত ডলার উইথড্র করতে চান লিখুন (সর্বনিম্ন ${min:.2f}):",
        'withdraw_success': "✅ **উইথড্র রিকোয়েস্ট সফলভাবে জমা হয়েছে!**\n\n💰 মোট উত্তোলনের পরিমাণ: `${amount:.4f}`\n🔻 ফি বা কমিশন কাটা হয়েছে: `${fee:.4f}`\n📥 আপনি পাবেন: `${net:.4f}`\n\nএডমিন প্যানেল থেকে রিভিউ করে পেমেন্ট সম্পন্ন করা হবে।",
        'insufficient_balance': "❌ আপনার একাউন্টে পর্যাপ্ত মেইন ব্যালেন্স নেই!",
        'leave_warning': "⚠️ **সতর্কবার্তা!**\n\nআপনি অফিশিয়াল/টাস্ক চ্যানেল থেকে লিভ নেওয়ায় আপনার ব্যালেন্স থেকে ${deducted:.4f} কেটে নেওয়া হয়েছে। পরবর্তীতে এমন করলে একাউন্ট ব্লক করা হতে পারে!",
        'banned_msg': "🚫 আপনার একাউন্টটি সাময়িকভাবে ব্লক করা হয়েছে।",
        
        # Admin Panel Texts (BN)
        'admin_menu': "⚙️ **ADMIN PANEL**\n\nনিচের যেকোনো অপশন বেছে নিন:",
        'admin_btn_users': "👥 ইউজার্স লিস্ট",
        'admin_btn_withdraws': "📥 পেন্ডিং উইথড্র",
        'admin_btn_add_task': "➕ টাস্ক এড করুন",
        'admin_btn_broadcast': "📢 ব্রডকাস্ট",
        'admin_btn_stats': "📊 স্ট্যাটস",
        'admin_btn_user_edit': "🔍 ইউজার সার্চ / ব্যালেন্স এডিট"
    },
    'en': {
        'welcome': "👋 **Welcome!**\n\nEarn money by completing simple tasks. Please join our official channel to get started.",
        'must_join': "⚠️ You must join our official channel to use this bot!",
        'btn_join': "📢 Official Channel",
        'btn_verify': "✅ Verify",
        'verified_success': "🎉 Thank you! Verification successful.",
        'not_joined': "❌ You have not joined the channel yet! Please join and click verify.",
        'btn_balance': "💰 Balance",
        'btn_tasks': "📋 Tasks",
        'btn_withdraw': "📥 Withdraw",
        'btn_profile': "👤 Profile",
        'btn_referrals': "👥 My Referrals",
        'btn_lang': "🌐 Language / ভাষা",
        'btn_cancel': "❌ Cancel",
        'action_cancelled': "👍 Action cancelled.",
        'balance_info': "💰 **Your Wallet Details:**\n\nMain Balance: `${balance:.4f}`\nPending Balance: `${pending:.4f}`\n\n*(Pending task rewards unlock after 10 days)*",
        'profile_info': "👤 **Your Profile:**\n\n🆔 User ID: `{user_id}`\n🌐 Language: {lang_name}\n📅 Joined: {date}",
        'referral_info': "👥 **Referral Program:**\n\n🔗 **Your Referral Link:**\n`https://t.me/{bot_username}?start={user_id}`\n\n📊 Total Referrals: {ref_count}\n\n💡 **Rule:** When your referee makes their 1st withdrawal, the $0.02 fee deducted from them will automatically be added to your balance!",
        'lang_select': "🌐 **Select your preferred language:**",
        'lang_changed': "✅ Language updated successfully.",
        'tasks_title': "📋 **Available Tasks:**",
        'no_tasks': "❌ No tasks available right now! Check back later.",
        'withdraw_select_method': "📥 **Select Withdrawal Method:**",
        'withdraw_min_error': "❌ Minimum withdrawal is ${min:.2f}. Your balance:${bal:.4f}",
        'withdraw_enter_addr': "🔹 Enter your {method} wallet address:",
        'withdraw_enter_amount': "🔹 Enter withdrawal amount (Min ${min:.2f}):",
        'withdraw_success': "✅ **Withdrawal Request Submitted!**\n\n💰 Total Requested: `${amount:.4f}`\n🔻 Fee Deducted: `${fee:.4f}`\n📥 Net Received: `${net:.4f}`\n\nAdmin will review and process your request soon.",
        'insufficient_balance': "❌ Insufficient main balance!",
        'leave_warning': "⚠️ **Warning!**\n\nYou left a required channel/group. ${deducted:.4f} was deducted from your balance. Repeated actions may cause account termination!",
        'banned_msg': "🚫 Your account has been suspended.",
        
        # Admin Panel Texts (EN)
        'admin_menu': "⚙️ **ADMIN PANEL**\n\nSelect an option below:",
        'admin_btn_users': "👥 Users List",
        'admin_btn_withdraws': "📥 Pending Withdraws",
        'admin_btn_add_task': "➕ Add Task",
        'admin_btn_broadcast': "📢 Broadcast",
        'admin_btn_stats': "📊 Stats",
        'admin_btn_user_edit': "🔍 Search User / Edit Balance"
    }
}

# ================= HELPER FUNCTIONS =================
def get_user_lang(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row['lang'] if row else 'bn'

def is_user_joined(user_id, channel_username):
    try:
        member = bot.get_chat_member(channel_username, user_id)
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return False

def get_main_keyboard(user_id):
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton(t['btn_balance']),
        types.KeyboardButton(t['btn_tasks']),
        types.KeyboardButton(t['btn_withdraw']),
        types.KeyboardButton(t['btn_profile']),
        types.KeyboardButton(t['btn_referrals']),
        types.KeyboardButton(t['btn_lang'])
    )
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("⚙️ Admin Panel"))
    return markup

def get_cancel_keyboard(user_id):
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton(t['btn_cancel']))
    return markup

def get_admin_keyboard(user_id):
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton(t['admin_btn_users']),
        types.KeyboardButton(t['admin_btn_withdraws']),
        types.KeyboardButton(t['admin_btn_add_task']),
        types.KeyboardButton(t['admin_btn_broadcast']),
        types.KeyboardButton(t['admin_btn_stats']),
        types.KeyboardButton(t['admin_btn_user_edit']),
        types.KeyboardButton("🔙 Main Menu")
    )
    return markup

# ================= USER & FORCE JOIN HANDLERS =================
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    
    # Check ban status
    cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row['is_banned']:
        lang = get_user_lang(user_id)
        bot.send_message(user_id, TEXTS[lang]['banned_msg'])
        conn.close()
        return

    # Handle Referral
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        ref_candidate = int(args[1])
        if ref_candidate != user_id:
            referrer_id = ref_candidate

    if not row:
        cursor.execute(
            "INSERT INTO users (user_id, referrer_id, joined_at) VALUES (?, ?, ?)",
            (user_id, referrer_id, int(time.time()))
        )
        conn.commit()

    conn.close()
    
    # Check Official Channel Force Join
    if not is_user_joined(user_id, OFFICIAL_CHANNEL):
        lang = get_user_lang(user_id)
        t = TEXTS[lang]
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton(t['btn_join'], url=f"https://t.me/{OFFICIAL_CHANNEL.replace('@','')}")
        btn2 = types.InlineKeyboardButton(t['btn_verify'], callback_data="verify_official_join")
        markup.add(btn1)
        markup.add(btn2)
        bot.send_message(user_id, t['must_join'], reply_markup=markup)
        return

    lang = get_user_lang(user_id)
    bot.send_message(user_id, TEXTS[lang]['welcome'], reply_markup=get_main_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "verify_official_join")
def verify_official_join(call):
    user_id = call.from_user.id
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    if is_user_joined(user_id, OFFICIAL_CHANNEL):
        bot.answer_callback_query(call.id, t['verified_success'])
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, t['welcome'], reply_markup=get_main_keyboard(user_id))
    else:
        bot.answer_callback_query(call.id, t['not_joined'], show_alert=True)

# ================= MAIN MENU BUTTON ROUTING =================
@bot.message_handler(func=lambda m: True)
def handle_text_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    lang = get_user_lang(user_id)
    t = TEXTS[lang]

    # Handle State Cancellation
    if text in [TEXTS['bn']['btn_cancel'], TEXTS['en']['btn_cancel'], "❌ Cancel"]:
        USER_STATES.pop(user_id, None)
        bot.send_message(user_id, t['action_cancelled'], reply_markup=get_main_keyboard(user_id))
        return

    # Check Active Input State
    if user_id in USER_STATES:
        process_user_state(message)
        return

    # 💰 Balance
    if text in [TEXTS['bn']['btn_balance'], TEXTS['en']['btn_balance']]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance, pending_balance FROM users WHERE user_id = ?", (user_id,))
        u = cursor.fetchone()
        conn.close()
        msg = t['balance_info'].format(balance=u['balance'], pending=u['pending_balance'])
        bot.send_message(user_id, msg)

    # 👤 Profile
    elif text in [TEXTS['bn']['btn_profile'], TEXTS['en']['btn_profile']]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT joined_at FROM users WHERE user_id = ?", (user_id,))
        u = cursor.fetchone()
        conn.close()
        date_str = time.strftime('%Y-%m-%d', time.localtime(u['joined_at'])) if u else "N/A"
        lang_name = "বাংলা" if lang == 'bn' else "English"
        msg = t['profile_info'].format(user_id=user_id, lang_name=lang_name, date=date_str)
        bot.send_message(user_id, msg)

    # 👥 My Referrals
    elif text in [TEXTS['bn']['btn_referrals'], TEXTS['en']['btn_referrals']]:
        bot_info = bot.get_me()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE referrer_id = ?", (user_id,))
        count = cursor.fetchone()['cnt']
        conn.close()
        msg = t['referral_info'].format(bot_username=bot_info.username, user_id=user_id, ref_count=count)
        bot.send_message(user_id, msg)

    # 🌐 Language / Switch
    elif text in [TEXTS['bn']['btn_lang'], TEXTS['en']['btn_lang']]:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🇧🇩 বাংলা", callback_data="set_lang_bn"),
            types.InlineKeyboardButton("🇺🇸 English", callback_data="set_lang_en")
        )
        bot.send_message(user_id, t['lang_select'], reply_markup=markup)

    # 📋 Tasks
    elif text in [TEXTS['bn']['btn_tasks'], TEXTS['en']['btn_tasks']]:
        show_tasks_list(user_id)

    # 📥 Withdraw
    elif text in [TEXTS['bn']['btn_withdraw'], TEXTS['en']['btn_withdraw']]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = cursor.fetchone()['balance']
        conn.close()

        if bal < MIN_WITHDRAW:
            bot.send_message(user_id, t['withdraw_min_error'].format(min=MIN_WITHDRAW, bal=bal))
            return

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("USDT (BEP-20)", callback_data="withdraw_meth_USDT (BEP-20)"),
            types.InlineKeyboardButton("Bkash / Nagad", callback_data="withdraw_meth_Bkash/Nagad")
        )
        bot.send_message(user_id, t['withdraw_select_method'], reply_markup=markup)

    # ⚙️ Admin Panel Command / Button
    elif text == "⚙️ Admin Panel" and user_id == ADMIN_ID:
        bot.send_message(user_id, t['admin_menu'], reply_markup=get_admin_keyboard(user_id))

    elif text == "🔙 Main Menu":
        bot.send_message(user_id, t['welcome'], reply_markup=get_main_keyboard(user_id))

    # Admin Panel Sub-Buttons
    elif user_id == ADMIN_ID:
        handle_admin_buttons(message)

# ================= LANGUAGE TOGGLE CALLBACK =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_lang_"))
def set_language_callback(call):
    user_id = call.from_user.id
    new_lang = call.data.split("_")[2]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (new_lang, user_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, TEXTS[new_lang]['lang_changed'])
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(user_id, TEXTS[new_lang]['welcome'], reply_markup=get_main_keyboard(user_id))

# ================= TASKS SYSTEM =================
def show_tasks_list(user_id):
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE status = 'active'")
    all_tasks = cursor.fetchall()
    
    # Filter completed tasks
    cursor.execute("SELECT task_id FROM user_tasks WHERE user_id = ?", (user_id,))
    completed_ids = [row['task_id'] for row in cursor.fetchall()]
    conn.close()

    available_tasks = [task for task in all_tasks if task['id'] not in completed_ids]

    if not available_tasks:
        bot.send_message(user_id, t['no_tasks'])
        return

    markup = types.InlineKeyboardMarkup()
    for task in available_tasks:
        title = task['title_bn'] if lang == 'bn' else task['title_en']
        markup.add(types.InlineKeyboardButton(f"{title} (${task['reward']:.4f})", callback_data=f"do_task_{task['id']}"))
    
    bot.send_message(user_id, t['tasks_title'], reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("do_task_"))
def task_detail_callback(call):
    user_id = call.from_user.id
    task_id = int(call.data.split("_")[2])
    lang = get_user_lang(user_id)
    t = TEXTS[lang]

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    conn.close()

    if not task:
        return

    title = task['title_bn'] if lang == 'bn' else task['title_en']
    msg = f"📌 **{title}**\n\n💰 Reward: `${task['reward']:.4f}`\n\n👉 Click below to complete task:"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Open Task Link", url=task['link']))
    markup.add(types.InlineKeyboardButton("✅ Claim Reward", callback_data=f"claim_task_{task['id']}"))
    bot.send_message(user_id, msg, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("claim_task_"))
def claim_task_callback(call):
    user_id = call.from_user.id
    task_id = int(call.data.split("_")[2])
    lang = get_user_lang(user_id)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()

    # Insert into user_tasks with 10 days maturity
    matures_at = int(time.time()) + TEN_DAYS_SEC
    cursor.execute(
        "INSERT INTO user_tasks (user_id, task_id, reward, matures_at, status) VALUES (?, ?, ?, ?, 'pending')",
        (user_id, task_id, task['reward'], matures_at)
    )
    cursor.execute("UPDATE users SET pending_balance = pending_balance + ? WHERE user_id = ?", (task['reward'], user_id))
    conn.commit()
    conn.close()

    bot.answer_callback_query(call.id, "✅ Task completed! Reward added to Pending Balance (Unlocks in 10 days).", show_alert=True)
    bot.delete_message(call.message.chat.id, call.message.message_id)

# ================= WITHDRAW SYSTEM =================
@bot.callback_query_handler(func=lambda call: call.data.startswith("withdraw_meth_"))
def select_withdraw_method(call):
    user_id = call.from_user.id
    method = call.data.split("_")[2]
    lang = get_user_lang(user_id)
    t = TEXTS[lang]

    USER_STATES[user_id] = {'step': 'withdraw_addr', 'method': method}
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(user_id, t['withdraw_enter_addr'].format(method=method), reply_markup=get_cancel_keyboard(user_id))

def process_user_state(message):
    user_id = message.from_user.id
    state = USER_STATES.get(user_id)
    lang = get_user_lang(user_id)
    t = TEXTS[lang]
    text = message.text.strip()

    # Step 1: Wallet Address Input
    if state['step'] == 'withdraw_addr':
        state['address'] = text
        state['step'] = 'withdraw_amount'
        bot.send_message(user_id, t['withdraw_enter_amount'].format(min=MIN_WITHDRAW), reply_markup=get_cancel_keyboard(user_id))

    # Step 2: Withdrawal Amount Input
    elif state['step'] == 'withdraw_amount':
        try:
            amount = float(text)
        except ValueError:
            bot.send_message(user_id, "❌ Valid number input করুন:")
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance, has_withdrawn_once, referrer_id FROM users WHERE user_id = ?", (user_id,))
        u = cursor.fetchone()

        if amount < MIN_WITHDRAW or amount > u['balance']:
            bot.send_message(user_id, t['insufficient_balance'], reply_markup=get_main_keyboard(user_id))
            USER_STATES.pop(user_id, None)
            conn.close()
            return

        fee = WITHDRAW_FEE
        net_amount = amount - fee

        # Deduct balance & insert withdrawal request
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        cursor.execute(
            "INSERT INTO withdrawals (user_id, method, address, amount, fee, net_amount, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, state['method'], state['address'], amount, fee, net_amount, int(time.time()))
        )

        # 🎯 REFERRAL FEE LOGIC FOR 1st WITHDRAWAL 🎯
        if u['has_withdrawn_once'] == 0:
            cursor.execute("UPDATE users SET has_withdrawn_once = 1 WHERE user_id = ?", (user_id,))
            referrer_id = u['referrer_id']
            if referrer_id:
                # Add $0.02 fee automatically to Referrer's balance
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (WITHDRAW_FEE, referrer_id))
                try:
                    ref_lang = get_user_lang(referrer_id)
                    ref_msg = f"🎉 **Referral Bonus Received!**\n\nYour referred user (ID: `{user_id}`) completed their 1st withdrawal! `${WITHDRAW_FEE:.4f}` has been added to your balance."
                    bot.send_message(referrer_id, ref_msg)
                except Exception:
                    pass

        conn.commit()
        conn.close()

        # Send confirmation message
        success_msg = t['withdraw_success'].format(amount=amount, fee=fee, net=net_amount)
        bot.send_message(user_id, success_msg, reply_markup=get_main_keyboard(user_id))
        USER_STATES.pop(user_id, None)

    # Admin State Handlers
    elif state['step'] == 'admin_add_task_bn':
        state['title_bn'] = text
        state['step'] = 'admin_add_task_en'
        bot.send_message(user_id, "🔹 Enter Task Title in English:", reply_markup=get_cancel_keyboard(user_id))

    elif state['step'] == 'admin_add_task_en':
        state['title_en'] = text
        state['step'] = 'admin_add_task_link'
        bot.send_message(user_id, "🔹 Enter Task Link:", reply_markup=get_cancel_keyboard(user_id))

    elif state['step'] == 'admin_add_task_link':
        state['link'] = text
        state['step'] = 'admin_add_task_reward'
        bot.send_message(user_id, "🔹 Enter Task Reward Amount ($):", reply_markup=get_cancel_keyboard(user_id))

    elif state['step'] == 'admin_add_task_reward':
        try:
            reward = float(text)
        except ValueError:
            bot.send_message(user_id, "❌ Enter a valid numeric amount:")
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (title_bn, title_en, reward, link, task_type) VALUES (?, ?, ?, ?, 'telegram')",
            (state['title_bn'], state['title_en'], reward, state['link'])
        )
        conn.commit()
        conn.close()
        bot.send_message(user_id, "✅ Task added successfully!", reply_markup=get_admin_keyboard(user_id))
        USER_STATES.pop(user_id, None)

    elif state['step'] == 'admin_broadcast':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()

        sent, failed = 0, 0
        for u in users:
            try:
                bot.send_message(u['user_id'], text)
                sent += 1
            except Exception:
                failed += 1

        bot.send_message(user_id, f"✅ Broadcast Complete!\n\nSent: {sent}\nFailed: {failed}", reply_markup=get_admin_keyboard(user_id))
        USER_STATES.pop(user_id, None)

# ================= ADMIN PANEL HANDLERS =================
def handle_admin_buttons(message):
    user_id = message.from_user.id
    text = message.text.strip()
    lang = get_user_lang(user_id)
    t = TEXTS[lang]

    # Users List
    if text in [TEXTS['bn']['admin_btn_users'], TEXTS['en']['admin_btn_users']]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, balance, is_banned FROM users LIMIT 20")
        users = cursor.fetchall()
        conn.close()

        msg = "👥 **BOT USERS LIST (Top 20):**\n\n"
        markup = types.InlineKeyboardMarkup()
        for u in users:
            status = "🚫 Banned" if u['is_banned'] else "✅ Active"
            msg += f"• ID: `{u['user_id']}` | Bal: `${u['balance']:.4f}` | {status}\n"
            markup.add(types.InlineKeyboardButton(f"💬 Direct Chat (ID: {u['user_id']})", url=f"tg://user?id={u['user_id']}"))

        bot.send_message(user_id, msg, reply_markup=markup)

    # Pending Withdrawals
    elif text in [TEXTS['bn']['admin_btn_withdraws'], TEXTS['en']['admin_btn_withdraws']]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM withdrawals WHERE status = 'pending'")
        withdraws = cursor.fetchall()
        conn.close()

        if not withdraws:
            bot.send_message(user_id, "✅ No pending withdrawal requests!")
            return

        for w in withdraws:
            w_msg = f"📥 **WITHDRAWAL REQUEST #{w['id']}**\n\n🆔 User ID: `{w['user_id']}`\n💳 Method: {w['method']}\n🏠 Address: `{w['address']}`\n💰 Total: `${w['amount']:.4f}`\n🔻 Fee: `${w['fee']:.4f}`\n📥 Net Pay: `${w['net_amount']:.4f}`"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"app_w_{w['id']}"),
                types.InlineKeyboardButton("❌ Reject", callback_data=f"rej_w_{w['id']}")
            )
            bot.send_message(user_id, w_msg, reply_markup=markup)

    # Add Task
    elif text in [TEXTS['bn']['admin_btn_add_task'], TEXTS['en']['admin_btn_add_task']]:
        USER_STATES[user_id] = {'step': 'admin_add_task_bn'}
        bot.send_message(user_id, "🔹 Enter Task Title in Bangla:", reply_markup=get_cancel_keyboard(user_id))

    # Broadcast
    elif text in [TEXTS['bn']['admin_btn_broadcast'], TEXTS['en']['admin_btn_broadcast']]:
        USER_STATES[user_id] = {'step': 'admin_broadcast'}
        bot.send_message(user_id, "📢 Enter message to broadcast to ALL users:", reply_markup=get_cancel_keyboard(user_id))

    # Stats
    elif text in [TEXTS['bn']['admin_btn_stats'], TEXTS['en']['admin_btn_stats']]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        u_cnt = cursor.fetchone()['total_users']
        cursor.execute("SELECT SUM(amount) as total_w FROM withdrawals WHERE status = 'approved'")
        w_sum = cursor.fetchone()['total_w'] or 0.0
        conn.close()

        stats_msg = f"📊 **BOT LIVE STATISTICS:**\n\n👥 Total Users: {u_cnt}\n💸 Total Paid Withdrawals: `${w_sum:.4f}`"
        bot.send_message(user_id, stats_msg)

# Withdraw Approval/Rejection Callbacks
@bot.callback_query_handler(func=lambda call: call.data.startswith(("app_w_", "rej_w_")))
def handle_withdraw_approval(call):
    action, _, w_id = call.data.split("_")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM withdrawals WHERE id = ?", (w_id,))
    w = cursor.fetchone()

    if action == "app":
        cursor.execute("UPDATE withdrawals SET status = 'approved' WHERE id = ?", (w_id,))
        bot.send_message(w['user_id'], f"🎉 Your withdrawal request of `${w['net_amount']:.4f}` has been approved!")
        bot.answer_callback_query(call.id, "Approved!")
    else:
        cursor.execute("UPDATE withdrawals SET status = 'rejected' WHERE id = ?", (w_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (w['amount'], w['user_id']))
        bot.send_message(w['user_id'], f"❌ Your withdrawal request of `${w['amount']:.4f}` was rejected. Amount refunded to balance.")
        bot.answer_callback_query(call.id, "Rejected & Refunded!")

    conn.commit()
    conn.close()
    bot.delete_message(call.message.chat.id, call.message.message_id)

# ================= BACKGROUND THREAD FOR 10-DAY MATURITY =================
def auto_release_pending_rewards():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            now = int(time.time())
            
            # Find mature tasks
            cursor.execute("SELECT * FROM user_tasks WHERE status = 'pending' AND matures_at <= ?", (now,))
            matures = cursor.fetchall()

            for m in matures:
                cursor.execute("UPDATE users SET balance = balance + ?, pending_balance = pending_balance - ? WHERE user_id = ?", 
                               (m['reward'], m['reward'], m['user_id']))
                cursor.execute("UPDATE user_tasks SET status = 'completed' WHERE id = ?", (m['id'],))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error in auto_release_pending_rewards: {e}")
        time.sleep(60)  # Check every 1 minute

Thread(target=auto_release_pending_rewards, daemon=True).start()

# ================= BOT RUNNER =================
if __name__ == "__main__":
    print("🤖 Bot started successfully...")
    bot.infinity_polling()
