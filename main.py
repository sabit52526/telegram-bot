import os
import time
import sqlite3
import threading
from datetime import datetime, timedelta
from flask import Flask
import telebot
from telebot import types

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8808647263")) # আপনার এডমিন আইডি
OFFICIAL_CHANNEL = os.environ.get("OFFICIAL_CHANNEL", "@ClickEarnOfficial") # আপনার অফিশিয়াল চ্যানেলের ইউজারনেম

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- FLASK KEEP-ALIVE SERVER ---
@app.route('/')
def home():
    return "ClickEarn Pro Bot is Live & Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- DATABASE SETUP ---
DB_FILE = "bot_data.db"

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            main_balance REAL DEFAULT 0.0,
            pending_balance REAL DEFAULT 0.0,
            spam_count INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tasks Table (Created by Admin)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_username TEXT,
            channel_name TEXT,
            reward REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # User Tasks Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            channel_username TEXT,
            reward REAL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            unlock_at TIMESTAMP
        )
    ''')
    
    # Withdrawals Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            account_number TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def get_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(user_id, username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()
    conn.close()

def is_blocked(user_id):
    user = get_user(user_id)
    return user['is_blocked'] == 1 if user else False

def is_in_official_channel(user_id):
    if not OFFICIAL_CHANNEL or OFFICIAL_CHANNEL == "@":
        return True
    try:
        member = bot.get_chat_member(OFFICIAL_CHANNEL, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception:
        return True

def send_must_join_msg(chat_id):
    markup = types.InlineKeyboardMarkup()
    ch_clean = OFFICIAL_CHANNEL.replace('@', '')
    btn_join = types.InlineKeyboardButton("📢 Join Official Channel", url=f"https://t.me/{ch_clean}")
    btn_verify = types.InlineKeyboardButton("🔄 Verify Join", callback_data="check_official_join")
    markup.add(btn_join)
    markup.add(btn_verify)
    bot.send_message(
        chat_id,
        "⚠️ **আপনি আমাদের অফিশিয়াল চ্যানেলে যুক্ত নেই!**\n\nবোটটি ব্যবহার করতে প্রথমে অফিশিয়াল চ্যানেলে জয়েন করুন এবং 'Verify Join' বাটনে চাপ দিন।",
        parse_mode="Markdown",
        reply_markup=markup
    )

# --- BACKGROUND THREAD (10-Day Unlock & Auto Leave Detection) ---
def background_task_monitor():
    while True:
        try:
            time.sleep(30)
            conn = get_db()
            cursor = conn.cursor()
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("SELECT id, user_id, channel_username, reward, unlock_at FROM user_tasks WHERE status = 'pending'")
            pending_tasks = cursor.fetchall()
            
            for task in pending_tasks:
                task_id = task['id']
                user_id = task['user_id']
                ch_name = task['channel_username']
                reward = task['reward']
                unlock_at = task['unlock_at']
                
                is_member = True
                try:
                    member = bot.get_chat_member(ch_name, user_id)
                    if member.status in ['left', 'kicked']:
                        is_member = False
                except Exception:
                    pass
                
                if not is_member:
                    # ইউজার লিভ নিলে পেন্ডিং কাটা হবে এবং স্প্যাম কাউন্ট ১ বাড়বে
                    cursor.execute("UPDATE user_tasks SET status = 'cancelled' WHERE id = ?", (task_id,))
                    cursor.execute("UPDATE users SET pending_balance = MAX(0, pending_balance - ?), spam_count = spam_count + 1 WHERE user_id = ?", (reward, user_id))
                    conn.commit()
                    
                    markup = types.InlineKeyboardMarkup()
                    btn_reverify = types.InlineKeyboardButton("🔄 Re-join & Verify", callback_data=f"reverify_task_{task_id}")
                    markup.add(btn_reverify)
                    
                    try:
                        bot.send_message(
                            user_id,
                            f"❌ **সতর্কবার্তা!**\n\nআপনি `{ch_name}` থেকে লিভ নিয়েছেন! আপনার **${reward:.4f}** পেন্ডিং বোনাস কেটে নেওয়া হয়েছে।\n\nআবার জয়েন করে নিচের 'Re-join & Verify' বাটনে চাপ দিন।",
                            parse_mode="Markdown",
                            reply_markup=markup
                        )
                    except Exception:
                        pass
                else:
                    # ১০ দিন পূর্ণ হলে পেন্ডিং থেকে মেইন ব্যালেন্সে ট্রান্সফার
                    if unlock_at and now_str >= unlock_at:
                        cursor.execute("UPDATE user_tasks SET status = 'completed' WHERE id = ?", (task_id,))
                        cursor.execute("UPDATE users SET pending_balance = MAX(0, pending_balance - ?), main_balance = main_balance + ? WHERE user_id = ?", (reward, reward, user_id))
                        conn.commit()
                        
                        try:
                            bot.send_message(
                                user_id,
                                f"🎉 **অভিনন্দন!**\n\nআপনার `{ch_name}` টাস্কের ১০ দিন পূরণ হয়েছে! **${reward:.4f}** মেইন ব্যালেন্সে যোগ করা হয়েছে।",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass

            conn.close()
        except Exception:
            time.sleep(10)

threading.Thread(target=background_task_monitor, daemon=True).start()

# --- MAIN KEYBOARD ---
def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('📋 Tasks', '👤 Profile', '💰 Balance', '📤 Withdraw')
    if user_id == ADMIN_ID:
        markup.add('⚙️ Admin Panel')
    return markup

# --- COMMAND HANDLERS ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or "User"
    add_user(user_id, username)
    
    if is_blocked(user_id):
        bot.reply_to(message, "❌ আপনার অ্যাকাউন্টটি স্প্যামিংয়ের কারণে ব্লক করা হয়েছে!")
        return

    if not is_in_official_channel(user_id):
        send_must_join_msg(message.chat.id)
        return

    bot.send_message(
        message.chat.id,
        "👋 **Welcome to ClickEarn Pro!**\n\nEarn money by completing simple tasks.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user_id)
    )

# --- CALLBACK HANDLERS ---
@bot.callback_query_handler(func=lambda call: call.data == "check_official_join")
def verify_official_join(call):
    user_id = call.from_user.id
    if is_in_official_channel(user_id):
        bot.answer_callback_query(call.id, "✅ অফিশিয়াল চ্যানেলে জয়েন নিশ্চিত হয়েছে!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        start_cmd(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনও অফিশিয়াল চ্যানেলে জয়েন করেননি!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reverify_task_"))
def reverify_task(call):
    user_id = call.from_user.id
    task_id = int(call.data.split("_")[2])
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_username, reward, status FROM user_tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    task = cursor.fetchone()
    
    if not task:
        bot.answer_callback_query(call.id, "টাস্কটি পাওয়া যায়নি!", show_alert=True)
        conn.close()
        return
        
    ch_name = task['channel_username']
    reward = task['reward']
    status = task['status']
    
    try:
        member = bot.get_chat_member(ch_name, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            if status == 'cancelled':
                unlock_time = datetime.now() + timedelta(days=10)
                unlock_str = unlock_time.strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute("UPDATE user_tasks SET status = 'pending', unlock_at = ? WHERE id = ?", (unlock_str, task_id))
                cursor.execute("UPDATE users SET pending_balance = pending_balance + ? WHERE user_id = ?", (reward, user_id))
                conn.commit()
                
                bot.edit_message_text(
                    f"✅ **সফলভাবে পুনরায় জয়েন করেছেন!**\n\nআপনার **${reward:.4f}** বোনাস আবার পেন্ডিং ব্যালেন্সে যোগ করা হলো।\n\n⚠️ **সতর্কতা:** এর পরে এরকম করলে বা বারবার লিভ নিলে আপনার অ্যাকাউন্ট চিরতরে ব্লক করা হতে পারে!",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="Markdown"
                )
            else:
                bot.answer_callback_query(call.id, "এই টাস্কটি ইতিমধ্যেই অ্যাক্টিভ আছে।", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ আপনি এখনও চ্যানেলে জয়েন করেননি! আগে জয়েন করুন।", show_alert=True)
    except Exception:
        bot.answer_callback_query(call.id, "যান্ত্রিক ত্রুটি! চ্যানেলে ঠিকমতো জয়েন করেছেন কি না চেক করুন।", show_alert=True)
    conn.close()

# --- MENU BUTTONS ---
@bot.message_handler(func=lambda m: True)
def handle_menu_messages(message):
    user_id = message.from_user.id
    text = message.text
    
    if is_blocked(user_id):
        bot.reply_to(message, "❌ আপনার অ্যাকাউন্ট ব্লকড!")
        return

    if not is_in_official_channel(user_id):
        send_must_join_msg(message.chat.id)
        return

    if text == '💰 Balance':
        user = get_user(user_id)
        main_bal = user['main_balance'] if user else 0.0
        pend_bal = user['pending_balance'] if user else 0.0
        bot.send_message(
            message.chat.id,
            f"💼 **Your Wallet Details:**\n\n**Main Balance:** ${main_bal:.4f}\n**Pending Balance:** ${pend_bal:.4f}\n\n_(Pending task rewards unlock after 10 days)_",
            parse_mode="Markdown"
        )
        
    elif text == '👤 Profile':
        user = get_user(user_id)
        username = user['username'] if user else "N/A"
        joined = user['joined_date'] if user else "N/A"
        bot.send_message(
            message.chat.id,
            f"👤 **Your Profile:**\n\n🆔 **User ID:** `{user_id}`\n👤 **Username:** @{username}\n📅 **Joined:** {joined}\n🌐 **Language:** English",
            parse_mode="Markdown"
        )

    elif text == '📋 Tasks':
        show_available_tasks(message)

    elif text == '📤 Withdraw':
        start_withdrawal_process(message)

    elif text == '⚙️ Admin Panel' and user_id == ADMIN_ID:
        show_admin_panel(message.chat.id)

# --- TASK LOGIC ---
def show_available_tasks(message):
    user_id = message.from_user.id
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM tasks WHERE id NOT IN (
            SELECT task_id FROM user_tasks WHERE user_id = ? AND status IN ('pending', 'completed')
        )
    ''', (user_id,))
    available_tasks = cursor.fetchall()
    conn.close()
    
    if not available_tasks:
        bot.send_message(message.chat.id, "❌ No tasks available right now! Check back later.")
        return
        
    msg = "📋 **Available Tasks:**\n\nJoin the channels/groups below to earn rewards:\n"
    markup = types.InlineKeyboardMarkup()
    
    for task in available_tasks:
        t_id = task['id']
        c_name = task['channel_name'] or task['channel_username']
        reward = task['reward']
        markup.add(types.InlineKeyboardButton(f"👉 Join {c_name} (+${reward:.4f})", callback_data=f"do_task_{t_id}"))
        
    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("do_task_"))
def handle_do_task(call):
    task_id = int(call.data.split("_")[2])
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        bot.answer_callback_query(call.id, "টাস্কটি পাওয়া যায়নি!", show_alert=True)
        conn.close()
        return
        
    ch_user = task['channel_username']
    ch_name = task['channel_name'] or ch_user
    reward = task['reward']
    
    markup = types.InlineKeyboardMarkup()
    ch_clean = ch_user.replace('@', '')
    markup.add(types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{ch_clean}"))
    markup.add(types.InlineKeyboardButton("✅ Verify Task", callback_data=f"verify_task_{task_id}"))
    
    bot.send_message(
        call.message.chat.id,
        f"📌 **Task Instructions:**\n\n1. Click 'Join Channel' and join `{ch_name}`.\n2. Do NOT leave for at least 10 days.\n3. Click 'Verify Task' below.\n\n💰 **Reward:** ${reward:.4f} (Pending for 10 days)",
        parse_mode="Markdown",
        reply_markup=markup
    )
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_task_"))
def handle_verify_task(call):
    user_id = call.from_user.id
    task_id = int(call.data.split("_")[2])
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    
    if not task:
        bot.answer_callback_query(call.id, "টাস্কটি পাওয়া যায়নি!", show_alert=True)
        conn.close()
        return
        
    ch_user = task['channel_username']
    reward = task['reward']
    
    try:
        member = bot.get_chat_member(ch_user, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            unlock_time = datetime.now() + timedelta(days=10)
            unlock_str = unlock_time.strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                INSERT INTO user_tasks (user_id, task_id, channel_username, reward, status, unlock_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            ''', (user_id, task_id, ch_user, reward, unlock_str))
            
            cursor.execute("UPDATE users SET pending_balance = pending_balance + ? WHERE user_id = ?", (reward, user_id))
            conn.commit()
            
            bot.edit_message_text(
                f"✅ **Task Completed Successfully!**\n\n**${reward:.4f}** আপনার পেন্ডিং ব্যালেন্সে যোগ হয়েছে। ১০ দিন পর এটি মেইন ব্যালেন্সে আনলক হবে।",
                call.message.chat.id,
                call.message.message_id,
                parse_mode="Markdown"
            )
        else:
            bot.answer_callback_query(call.id, "❌ আপনি এখনও চ্যানেলে জয়েন করেননি! আগে জয়েন করুন।", show_alert=True)
    except Exception:
        bot.answer_callback_query(call.id, "❌ চ্যানেল ভেরিফিকেশন ব্যর্থ হয়েছে। বোটটি চ্যানেলে সঠিক ইউজারনেম দিয়ে খুঁজে পাওয়া যাচ্ছে কি না চেক করুন।", show_alert=True)
    conn.close()

# --- WITHDRAWAL LOGIC ---
def start_withdrawal_process(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    main_bal = user['main_balance'] if user else 0.0
    
    if main_bal < 1.0:
        bot.send_message(message.chat.id, f"❌ **Minimum withdrawal is $1.0000**\n\nআপনার মেইন ব্যালেন্স: **${main_bal:.4f}**", parse_mode="Markdown")
        return
        
    msg = bot.send_message(message.chat.id, "💳 পেমেন্ট মেথড এবং অ্যাকাউন্ট নম্বর লিখে রিপ্লাই দিন (যেমন: `bKash 01700000000`):")
    bot.register_next_step_handler(msg, process_withdrawal, main_bal)

def process_withdrawal(message, amount):
    user_id = message.from_user.id
    details = message.text
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET main_balance = main_balance - ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("INSERT INTO withdrawals (user_id, amount, method, account_number) VALUES (?, ?, 'Wallet', ?)", (user_id, amount, details))
    conn.commit()
    conn.close()
    
    bot.send_message(message.chat.id, "✅ **Withdrawal Request Submitted!**")
    try:
        bot.send_message(ADMIN_ID, f"🔔 **New Withdrawal Request!**\n\nUser ID: `{user_id}`\nAmount: ${amount:.4f}\nDetails: {details}", parse_mode="Markdown")
    except Exception:
        pass

# --- ADMIN PANEL LOGIC ---
def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_spam = types.InlineKeyboardButton("🚨 Spam Users List", callback_data="admin_spam_users")
    btn_add_task = types.InlineKeyboardButton("➕ Add New Task", callback_data="admin_add_task")
    btn_withdraws = types.InlineKeyboardButton("💳 Withdraw Requests", callback_data="admin_withdraw_requests")
    btn_broadcast = types.InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")
    btn_stats = types.InlineKeyboardButton("📊 Bot Statistics", callback_data="admin_stats")
    
    markup.add(btn_spam, btn_add_task)
    markup.add(btn_withdraws, btn_broadcast)
    markup.add(btn_stats)
    
    bot.send_message(chat_id, "⚙️ **Welcome to Admin Control Panel**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return
        
    data = call.data
    
    if data == "admin_spam_users":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, spam_count, is_blocked FROM users WHERE spam_count > 0 ORDER BY spam_count DESC LIMIT 15")
        spammers = cursor.fetchall()
        conn.close()
        
        if not spammers:
            bot.send_message(call.message.chat.id, "✅ কোনো স্প্যাম ইউজার পাওয়া যায়নি।")
            return
            
        msg = "🚨 **Spam Users List:**\n\n"
        markup = types.InlineKeyboardMarkup()
        for u in spammers:
            uid = u['user_id']
            uname = u['username'] or "NoName"
            s_count = u['spam_count']
            blocked = u['is_blocked']
            status = "🔴 BLOCKED" if blocked else "🟢 ACTIVE"
            msg += f"👤 @{uname} (ID: `{uid}`)\n└ Spam Count: {s_count} | Status: {status}\n\n"
            if not blocked:
                markup.add(types.InlineKeyboardButton(f"🚫 Block {uname}", callback_data=f"block_user_{uid}"))
            else:
                markup.add(types.InlineKeyboardButton(f"🟢 Unblock {uname}", callback_data=f"unblock_user_{uid}"))
                
        bot.send_message(call.message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

    elif data == "admin_add_task":
        msg = bot.send_message(call.message.chat.id, "➕ চ্যানেল ইউজারনেম এবং রিওয়ার্ড এভাবে পাঠান:\n`@channelusername 0.05`")
        bot.register_next_step_handler(msg, process_add_task)

    elif data == "admin_withdraw_requests":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM withdrawals WHERE status = 'pending' ORDER BY id DESC LIMIT 10")
        w_reqs = cursor.fetchall()
        conn.close()
        
        if not w_reqs:
            bot.send_message(call.message.chat.id, "✅ কোনো পেন্ডিং উইথড্র রিকোয়েস্ট নেই।")
            return
            
        for w in w_reqs:
            w_id = w['id']
            uid = w['user_id']
            amt = w['amount']
            acc = w['account_number']
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"app_w_{w_id}"),
                types.InlineKeyboardButton("❌ Reject", callback_data=f"rej_w_{w_id}")
            )
            bot.send_message(call.message.chat.id, f"💳 **Withdraw ID #{w_id}**\nUser: `{uid}`\nAmount: ${amt:.4f}\nDetails: {acc}", parse_mode="Markdown", reply_markup=markup)

    elif data == "admin_stats":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_users = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as total FROM user_tasks WHERE status = 'completed'")
        total_tasks = cursor.fetchone()['total']
        conn.close()
        
        bot.send_message(call.message.chat.id, f"📊 **Bot Statistics:**\n\n👥 **Total Users:** {total_users}\n✅ **Completed Tasks:** {total_tasks}")

    elif data == "admin_broadcast":
        msg = bot.send_message(call.message.chat.id, "📢 মেসেজটি এখানে লিখুন:")
        bot.register_next_step_handler(msg, process_broadcast)

def process_add_task(message):
    try:
        parts = message.text.split()
        ch_username = parts[0]
        reward = float(parts[1])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks (channel_username, channel_name, reward) VALUES (?, ?, ?)", (ch_username, ch_username, reward))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"✅ Task added!\nChannel: {ch_username}\nReward: ${reward:.4f}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Format error! Example: `@mychannel 0.05`\nError: {e}")

def process_broadcast(message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    count = 0
    for u in users:
        try:
            bot.send_message(u['user_id'], message.text)
            count += 1
            time.sleep(0.05)
        except Exception:
            pass
            
    bot.send_message(message.chat.id, f"✅ Broadcast sent to {count} users!")

# BLOCK / UNBLOCK
@bot.callback_query_handler(func=lambda call: call.data.startswith("block_user_") or call.data.startswith("unblock_user_"))
def handle_block_unblock(call):
    if call.from_user.id != ADMIN_ID:
        return
        
    uid = int(call.data.split("_")[2])
    is_blk = 1 if "block_user" in call.data else 0
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?", (is_blk, uid))
    conn.commit()
    conn.close()
    
    status_txt = "blocked" if is_blk == 1 else "unblocked"
    bot.answer_callback_query(call.id, f"User {uid} {status_txt}!", show_alert=True)
    bot.send_message(call.message.chat.id, f"👤 User `{uid}` is now **{status_txt.upper()}**.", parse_mode="Markdown")

# WITHDRAW ACTIONS
@bot.callback_query_handler(func=lambda call: call.data.startswith("app_w_") or call.data.startswith("rej_w_"))
def handle_withdraw_action(call):
    if call.from_user.id != ADMIN_ID:
        return
        
    w_id = int(call.data.split("_")[2])
    is_approve = call.data.startswith("app_w_")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM withdrawals WHERE id = ?", (w_id,))
    w = cursor.fetchone()
    
    if not w:
        bot.answer_callback_query(call.id, "Request-ti paowa jayni!", show_alert=True)
        conn.close()
        return
        
    uid = w['user_id']
    amt = w['amount']
    
    if is_approve:
        cursor.execute("UPDATE withdrawals SET status = 'approved' WHERE id = ?", (w_id,))
        bot.send_message(uid, f"🎉 **Withdrawal Approved!**\n\nআপনার ${amt:.4f} পেমেন্ট কমপ্লিট করা হয়েছে।")
    else:
        cursor.execute("UPDATE withdrawals SET status = 'rejected' WHERE id = ?", (w_id,))
        cursor.execute("UPDATE users SET main_balance = main_balance + ? WHERE user_id = ?", (amt, uid))
        bot.send_message(uid, f"❌ **Withdrawal Rejected!**\n\nআপনার ${amt:.4f} মেইন ব্যালেন্সে ফেরত দেওয়া হয়েছে।")
        
    conn.commit()
    conn.close()
    bot.edit_message_text(f"Withdrawal #{w_id} updated: {'APPROVED' if is_approve else 'REJECTED'}", call.message.chat.id, call.message.message_id)

# --- START BOT & FLASK SERVER ---
threading.Thread(target=run_flask, daemon=True).start()

if __name__ == '__main__':
    bot.infinity_polling()
