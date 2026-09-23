import os
import time
import sqlite3
import telebot
from telebot import apihelper
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)

# ======================================================================
# ⚙️ BOT CONFIGURATION
# ======================================================================
BOT_TOKEN = "8967409217:AAFdraRYBtOejxKZKxA-4c3MLg8ACkZumC0"
ADMIN_ID = "8808647263"
REQUIRED_CHANNEL = "@ClickEarnProOfficial"

DATABASE = "bot_database.db"

TASK_REWARD = 0.0008
REFERRAL_REWARD = 0.0002
MIN_WITHDRAW = 0.05
TASK_WAIT_SECONDS = 10

# Global Proxy / Network settings for cloud platforms
apihelper.CONNECT_TIMEOUT = 15
apihelper.CUSTOM_REQUEST_TIMEOUT = 15

# Force Active Server Tunnel Routing for PythonAnywhere


bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ======================================================================
# 🛠️ 1. DATABASE SETUP & THREAD-SAFE ARCHITECTURE
# ======================================================================
def db():
    # Multi-Thread Lock Fix and String ID Support
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()

    # Users Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0.0,
            lang TEXT DEFAULT 'BN',
            referred_by TEXT DEFAULT '0',
            ref_paid INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0,
            created_at INTEGER
        )
    """)

    # Tasks Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            created_at INTEGER
        )
    """)

    # User Completed Tasks Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_tasks (
            user_id TEXT,
            task_id INTEGER,
            PRIMARY KEY (user_id, task_id)
        )
    """)

    # Withdrawals Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            amount REAL,
            method TEXT,
            account TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at INTEGER
        )
    """)

    # Admin State Control Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_state (
            admin_id TEXT PRIMARY KEY,
            state TEXT,
            target_user TEXT DEFAULT '0'
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ======================================================================
# 🔒 HELPER FUNCTIONS & GUARDS
# ======================================================================
def is_blocked(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT blocked FROM users WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    conn.close()
    return row and row['blocked'] == 1

def check_force_join(user_id):
    if str(user_id) == str(ADMIN_ID):
        return True
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, int(user_id))
        return member.status in ['creator', 'administrator', 'member']
    except Exception:
        return False

def get_admin_state(admin_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT state, target_user FROM admin_state WHERE admin_id = ?", (str(admin_id),))
    row = cur.fetchone()
    conn.close()
    return row if row else {'state': None, 'target_user': '0'}

def set_admin_state(admin_id, state, target_user='0'):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO admin_state (admin_id, state, target_user)
        VALUES (?, ?, ?)
    """, (str(admin_id), state, str(target_user)))
    conn.commit()
    conn.close()

# Temporary memory cache for Task 10s Anti-Spam click lock
task_clicks = {}

# ======================================================================
# 📱 KEYBOARDS & UI BUILDERS
# ======================================================================
def get_user_keyboard(lang='BN'):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == 'BN':
        kb.row(KeyboardButton("💰 ব্যালেন্স"), KeyboardButton("📋 টাস্ক"))
        kb.row(KeyboardButton("🤝 রেফার"), KeyboardButton("📥 উইথড্র"))
        kb.row(KeyboardButton("👤 প্রোফাইল"), KeyboardButton("🌐 Language / ভাষা"))
    else:
        kb.row(KeyboardButton("💰 Balance"), KeyboardButton("📋 Tasks"))
        kb.row(KeyboardButton("🤝 Refer"), KeyboardButton("📥 Withdraw"))
        kb.row(KeyboardButton("👤 Profile"), KeyboardButton("🌐 Language / ভাষা"))
    return kb

def get_admin_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➕ Add Link"), KeyboardButton("📊 View Users"))
    kb.row(KeyboardButton("🚫 Block User"), KeyboardButton("✅ Unblock User"))
    kb.row(KeyboardButton("🎁 Give Bonus"), KeyboardButton("💸 Manage Payouts"))
    return kb

# ======================================================================
# 🚀 USER COMMANDS & HANDLERS
# ======================================================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = str(message.from_user.id)
    if is_blocked(uid):
        return

    # Extract referral parameter
    args = message.text.split()
    ref_by = "0"
    if len(args) > 1 and args[1].isdigit() and args[1] != uid:
        ref_by = args[1]

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
    user = cur.fetchone()

    if not user:
        cur.execute("""
            INSERT INTO users (user_id, username, first_name, referred_by, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (uid, message.from_user.username or "", message.from_user.first_name or "", ref_by, int(time.time())))
        conn.commit()
    conn.close()

    # Language selection step
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("বাংলা 🇧🇩", callback_data="lang_BN"),
        InlineKeyboardButton("English 🇺🇸", callback_data="lang_EN")
    )
    bot.send_message(message.chat.id, "🌐 <b>Select Language / ভাষা নির্বাচন করুন:</b>", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def set_language(call):
    uid = str(call.from_user.id)
    lang = call.data.split("_")[1]

    conn = db()
    conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, uid))
    conn.commit()
    conn.close()

    bot.delete_message(call.message.chat.id, call.message.message_id)
    verify_channel_access(call.message.chat.id, uid, lang)

def verify_channel_access(chat_id, user_id, lang='BN'):
    if not check_force_join(user_id):
        markup = InlineKeyboardMarkup()
        channel_clean = REQUIRED_CHANNEL.replace('@', '')
        markup.add(InlineKeyboardButton("📢 Join Official Group", url=f"https://t.me/{channel_clean}"))
        markup.add(InlineKeyboardButton("✅ Verify Join", callback_data="check_join"))

        msg = "⚠️ <b>বটের মূল মেনু ব্যবহার করতে অবশ্যই আমাদের অফিশিয়াল চ্যানেলে জয়েন করুন!</b>" if lang == 'BN' else "⚠️ <b>You must join our official channel before using the bot!</b>"
        bot.send_message(chat_id, msg, reply_markup=markup)
    else:
        if str(user_id) == str(ADMIN_ID):
            bot.send_message(chat_id, "👑 <b>Welcome Admin Panel!</b>", reply_markup=get_admin_keyboard())
        else:
            msg = "🎉 <b>স্বাগতম! বটের প্রধান মেনু সক্রিয় হয়েছে।</b>" if lang == 'BN' else "🎉 <b>Welcome! The main menu is active.</b>"
            bot.send_message(chat_id, msg, reply_markup=get_user_keyboard(lang))

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def check_join_callback(call):
    uid = str(call.from_user.id)
    conn = db()
    row = conn.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    lang = row['lang'] if row else 'BN'

    if check_force_join(uid):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        if uid == str(ADMIN_ID):
            bot.send_message(call.message.chat.id, "👑 <b>Welcome Admin Panel!</b>", reply_markup=get_admin_keyboard())
        else:
            msg = "🎉 <b>আপনার জয়েন ভেরিফাই হয়েছে!</b>" if lang == 'BN' else "🎉 <b>Your join verification is successful!</b>"
            bot.send_message(call.message.chat.id, msg, reply_markup=get_user_keyboard(lang))
    else:
        alert_msg = "❌ আপনি এখনো চ্যানেলে জয়েন করেননি!" if lang == 'BN' else "❌ You haven't joined the channel yet!"
        bot.answer_callback_query(call.id, alert_msg, show_alert=True)

# Change Language option from menu
@bot.message_handler(func=lambda message: message.text and "Language" in message.text)
def change_language_cmd(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("বাংলা 🇧🇩", callback_data="lang_BN"),
        InlineKeyboardButton("English 🇺🇸", callback_data="lang_EN")
    )
    bot.send_message(message.chat.id, "🌐 <b>Select Language / ভাষা নির্বাচন করুন:</b>", reply_markup=markup)

# ----------------------------------------------------------------------
# 💰 Multi-Tier Wallet Tracker & User Interfaces
# ----------------------------------------------------------------------
@bot.message_handler(func=lambda message: message.text in ["💰 Balance", "💰 ব্যালেন্স"])
def balance_handler(message):
    uid = str(message.from_user.id)
    if is_blocked(uid): return
    if not check_force_join(uid):
        verify_channel_access(message.chat.id, uid)
        return

    conn = db()
    user = conn.execute("SELECT balance, lang FROM users WHERE user_id = ?", (uid,)).fetchone()
    lang = user['lang'] if user else 'BN'
    avail_bal = user['balance'] if user else 0.0

    pending = conn.execute("SELECT SUM(amount) FROM withdrawals WHERE user_id = ? AND status = 'PENDING'", (uid,)).fetchone()[0] or 0.0
    approved = conn.execute("SELECT SUM(amount) FROM withdrawals WHERE user_id = ? AND status = 'APPROVED'", (uid,)).fetchone()[0] or 0.0
    rejected = conn.execute("SELECT SUM(amount) FROM withdrawals WHERE user_id = ? AND status = 'REJECTED'", (uid,)).fetchone()[0] or 0.0
    conn.close()

    if lang == 'BN':
        msg = f"""
💰 <b>আপনার ওয়ালেট সামারি:</b>

💵 <b>কারেন্ট ব্যালেন্স:</b> ${avail_bal:.4f} USD
⏳ <b>পেন্ডিং উইথড্র:</b> ${pending:.4f} USD
✅ <b>মোট এপ্রুভড উইথড্র:</b> ${approved:.4f} USD
❌ <b>মোট রিজেক্টেড/পেনাল্টি:</b> ${rejected:.4f} USD
"""
    else:
        msg = f"""
💰 <b>Your Wallet Summary:</b>

💵 <b>Available Balance:</b> ${avail_bal:.4f} USD
⏳ <b>Pending Withdrawal:</b> ${pending:.4f} USD
✅ <b>Total Approved:</b> ${approved:.4f} USD
❌ <b>Total Rejected/Penalty:</b> ${rejected:.4f} USD
"""
    bot.send_message(message.chat.id, msg)

# ----------------------------------------------------------------------
# 📋 Tasks Handler (Monetag Ads & 10s Timer)
# ----------------------------------------------------------------------
@bot.message_handler(func=lambda message: message.text in ["📋 Tasks", "📋 টাস্ক"])
def task_handler(message):
    uid = str(message.from_user.id)
    if is_blocked(uid): return
    if not check_force_join(uid):
        verify_channel_access(message.chat.id, uid)
        return

    conn = db()
    user = conn.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)).fetchone()
    lang = user['lang'] if user else 'BN'

    task = conn.execute("""
        SELECT * FROM tasks
        WHERE task_id NOT IN (SELECT task_id FROM user_tasks WHERE user_id = ?)
        ORDER BY task_id ASC LIMIT 1
    """, (uid,)).fetchone()
    conn.close()

    if not task:
        msg = "🚫 <b>বর্তমানে কোনো নতুন টাস্ক নেই! পরে চেষ্টা করুন।</b>" if lang == 'BN' else "🚫 <b>No tasks available right now! Try again later.</b>"
        bot.send_message(message.chat.id, msg)
        return

    tid = task['task_id']
    task_clicks[f"{uid}_{tid}"] = time.time()

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 Visit Advertisement", url=task['url']))
    markup.add(InlineKeyboardButton(f"🟢 Verify View ({TASK_WAIT_SECONDS}s)", callback_data=f"vtask_{tid}"))

    msg = f"📋 <b>বিজ্ঞাপনটি দেখুন এবং ১০ সেকেন্ড পর ভেরিফাই বাটনে চাপুন:</b>" if lang == 'BN' else f"📋 <b>Visit advertisement and click verify after 10 seconds:</b>"
    bot.send_message(message.chat.id, msg, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("vtask_"))
def verify_task(call):
    uid = str(call.from_user.id)
    tid = call.data.split("_")[1]
    key = f"{uid}_{tid}"

    conn = db()
    user = conn.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)).fetchone()
    lang = user['lang'] if user else 'BN'

    start_time = task_clicks.get(key, 0)
    elapsed = time.time() - start_time

    if elapsed < TASK_WAIT_SECONDS:
        remaining = int(TASK_WAIT_SECONDS - elapsed)
        alert = f"⚠️ অন্তত {TASK_WAIT_SECONDS} সেকেন্ড অপেক্ষা করুন! আরো {remaining} সেকেন্ড বাকি।" if lang == 'BN' else f"⚠️ Wait at least {TASK_WAIT_SECONDS}s! {remaining}s remaining."
        bot.answer_callback_query(call.id, alert, show_alert=True)
        conn.close()
        return

    # Check duplicate
    if conn.execute("SELECT 1 FROM user_tasks WHERE user_id = ? AND task_id = ?", (uid, tid)).fetchone():
        bot.answer_callback_query(call.id, "⚠️ আপনি ইতিমধ্যেই রিওয়ার্ড পেয়েছেন!", show_alert=True)
        conn.close()
        return

    conn.execute("INSERT INTO user_tasks (user_id, task_id) VALUES (?, ?)", (uid, tid))
    conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (TASK_REWARD, uid))
    conn.commit()
    conn.close()

    if key in task_clicks:
        del task_clicks[key]

    bot.delete_message(call.message.chat.id, call.message.message_id)
    msg = f"✅ <b>টাস্ক সম্পন্ন হয়েছে! ${TASK_REWARD} USD যোগ করা হলো।</b>" if lang == 'BN' else f"✅ <b>Task completed! ${TASK_REWARD} USD added.</b>"
    bot.send_message(call.message.chat.id, msg)

# ----------------------------------------------------------------------
# 🤝 Referral Handler
# ----------------------------------------------------------------------
@bot.message_handler(func=lambda message: message.text in ["🤝 Refer", "🤝 রেফার"])
def refer_handler(message):
    uid = str(message.from_user.id)
    if is_blocked(uid): return
    if not check_force_join(uid):
        verify_channel_access(message.chat.id, uid)
        return

    conn = db()
    user = conn.execute("SELECT lang FROM users WHERE user_id = ?", (uid,)).fetchone()
    lang = user['lang'] if user else 'BN'
    conn.close()

    bot_name = bot.get_me().username
    ref_link = f"https://t.me/{bot_name}?start={uid}"

    if lang == 'BN':
        msg = f"""
🤝 <b>আপনার রেফারেল লিংক:</b>
<code>{ref_link}</code>

ℹ️ <b>রেফারেল নিয়ম:</b>
আপনার রেফার করা মেম্বার ১ম উইথড্র রিকোয়েস্ট পাঠালে আপনার ব্যালেন্সে অটোমেটিক <b>${REFERRAL_REWARD} USD</b> বোনাস যুক্ত হবে।
"""
    else:
        msg = f"""
🤝 <b>Your Referral Link:</b>
<code>{ref_link}</code>

ℹ️ <b>Referral Policy:</b>
When your referred user places their 1st withdrawal request, you will automatically receive <b>${REFERRAL_REWARD} USD</b>.
"""
    bot.send_message(message.chat.id, msg)

# ----------------------------------------------------------------------
# 👤 Profile Handler
# ----------------------------------------------------------------------
@bot.message_handler(func=lambda message: message.text in ["👤 Profile", "👤 প্রোফাইল"])
def profile_handler(message):
    uid = str(message.from_user.id)
    if is_blocked(uid): return

    conn = db()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,)).fetchone()
    conn.close()

    if not user: return
    lang = user['lang']

    if lang == 'BN':
        msg = f"""
👤 <b>আপনার প্রোফাইল:</b>

🆔 <b>ইউজার আইডি:</b> <code>{user['user_id']}</code>
নাম: <b>{user['first_name']}</b>
ব্যালেন্স: <b>${user['balance']:.4f} USD</b>
ভাষা: <b>{'বাংলা' if lang == 'BN' else 'English'}</b>
"""
    else:
        msg = f"""
👤 <b>Your Profile:</b>

🆔 <b>User ID:</b> <code>{user['user_id']}</code>
Name: <b>{user['first_name']}</b>
Balance: <b>${user['balance']:.4f} USD</b>
Language: <b>English</b>
"""
    bot.send_message(message.chat.id, msg)

# ----------------------------------------------------------------------
# 📥 Withdrawal System
# ----------------------------------------------------------------------
@bot.message_handler(func=lambda message: message.text in ["📥 Withdraw", "📥 উইথড্র"])
def withdraw_handler(message):
    uid = str(message.from_user.id)
    if is_blocked(uid): return
    if not check_force_join(uid):
        verify_channel_access(message.chat.id, uid)
        return

    conn = db()
    user = conn.execute("SELECT balance, lang FROM users WHERE user_id = ?", (uid,)).fetchone()
    conn.close()

    bal = user['balance'] if user else 0.0
    lang = user['lang'] if user else 'BN'

    if bal < MIN_WITHDRAW:
        msg = f"⚠️ <b>সর্বনিম্ন উইথড্র ${MIN_WITHDRAW} USD। আপনার পর্যাপ্ত ব্যালেন্স নেই!</b>" if lang == 'BN' else f"⚠️ <b>Minimum withdraw is ${MIN_WITHDRAW} USD. Insufficient balance!</b>"
        bot.send_message(message.chat.id, msg)
        return

    msg_text = "💳 <b>পেমেন্ট মেথড ও নম্বর লিখুন (যেমন: bKash - 017xxxxxxxx):</b>" if lang == 'BN' else "💳 <b>Enter payment method and account (e.g. bKash - 017xxxxxxxx):</b>"
    sent = bot.send_message(message.chat.id, msg_text)
    bot.register_next_step_handler(sent, process_withdrawal, bal, lang)

def process_withdrawal(message, amount, lang):
    uid = str(message.from_user.id)
    account_info = message.text

    conn = db()
    conn.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (uid,))
    conn.execute("""
        INSERT INTO withdrawals (user_id, amount, method, account, status, created_at)
        VALUES (?, ?, 'UserPayout', ?, 'PENDING', ?)
    """, (uid, amount, account_info, int(time.time())))

    # Release referral bonus to upline on 1st withdrawal
    u_data = conn.execute("SELECT referred_by, ref_paid FROM users WHERE user_id = ?", (uid,)).fetchone()
    if u_data and u_data['referred_by'] != '0' and u_data['ref_paid'] == 0:
        ref_id = u_data['referred_by']
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REFERRAL_REWARD, ref_id))
        conn.execute("UPDATE users SET ref_paid = 1 WHERE user_id = ?", (uid,))
        try:
            bot.send_message(ref_id, f"🎉 <b>আপনার রেফার করা মেম্বার ১ম উইথড্র দেওয়ায় ${REFERRAL_REWARD} USD জমা হয়েছে!</b>")
        except Exception:
            pass

    conn.commit()
    conn.close()

    success_msg = "✅ <b>আপনার উইথড্র রিকোয়েস্ট জমা হয়েছে! এডমিন শীঘ্রই প্রসেস করবেন।</b>" if lang == 'BN' else "✅ <b>Your withdrawal request is submitted! Admin will process soon.</b>"
    bot.send_message(message.chat.id, success_msg)

# ======================================================================
# 👑 ADMIN PANEL HANDLERS
# ======================================================================
@bot.message_handler(func=lambda m: str(m.from_user.id) == str(ADMIN_ID) and m.text in ["➕ Add Link", "📊 View Users", "🚫 Block User", "✅ Unblock User", "🎁 Give Bonus", "💸 Manage Payouts"])
def admin_buttons(message):
    uid = str(message.from_user.id)
    text = message.text

    if text == "➕ Add Link":
        set_admin_state(uid, "WAIT_ADD_LINK")
        bot.send_message(message.chat.id, "🔗 <b>স্পনসর/মনিট্যাগ ডিরেক্ট লিংক দিন:</b>")

    elif text == "📊 View Users":
        conn = db()
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        rows = conn.execute("SELECT user_id, username, balance FROM users ORDER BY created_at DESC LIMIT 30").fetchall()
        conn.close()

        msg = f"📊 <b>মোট ইউজার: {total_users}</b>\n\n<b>সর্বশেষ ৩০ ইউজার:</b>\n"
        for r in rows:
            msg += f"• <code>{r['user_id']}</code> | @{r['username']} | ${r['balance']:.4f}\n"
        bot.send_message(message.chat.id, msg)

    elif text == "🚫 Block User":
        set_admin_state(uid, "WAIT_BLOCK_ID")
        bot.send_message(message.chat.id, "🚫 <b>ব্লক করার জন্য ইউজার ID লিখুন:</b>")

    elif text == "✅ Unblock User":
        set_admin_state(uid, "WAIT_UNBLOCK_ID")
        bot.send_message(message.chat.id, "✅ <b>আনব্লক করার জন্য ইউজার ID লিখুন:</b>")

    elif text == "🎁 Give Bonus":
        set_admin_state(uid, "WAIT_BONUS_ID")
        bot.send_message(message.chat.id, "🎁 <b>বোনাস দেয়ার জন্য ইউজার ID লিখুন:</b>")

    elif text == "💸 Manage Payouts":
        process_next_payout(message.chat.id)

@bot.message_handler(func=lambda m: str(m.from_user.id) == str(ADMIN_ID) and get_admin_state(m.from_user.id)['state'] is not None)
def handle_admin_inputs(message):
    uid = str(message.from_user.id)
    state_info = get_admin_state(uid)
    state = state_info['state']

    if state == "WAIT_ADD_LINK":
        link = message.text.strip()
        conn = db()
        try:
            conn.execute("INSERT INTO tasks (url, created_at) VALUES (?, ?)", (link, int(time.time())))
            conn.commit()
            bot.send_message(message.chat.id, "✅ <b>লিংক সফলভাবে যোগ হয়েছে!</b>")
        except Exception:
            bot.send_message(message.chat.id, "❌ লিংকটি আগেই যোগ করা হয়েছিল!")
        finally:
            conn.close()
        set_admin_state(uid, None)

    elif state == "WAIT_BLOCK_ID":
        target = message.text.strip()
        conn = db()
        conn.execute("UPDATE users SET blocked = 1 WHERE user_id = ?", (target,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"🚫 <b>ইউজার {target} ব্লক করা হয়েছে!</b>")
        set_admin_state(uid, None)

    elif state == "WAIT_UNBLOCK_ID":
        target = message.text.strip()
        conn = db()
        conn.execute("UPDATE users SET blocked = 0 WHERE user_id = ?", (target,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ <b>ইউজার {target} আনব্লক করা হয়েছে!</b>")
        set_admin_state(uid, None)

    elif state == "WAIT_BONUS_ID":
        target = message.text.strip()
        set_admin_state(uid, "WAIT_BONUS_AMT", target_user=target)
        bot.send_message(message.chat.id, f"💵 <b>{target}-কে কত ডলার দিতে চান লিখুন:</b>")

    elif state == "WAIT_BONUS_AMT":
        try:
            amt = float(message.text.strip())
            target = state_info['target_user']
            conn = db()
            conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, target))
            conn.commit()
            conn.close()

            bot.send_message(message.chat.id, f"🎉 <b>{target}-কে ${amt} USD দেওয়া হয়েছে!</b>")
            try:
                bot.send_message(target, f"🎁 <b>এডমিন আপনাকে ${amt} USD ফ্রি বোনাস পাঠিয়েছেন!</b>")
            except Exception:
                pass
        except ValueError:
            bot.send_message(message.chat.id, "❌ ভুল সংখ্যা লিখেছেন!")
        set_admin_state(uid, None)

def process_next_payout(chat_id):
    conn = db()
    req = conn.execute("SELECT * FROM withdrawals WHERE status = 'PENDING' ORDER BY id ASC LIMIT 1").fetchone()
    conn.close()

    if not req:
        bot.send_message(chat_id, "🎉 <b>কোনো পেন্ডিং উইথড্র রিকোয়েস্ট নেই!</b>")
        return

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Approve Payout", callback_data=f"pay_app_{req['id']}"),
        InlineKeyboardButton("❌ Reject & Wipe Balance", callback_data=f"pay_rej_{req['id']}")
    )

    msg = f"""
💸 <b>পেন্ডিং পেমেন্ট:</b>

👤 <b>ID:</b> <code>{req['user_id']}</code>
💰 <b>পরিমাণ:</b> ${req['amount']:.4f} USD
💳 <b>মেথড/নম্বর:</b> <code>{req['account']}</code>
"""
    bot.send_message(chat_id, msg, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith(("pay_app_", "pay_rej_")))
def handle_payout_action(call):
    if str(call.from_user.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "🚨 সিকিউরিটি ওয়ার্নিং: আপনার অনুমতি নেই!", show_alert=True)
        return

    action, wid = call.data.split("_")[1], call.data.split("_")[2]

    conn = db()
    req = conn.execute("SELECT * FROM withdrawals WHERE id = ?", (wid,)).fetchone()

    if not req or req['status'] != 'PENDING':
        bot.answer_callback_query(call.id, "⚠️ রিকোয়েস্টটি ইতিমধ্যেই প্রসেস করা হয়েছে!", show_alert=True)
        conn.close()
        return

    target_user = req['user_id']

    if action == "app":
        conn.execute("UPDATE withdrawals SET status = 'APPROVED' WHERE id = ?", (wid,))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ এপ্রুভড!")
        try:
            bot.send_message(target_user, f"🎉 <b>আপনার ${req['amount']:.4f} USD উইথড্র এপ্রুভ হয়েছে!</b>")
        except Exception:
            pass

    elif action == "rej":
        conn.execute("UPDATE withdrawals SET status = 'REJECTED' WHERE id = ?", (wid,))
        conn.execute("UPDATE users SET balance = 0.0 WHERE user_id = ?", (target_user,))
        conn.commit()
        bot.answer_callback_query(call.id, "❌ রিজেক্ট ও ব্যালেন্স জিরো করা হয়েছে!")
        try:
            bot.send_message(target_user, f"⚠️ <b>আপনার ${req['amount']:.4f} USD পেমেন্ট বাতিল করা হয়েছে এবং অ্যাকাউন্ট ব্যালেন্স পেনাল্টি হিসেবে $0 করা হয়েছে!</b>")
        except Exception:
            pass

    conn.close()
    bot.delete_message(call.message.chat.id, call.message.message_id)
    process_next_payout(call.message.chat.id)

# ======================================================================
# 💻 4. DEPLOYMENT & FORCE POLLING DRIVER
# ======================================================================
if __name__ == "__main__":
    print("🤖 Bot is starting with Infinity Polling...")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Error: {e}. Retrying in 3 seconds...")
            time.sleep(3)
