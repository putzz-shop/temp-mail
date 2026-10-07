# ====================================================================
# BOT TELEGRAM GENERATOR TEMP-MAIL (SEPERTI TEMP-MAIL.ORG)
# Runtime: Python 3.10+ dengan library python-telegram-bot v20+
# Dibuat untuk menerima kode OTP & email verifikasi secara otomatis
# ====================================================================

import os
import re
import random
import string
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Konfigurasi Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token Bot dari @BotFather
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "MASUKKAN_TOKEN_BOT_DI_SINI")

# Database sesi pengguna sederhana (in-memory)
# Format: {user_id: {"email": "...", "login": "...", "domain": "..."}}
user_sessions = {}

# Daftar domain publik 1secmail (cepat, tanpa perlu API key)
AVAILABLE_DOMAINS = [
    "1secmail.com",
    "1secmail.org",
    "1secmail.net",
    "esiix.com",
    "wwjmp.com",
    "vmani.com",
    "icznn.com"
]

def generate_random_login(length=8):
    """Membuat username acak huruf + angka"""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))

def extract_otp(text):
    """Mendeteksi kode OTP angka 4-8 digit dari isi email"""
    patterns = [
        r"(?:kode|otp|code|pin|verifikasi)[\s:=#\-*]+([0-9]{4,8})",
        r"\b([0-9]{6})\b",
        r"\b([0-9]{4})\b"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def fetch_inbox(login, domain):
    """Mengambil daftar email dari API 1secmail"""
    url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        logger.error(f"Error fetching inbox: {e}")
        return []

def fetch_message_detail(login, domain, msg_id):
    """Mengambil isi detail email"""
    url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={msg_id}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error reading message: {e}")
        return None

# ==================== HANDLER PERINTAH BOT ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perintah /start - Menyapa pengguna dan menampilkan menu"""
    user = update.effective_user
    welcome_text = (
        f"👋 Halo, <b>{user.first_name}</b>!\n\n"
        f"Selamat datang di <b>Temp Mail Bot</b>!\nBot ini membuat alamat email sementara gratis seperti di temp-mail.org untuk verifikasi OTP, pendaftaran akun, & anti-spam.\n\n<b>Perintah Utama:</b>\n• /new - Buat email acak baru\n• /inbox - Cek pesan masuk & kode OTP\n• /delete - Hapus email aktif\n• /help - Bantuan & panduan\n\n"
        f"Klik tombol di bawah untuk mulai:"
    )

    keyboard = [
        [
            InlineKeyboardButton("⚡ Buat Email Baru", callback_data="gen_email"),
            InlineKeyboardButton("📥 Kotak Masuk", callback_data="check_inbox")
        ],
        [
            InlineKeyboardButton("ℹ️ Bantuan & Info", callback_data="help_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

async def new_email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    """Membuat alamat email sementara baru untuk pengguna"""
    user_id = update.effective_user.id
    login = generate_random_login()
    domain = random.choice(AVAILABLE_DOMAINS)
    email_address = f"{login}@{domain}"

    # Simpan ke sesi
    user_sessions[user_id] = {
        "email": email_address,
        "login": login,
        "domain": domain
    }

    text = (
        f"🎉 <b>Email Sementara Berhasil Dibuat!</b>\n\n"
        f"📧 <code>{email_address}</code>\n\n"
        f"<i>(Ketuk alamat email di atas untuk langsung menyalin)</i>\n\nGunakan email ini untuk registrasi website atau aplikasi. Jika kode verifikasi/OTP dikirim, tekan tombol <b>Cek Kotak Masuk</b>."
    )

    keyboard = [
        [
            InlineKeyboardButton("📥 Cek Kotak Masuk", callback_data="check_inbox"),
            InlineKeyboardButton("🔄 Ganti Email", callback_data="gen_email")
        ],
        [
            InlineKeyboardButton("🗑️ Hapus Email", callback_data="delete_email")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.message.reply_html(text, reply_markup=reply_markup)

async def inbox_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    """Mengecek kotak masuk email pengguna"""
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)

    if not session:
        empty_text = "⚠️ Anda belum memiliki email aktif! Buat terlebih dahulu dengan perintah /new."
        keyboard = [[InlineKeyboardButton("⚡ Buat Email Sekarang", callback_data="gen_email")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if is_callback:
            await update.callback_query.edit_message_text(empty_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(empty_text, reply_markup=reply_markup)
        return

    login = session["login"]
    domain = session["domain"]
    email = session["email"]

    messages = fetch_inbox(login, domain)

    if not messages:
        no_msg_text = (
            f"📭 <b>Kotak Masuk Masih Kosong</b>\n\n"
            f"Alamat: <code>{email}</code>\n\n"
            f"Belum ada email yang masuk. Silakan kirim OTP/verifikasi lalu tekan tombol Refresh di bawah:"
        )
        keyboard = [
            [
                InlineKeyboardButton("🔄 Segarkan (Refresh)", callback_data="check_inbox"),
                InlineKeyboardButton("⚡ Email Baru", callback_data="gen_email")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if is_callback:
            await update.callback_query.edit_message_text(no_msg_text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await update.message.reply_html(no_msg_text, reply_markup=reply_markup)
        return

    # Jika ada pesan masuk
    response_text = f"📬 <b>Pesan Masuk ({len(messages)}):</b>\n\n"
    keyboard = []

    for idx, msg in enumerate(messages[:5], 1):
        msg_id = msg.get("id")
        sender = msg.get("from", "Unknown")
        subject = msg.get("subject", "(No Subject)")
        date = msg.get("date", "")

        # Ambil detail untuk mencari OTP
        detail = fetch_message_detail(login, domain, msg_id)
        otp = None
        if detail:
            body = detail.get("textBody", "") or detail.get("body", "")
            otp = extract_otp(f"{subject} {body}")

        response_text += f"<b>{idx}. Dari:</b> {sender}\n"
        response_text += f"<b>Subjek:</b> {subject}\n"
        response_text += f"<b>Waktu:</b> {date}\n"
        if otp:
            response_text += f"🔑 <b>KODE OTP:</b> <code>{otp}</code> (Ketuk untuk salin)\n"
        response_text += "-------------------------\n"

        keyboard.append([
            InlineKeyboardButton(f"📖 Buka Pesan #{idx}", callback_data=f"read_{msg_id}")
        ])

    keyboard.append([
        InlineKeyboardButton("🔄 Segarkan", callback_data="check_inbox"),
        InlineKeyboardButton("⚡ Email Baru", callback_data="gen_email")
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_callback:
        await update.callback_query.edit_message_text(response_text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.message.reply_html(response_text, reply_markup=reply_markup)

# ==================== CALLBACK QUERY ROUTER ====================

async def button_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani klik tombol inline pengguna"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "gen_email":
        await new_email_handler(update, context, is_callback=True)
    elif data == "check_inbox":
        await inbox_handler(update, context, is_callback=True)
    elif data == "delete_email":
        if user_id in user_sessions:
            del user_sessions[user_id]
        await query.edit_message_text(
            "🗑️ Email aktif telah dihapus. Gunakan /new untuk membuat yang baru.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚡ Buat Baru", callback_data="gen_email")]])
        )
    elif data.startswith("read_"):
        msg_id = data.split("_")[1]
        session = user_sessions.get(user_id)
        if session:
            detail = fetch_message_detail(session["login"], session["domain"], msg_id)
            if detail:
                body = detail.get("textBody", "") or detail.get("body", "")
                subject = detail.get("subject", "")
                sender = detail.get("from", "")
                otp = extract_otp(f"{subject} {body}")

                read_text = (
                    f"📨 <b>Detail Pesan:</b>\n\n"
                    f"<b>Dari:</b> {sender}\n"
                    f"<b>Subjek:</b> {subject}\n\n"
                )
                if otp:
                    read_text += f"🔑 <b>KODE OTP:</b> <code>{otp}</code>\n\n"
                read_text += f"<b>Isi Pesan:</b>\n<pre>{body[:800]}</pre>"

                back_btn = [[InlineKeyboardButton("⬅️ Kembali ke Kotak Masuk", callback_data="check_inbox")]]
                await query.edit_message_text(read_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(back_btn))

def main():
    """Fungsi utama untuk menjalankan bot"""
    print("🚀 Bot Telegram Temp Mail sedang berjalan...")
    app = Application.builder().token(TOKEN).build()

    # Daftarkan handler
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("new", lambda u, c: new_email_handler(u, c, False)))
    app.add_handler(CommandHandler("inbox", lambda u, c: inbox_handler(u, c, False)))
    app.add_handler(CallbackQueryHandler(button_callback_router))

    # Jalankan polling bot
    app.run_polling()

if __name__ == "__main__":
    main()
