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
SUPPORT_URL = "https://t.me/+8801720616501"
DOLLAR_RATE = 120.0
WITHDRAW_FEE = 0.02
REFERRAL_REWARD_ON_WITHDRAW = 0.01

# --- CONVERSATION STATES ---
AWAITING_PAYMENT_ADDRESS, AWAITING_TASK_INPUT, AWAITING_BLOCK_ID = range(3)

# --- MULTI-LANGUAGE DICTIONARY (6 Languages) ---
LANG_TEXTS = {
    'bn': {
        'welcome': "👋 'ClickEarn Pro'-এ স্বাগতম!\nকাজ সম্পন্ন করে প্রতিদিন ইনকাম করুন।\n\n⚠️ অবশই আমাদের অফিসিয়াল চ্যানেলে জয়েন থাকতে হবে।",
        'tasks': "📋 **উপলব্ধ টাস্কসমূহ:**",
        'balance': "💰 **ব্যালেন্স বিবরণী:**\n\nবর্তমান ব্যালেন্স: `${balance:.4f}` USD (~{bdt:.2f} BDT)",
        'withdraw_select': "💳 **উইথড্র অপশন:**\n• Binance (Min $0.20)\n• bKash (Min $1.00 - Rate: 120 BDT/$)",
        'referral': "👥 **রেফারাল প্রোগ্রাম:**\nআপনার রেফার করা ইউজার ১ম বার উইথড্র দিলে পাবেন `${reward}` বোনাস!\n\n🔗 লিংক:\n`https://t.me/{bot_username}?start={user_id}`",
        'lang_select': "🌐 **ভাষা নির্বাচন করুন:**",
        'must_join': "⚠️ বটের কাজ শুরু করতে আমাদের অফিসিয়াল চ্যানেলে জয়েন করুন!",
        'joined_btn': "✅ Check / Verify",
        'join_channel_btn': "📢 Join Channel",
        'cancel_btn': "❌ Cancel",
        'support_btn': "📞 Support (01720616501)",
        'cancelled': "🏠 মূল মেনুতে ফিরে আসা হয়েছে।",
        'no_tasks': "❌ কোনো নতুন টাস্ক নেই।",
        'task_claimed': "🎉 অভিনন্দন! আপনি `${reward}` রিওয়ার্ড পেয়েছেন।",
        'task_not_joined': "❌ আপনি এই চ্যানেলে জয়েন করেননি!",
        'penalty_alert': "🚨 **উইথড্র বাতিল!**\n\nআপনি পূর্বে কাজ করা চ্যানেল থেকে লিভ নিয়েছেন:\n• চ্যানেল: {channel}\n• কাটা ব্যালেন্স: `${reward}`",
        'min_withdraw_err': "❌ অপর্যাপ্ত ব্যালেন্স! সর্বনিম্ন উইথড্র: `${min_amt}` (ফি: `${fee}`)",
        'enter_address': "📝 আপনার {method} একাউন্ট নাম্বার/এড্রেস দিন:",
        'withdraw_success': "✅ উইথড্র রিকোয়েস্ট সফল!\nপরিমাণ: `${net:.4f}` | ফি: `${fee}`\nঅ্যাকাউন্ট: `{address}`",
        'blocked_msg': "🚫 আপনার একাউন্ট স্থগিত করা হয়েছে। সাপোর্টে যোগাযোগ করুন।"
    },
    'en': {
        'welcome': "👋 Welcome to 'ClickEarn Pro'!\nComplete tasks daily to earn.",
        'tasks': "📋 **Available Tasks:**",
        'balance': "💰 **Your Balance:**\n\nBalance: `${balance:.4f}` USD (~{bdt:.2f} BDT)",
        'withdraw_select': "💳 **Withdraw Options:**\n• Binance (Min $0.20)\n• bKash (Min $1.00 - Rate: 120 BDT/$)",
        'referral': "👥 **Referral Program:**\nEarn `${reward}` when your referral makes their first withdrawal!\n\n🔗 Link:\n`https://t.me/{bot_username}?start={user_id}`",
        'lang_select': "🌐 **Select Language:**",
        'must_join': "⚠️ Please join our Official Channel to use the bot!",
        'joined_btn': "✅ Check / Verify",
        'join_channel_btn': "📢 Join Channel",
        'cancel_btn': "❌ Cancel",
        'support_btn': "📞 Support (01720616501)",
        'cancelled': "🏠 Returned to main menu.",
        'no_tasks': "❌ No tasks available.",
        'task_claimed': "🎉 Congratulations! You received `${reward}`.",
        'task_not_joined': "❌ You have not joined this channel yet!",
        'penalty_alert': "🚨 **Withdrawal Rejected!**\n\nYou left previously joined channel:\n• Channel: {channel}\n• Penalty: `${reward}`",
        'min_withdraw_err': "❌ Insufficient balance! Minimum: `${min_amt}` (Fee: `${fee}`)",
        'enter_address': "📝 Enter your {method} account details:",
        'withdraw_success': "✅ Withdrawal successful!\nNet: `${net:.4f}` | Fee: `${fee}`\nAccount: `{address}`",
        'blocked_msg': "🚫 Your account is suspended. Contact support."
    },
    'es': {
        'welcome': "👋 ¡Bienvenido a 'ClickEarn Pro'!",
        'tasks': "📋 **Tareas disponibles:**",
        'balance': "💰 **Tu saldo:** `${balance:.4f}` USD",
        'withdraw_select': "💳 **Opciones de retiro:**",
        'referral': "👥 **Programa de referidos:**",
        'lang_select': "🌐 **Selecciona idioma:**",
        'must_join': "⚠️ ¡Únete al canal oficial!",
        'joined_btn': "✅ Verificar",
        'join_channel_btn': "📢 Unirse al canal",
        'cancel_btn': "❌ Cancelar",
        'support_btn': "📞 Soporte",
        'cancelled': "🏠 Menú principal.",
        'no_tasks': "❌ No hay tareas.",
        'task_claimed': "🎉 ¡Recibiste `${reward}`!",
        'task_not_joined': "❌ ¡Aún no te has unido!",
        'penalty_alert': "🚨 **Retiro rechazado por dejar canal.**",
        'min_withdraw_err': "❌ Saldo insuficiente.",
        'enter_address': "📝 Ingrese su cuenta:",
        'withdraw_success': "✅ Solicitud enviada.",
        'blocked_msg': "🚫 Cuenta suspendida."
    },
    'pt': {
        'welcome': "👋 Bem-vindo ao 'ClickEarn Pro'!",
        'tasks': "📋 **Tarefas disponíveis:**",
        'balance': "💰 **Seu saldo:** `${balance:.4f}` USD",
        'withdraw_select': "💳 **Opções de saque:**",
        'referral': "👥 **Programa de indicação:**",
        'lang_select': "🌐 **Selecione o idioma:**",
        'must_join': "⚠️ Entre no canal oficial!",
        'joined_btn': "✅ Verificar",
        'join_channel_btn': "📢 Entrar no Canal",
        'cancel_btn': "❌ Cancelar",
        'support_btn': "📞 Suporte",
        'cancelled': "🏠 Menu principal.",
        'no_tasks': "❌ Sem tarefas.",
        'task_claimed': "🎉 Você recebeu `${reward}`!",
        'task_not_joined': "❌ Você ainda não entrou!",
        'penalty_alert': "🚨 **Saque rejeitado.**",
        'min_withdraw_err': "❌ Saldo insuficiente.",
        'enter_address': "📝 Digite sua conta:",
        'withdraw_success': "✅ Pedido enviado.",
        'blocked_msg': "🚫 Conta suspensa."
    },
    'hi': {
        'welcome': "👋 'ClickEarn Pro' में आपका स्वागत है!",
        'tasks': "📋 **उपलब्ध कार्य:**",
        'balance': "💰 **आपका बैलेंस:** `${balance:.4f}` USD",
        'withdraw_select': "💳 **निकासी विकल्प:**",
        'referral': "👥 **रेफरल प्रोग्राम:**",
        'lang_select': "🌐 **भाषा चुनें:**",
        'must_join': "⚠️ कृपया हमारे आधिकारिक चैनल में शामिल हों!",
        'joined_btn': "✅ जांचें / सत्यापित करें",
        'join_channel_btn': "📢 चैनल से जुड़ें",
        'cancel_btn': "❌ रद्द करें",
        'support_btn': "📞 सहायता",
        'cancelled': "🏠 मुख्य मेनू।",
        'no_tasks': "❌ कोई कार्य उपलब्ध नहीं है।",
        'task_claimed': "🎉 बधाई! आपको `${reward}` मिले।",
        'task_not_joined': "❌ आप अभी तक इस चैनल में शामिल नहीं हुए हैं!",
        'penalty_alert': "🚨 **निकासी अस्वीकृत!**",
        'min_withdraw_err': "❌ अपर्याप्त बैलेंस!",
        'enter_address': "📝 अपना खाता विवरण दर्ज करें:",
        'withdraw_success': "✅ निकासी अनुरोध सफल!",
        'blocked_msg': "🚫 आपका खाता निलंबित कर दिया गया है।"
    },
    'ur': {
        'welcome': "👋 'ClickEarn Pro' میں خوش آمدید!",
        'tasks': "📋 **دستیاب کام:**",
        'balance': "💰 **آپ کا بیلنس:** `${balance:.4f}` USD",
        'withdraw_select': "💳 **نکالنے کے اختیارات:**",
        'referral': "👥 **ریفرل پروگرام:**",
        'lang_select': "🌐 **زبان منتخب کریں:**",
        'must_join': "⚠️ ہمارے آفیشل چینل میں شامل ہوں!",
        'joined_btn': "✅ تصدیق کریں",
        'join_channel_btn': "📢 چینل میں شامل ہوں",
        'cancel_btn': "❌ منسوخ کریں",
        'support_btn': "📞 سپورٹ",
        'cancelled': "🏠 مین مینو۔",
        'no_tasks': "❌ کوئی کام نہیں ہے۔",
        'task_claimed': "🎉 مبارک ہو! آپ کو `${reward}` ملا۔",
        'task_not_joined': "❌ آپ اس چینل میں شامل نہیں ہوئے!",
        'penalty_alert': "🚨 **رقم نکالنا مسترد!**",
        'min_withdraw_err': "❌ نا کافی بیلنس!",
        'enter_address': "📝 اپنے اکاؤنٹ کی تفصیلات درج کریں:",
        'withdraw_success': "✅ درخواست کامیابی کے ساتھ ارسال کر دی گئی۔",
        'blocked_msg': "🚫 آپ کا اکاؤنٹ معطل کر دیا گیا ہے۔"
    }
}

# --- DATABASE SETUP ---
DB_FILE = "earning_bot.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0,
        referred_by INTEGER DEFAULT 0, lang TEXT DEFAULT 'bn', is_blocked INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, link TEXT, reward REAL, channel_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS completed_tasks (
        user_id INTEGER, task_id INTEGER, PRIMARY KEY (user_id, task_id))''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

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
    except Exception:
        return False

# --- KEYBOARDS (SEPARATED USER & ADMIN) ---
def build_main_keyboard(user_id: int):
    # ADMIN PANEL KEYBOARD
    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("➕ Add Task", callback_data="admin_add_task"), InlineKeyboardButton("📊 View Users", callback_data="admin_view_users")],
            [InlineKeyboardButton("⚠️ Suspicious Users", callback_data="admin_suspicious"), InlineKeyboardButton("🚫 Block User", callback_data="admin_block_user")],
            [InlineKeyboardButton("🟢 Unblock User", callback_data="admin_unblock_user"), InlineKeyboardButton("📞 Support", url=SUPPORT_URL)],
            [InlineKeyboardButton(get_text(user_id, 'cancel_btn'), callback_data="nav_cancel")]
        ]
        return InlineKeyboardMarkup(keyboard)

    # REGULAR USER PANEL KEYBOARD
    keyboard = [
        [InlineKeyboardButton("📋 Tasks", callback_data="nav_tasks"), InlineKeyboardButton("💰 My Balance", callback_data="nav_balance")],
        [InlineKeyboardButton("💳 Withdraw", callback_data="nav_withdraw"), InlineKeyboardButton("👥 Referral", callback_data="nav_referral")],
        [InlineKeyboardButton("🌐 Language", callback_data="nav_lang"), InlineKeyboardButton("📞 Support", url=SUPPORT_URL)],
        [InlineKeyboardButton(get_text(user_id, 'cancel_btn'), callback_data="nav_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- SILENT BLOCK INTERCEPTOR & JOIN CHECK ---
async def check_user_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    # 1. SILENT BLOCK SYSTEM (Zero Response except Support Button)
    if is_user_blocked(user.id):
        if update.callback_query:
            await update.callback_query.answer()
        return False

    # Admin bypass
    if user.id == ADMIN_ID:
        return True

    # 2. MANDATORY CHANNEL JOIN CHECK
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

# --- START COMMAND ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user.id,))
    if not c.fetchone():
        ref_id = int(context.args[0]) if context.args and context.args[0].isdigit() and int(context.args[0]) != user.id else 0
        c.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
                  (user.id, user.username or "", ref_id))
        conn.commit()
    conn.close()

    if await check_user_access(update, context):
        text = "⚙️ **ClickEarn Pro Admin Panel**" if user.id == ADMIN_ID else get_text(user.id, 'welcome')
        await update.message.reply_text(text, reply_markup=build_main_keyboard(user.id), parse_mode="Markdown")

# --- UI NAVIGATION CALLBACKS ---
async def navigation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if is_user_blocked(user_id):
        await query.answer()
        return

    if data == "verify_channel_join":
        await query.answer()
        if await check_user_access(update, context):
            await query.edit_message_text(get_text(user_id, 'welcome'), reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")
        return

    if not await check_user_access(update, context):
        return

    await query.answer()

    if data == "nav_cancel":
        text = "⚙️ **ClickEarn Pro Admin Panel**" if user_id == ADMIN_ID else get_text(user_id, 'cancelled')
        await query.edit_message_text(text, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")

    elif data == "nav_balance":
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        bal = c.fetchone()['balance']
        conn.close()
        text = get_text(user_id, 'balance', balance=bal, bdt=bal * DOLLAR_RATE)
        await query.edit_message_text(text, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")

    elif data == "nav_referral":
        bot_obj = await context.bot.get_me()
        text = get_text(user_id, 'referral', reward=REFERRAL_REWARD_ON_WITHDRAW, bot_username=bot_obj.username, user_id=user_id)
        await query.edit_message_text(text, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")

    elif data == "nav_lang":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="setlang_bn"), InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")],
            [InlineKeyboardButton("🇪🇸 Español", callback_data="setlang_es"), InlineKeyboardButton("🇵🇹 Português", callback_data="setlang_pt")],
            [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="setlang_hi"), InlineKeyboardButton("🇵🇰 اردو", callback_data="setlang_ur")],
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

    # ADMIN BUTTON ACTIONS
    elif data == "admin_view_users" and user_id == ADMIN_ID:
        await admin_view_users_handler(query)

    elif data == "admin_suspicious" and user_id == ADMIN_ID:
        await admin_suspicious_handler(query)

# --- TASKS SYSTEM ---
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

    c.execute("INSERT INTO completed_tasks (user_id, task_id) VALUES (?, ?)", (user_id, task_id))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (task['reward'], user_id))
    conn.commit()
    conn.close()

    await query.edit_message_text(get_text(user_id, 'task_claimed', reward=f"{task['reward']:.4f}"), reply_markup=build_main_keyboard(user_id))

# --- WITHDRAWAL CONVERSATION & STRICT RE-VERIFICATION ---
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
            c.execute("UPDATE users SET balance = MAX(0.0, balance - ?) WHERE user_id = ?", (item['reward'], user_id))
            c.execute("DELETE FROM completed_tasks WHERE user_id = ? AND task_id = ?", (user_id, item['task_id']))
            conn.commit()
            conn.close()
            
            alert = get_text(user_id, 'penalty_alert', channel=item['title'], reward=f"{item['reward']:.4f}")
            await query.edit_message_text(alert, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")
            return ConversationHandler.END

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
    c.execute("UPDATE users SET balance = 0.0 WHERE user_id = ?", (user_id,))
    
    c.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row and row['referred_by'] > 0:
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REFERRAL_REWARD_ON_WITHDRAW, row['referred_by']))
        c.execute("UPDATE users SET referred_by = 0 WHERE user_id = ?", (user_id,))
    
    conn.commit()
    conn.close()

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
    await update.message.reply_text(get_text(user_id, 'withdraw_success', net=net_amount, fee=WITHDRAW_FEE, address=address), reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")
    return ConversationHandler.END

# --- ADMIN BUTTON HANDLERS ---
async def start_add_task_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(ADMIN_ID, 'cancel_btn'), callback_data="nav_cancel")]])
    await query.edit_message_text("📝 **নতুন টাস্ক যোগ করুন:**\n\nফরম্যাট অনুযায়ী একসাথে পাঠিয়া দিন:\n`Title | Link | Reward | @channel_id`", reply_markup=keyboard, parse_mode="Markdown")
    return AWAITING_TASK_INPUT

async def process_add_task_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw_text = update.message.text
        title, link, reward, channel_id = [x.strip() for x in raw_text.split("|")]
        
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO tasks (title, link, reward, channel_id) VALUES (?, ?, ?, ?)",
                  (title, link, float(reward), channel_id))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"✅ **Task Added Successfully!**\nTitle: {title}\nReward: ${reward}", reply_markup=build_main_keyboard(ADMIN_ID), parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("❌ ফরম্যাট সঠিক হয়নি! আবার চেষ্টা করুন:\n`Title | Link | Reward | @channel_id`", parse_mode="Markdown")
    return ConversationHandler.END

async def admin_view_users_handler(query):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, balance, is_blocked FROM users")
    users = c.fetchall()
    conn.close()

    msg = f"📊 **TOTAL USERS: {len(users)}**\n\n"
    for u in users[:25]:
        status = "🔴 Blocked" if u['is_blocked'] else "🟢 Active"
        msg += f"• [{u['user_id']}](tg://user?id={u['user_id']}) | @{u['username']} | `${u['balance']:.2f}` | {status}\n"
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(ADMIN_ID, 'cancel_btn'), callback_data="nav_cancel")]])
    await query.edit_message_text(msg, reply_markup=keyboard, parse_mode="Markdown")

async def admin_suspicious_handler(query):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, balance FROM users WHERE username = '' OR username IS NULL")
    suspicious = c.fetchall()
    conn.close()

    msg = f"⚠️ **SUSPICIOUS USERS (No Username): {len(suspicious)}**\n\n"
    for u in suspicious[:15]:
        msg += f"• ID: [{u['user_id']}](tg://user?id={u['user_id']}) | Bal: `${u['balance']:.2f}`\n"
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(ADMIN_ID, 'cancel_btn'), callback_data="nav_cancel")]])
    await query.edit_message_text(msg, reply_markup=keyboard, parse_mode="Markdown")

async def start_block_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_text(ADMIN_ID, 'cancel_btn'), callback_data="nav_cancel")]])
    await query.edit_message_text("🚫 **ব্লক করতে ইউজারের ID পাঠান:**", reply_markup=keyboard, parse_mode="Markdown")
    return AWAITING_BLOCK_ID

async def process_block_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text.strip())
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🚫 User {target_id} has been blocked silently.", reply_markup=build_main_keyboard(ADMIN_ID))
    except Exception:
        await update.message.reply_text("❌ বৈধ ID পাঠিয়া চেষ্টা করুন।")
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(get_text(user_id, 'cancelled'), reply_markup=build_main_keyboard(user_id))
    else:
        await update.message.reply_text(get_text(user_id, 'cancelled'), reply_markup=build_main_keyboard(user_id))
    return ConversationHandler.END

# --- MAIN INITIALIZATION ---
def main():
    init_db()
    keep_alive()

    app = Application.builder().token(BOT_TOKEN).build()

    withdraw_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_withdrawal_flow, pattern="^wmethod_")],
        states={AWAITING_PAYMENT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal_address)]},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^nav_cancel$")]
    )

    add_task_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_task_flow, pattern="^admin_add_task$")],
        states={AWAITING_TASK_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_task_input)]},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^nav_cancel$")]
    )

    block_user_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_block_flow, pattern="^admin_block_user$")],
        states={AWAITING_BLOCK_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_block_input)]},
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^nav_cancel$")]
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(withdraw_handler)
    app.add_handler(add_task_handler)
    app.add_handler(block_user_handler)
    app.add_handler(CallbackQueryHandler(navigation_handler))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
