import imaplib
import email
import asyncio
import html
import logging
from email.header import decode_header
from datetime import datetime
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

EMAIL_ACCOUNTS = [
    {
        "server": "mail.google.com",
        "email": "test@test.com",
        "password": "qwerty12345!!"
    },
    {
        "server": "mail.google.com",
        "email": "test2@test.com",
        "password": "qwerty12345!!"
    },
    {
        "server": "mail.google.com",
        "email": "test1@test.com",
        "password": "qwerty12345!!"
    }
]

TELEGRAM_TOKEN = ""
AUTHORIZED_CHAT_ID = ""  

def decode_email_part(part):
    content = part.get_payload(decode=True)
    charset = part.get_content_charset() or 'utf-8'
    try:
        return content.decode(charset, errors='replace')
    except Exception as e:
        logger.error(f"Decoding error: {e}")
        return content.decode('utf-8', errors='replace')

def get_attachment_info(part):
    filename = part.get_filename()
    if filename:
        try:
            filename, encoding = decode_header(filename)[0]
            if isinstance(filename, bytes):
                filename = filename.decode(encoding or 'utf-8', errors='replace')
        except Exception as e:
            logger.error(f"Attachment processing error: {e}")
            filename = "Unknown_file"
    return filename

def format_email_content(msg):
    try:
        subject = ""
        decoded_subject = decode_header(msg["Subject"])
        if decoded_subject and decoded_subject[0]:
            subject_part = decoded_subject[0]
            subject = subject_part[0]
            if isinstance(subject, bytes):
                subject = subject.decode(subject_part[1] or 'utf-8', errors='replace')

        from_ = html.escape(msg.get("From", "Unknown sender"))
        date_ = html.escape(msg.get("Date", "Date not specified"))
        to_ = html.escape(msg.get("To", "Recipient not specified"))

        formatted_msg = f"""
🌟 <b>New Email Received!</b> 🌟

📋 <b>DETAILS:</b>
━━━━━━━━━━━━━━━━━━━━━
👤 <b>From:</b> {from_}
👥 <b>To:</b> {to_}
🕒 <b>Date:</b> {date_}
📌 <b>Subject:</b> {html.escape(subject)}
━━━━━━━━━━━━━━━━━━━━━
"""

        body_parts = []
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = part.get_content_disposition()

                if content_disposition == 'attachment':
                    filename = get_attachment_info(part)
                    if filename:
                        attachments.append(f"📎 {html.escape(filename)}")
                elif content_type == "text/plain":
                    body = decode_email_part(part)
                    if body.strip():
                        body_parts.append(html.escape(body.strip()))
                elif content_type == "text/html" and not body_parts:
                    body_parts.append("(HTML content available in original email)")
        else:
            body = decode_email_part(msg)
            if body.strip():
                body_parts.append(html.escape(body.strip()))

        if body_parts:
            formatted_msg += """
📝 <b>CONTENT:</b>
━━━━━━━━━━━━━━━━━━━━━
""" + "\n".join(body_parts)

        if attachments:
            formatted_msg += """

📁 <b>ATTACHMENTS:</b>
━━━━━━━━━━━━━━━━━━━━━
""" + "\n".join(attachments)

        formatted_msg += f"""

━━━━━━━━━━━━━━━━━━━━━
🤖 Email Forwarding Bot
⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""

        return formatted_msg

    except Exception as e:
        logger.error(f"Email formatting error: {e}")
        return "⚠ Error processing email"

async def check_emails(context: ContextTypes.DEFAULT_TYPE):
    for account in EMAIL_ACCOUNTS:
        try:
            mail = imaplib.IMAP4_SSL(account["server"], timeout=10)
            mail.login(account["email"], account["password"])
            mail.select("inbox", readonly=True)

            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                continue

            email_ids = messages[0].split()
            if email_ids:
                logger.info(f"Found {len(email_ids)} new emails in {account['email']}")

            for email_id in email_ids:
                try:
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    if status == "OK":
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                formatted_content = format_email_content(msg)
                                await send_to_telegram(context.bot, formatted_content)
                except Exception as e:
                    logger.error(f"Email processing error: {e}")

            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"Error in account {account['email']}: {e}")

async def send_to_telegram(bot: Bot, message: str):
    try:
        max_length = 4096
        if len(message) > max_length:
            parts = [message[i:i+max_length] for i in range(0, len(message), max_length)]
            for i, part in enumerate(parts, 1):
                header = f"📑 Part {i}/{len(parts)}\n\n"
                await bot.send_message(
                    chat_id=AUTHORIZED_CHAT_ID,
                    text=header + part,
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(0.5)
        else:
            await bot.send_message(
                chat_id=AUTHORIZED_CHAT_ID,
                text=message,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Telegram sending error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != AUTHORIZED_CHAT_ID:
        await update.message.reply_text("⛔ Sorry, you don't have access!")
        return

    await update.message.reply_text(
        "✅ Bot is active!\n"
        "Status: Monitoring email accounts...\n"
        f"Accounts: {len(EMAIL_ACCOUNTS)}\n"
        f"Last check: {datetime.now().strftime('%H:%M:%S')}"
    )

async def restricted_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Access denied!\n"
                                  "Your ID: " + str(update.effective_chat.id))

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", restricted_command))
    application.add_handler(CommandHandler("status", restricted_command))

    application.job_queue.run_repeating(
        lambda context: asyncio.create_task(check_emails(context)),
        interval=60,
        first=10
    )

    application.run_polling()

if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════╗
    ║    📧 Email Forwarding Bot Activated   ║
    ╚════════════════════════════════════════╝
    """)
    main()