import imaplib
from email.message import EmailMessage
import aiosmtplib
import email
from email.header import decode_header
from aioimaplib import IMAP4_SSL
import asyncio
from email import message_from_bytes
from html import unescape
import re
from bs4 import BeautifulSoup


SMTP_SERVER = "smtp.yandex.ru"  # SMTP сервер (например, для yandex или gmail можете использовать)
SMTP_PORT = 587                 # Порт SMTP
SMTP_USER = ""   # Ваш email
SMTP_PASSWORD = ""     # Ваш пароль от почты


IMAP_SERVER = "imap.yandex.ru"
IMAP_PORT = 993


async def send_email(subject: str, recipient: str, body: str):
    try:
        message = EmailMessage()
        message["From"] = SMTP_USER
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        await aiosmtplib.send(
            message,
            hostname=SMTP_SERVER,
            port=SMTP_PORT,
            start_tls=True,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
        )
        print(f"Email sent to {recipient}")
    except Exception as e:
        print(f"Failed to send email: {e}")

    






async def read_emails_async(limit=10):
    return await asyncio.to_thread(_read_emails_sync, limit)

def _read_emails_sync(limit):
    emails = []
    try:
        
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(SMTP_USER, SMTP_PASSWORD)  

        
        mail.select("inbox")

        
        status, messages = mail.search(None, "ALL")
        if status != "OK":
            raise Exception("Не удалось найти письма")

        
        email_ids = messages[0].split()[-limit:]

        for email_id in email_ids:
           
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            if status != "OK":
                raise Exception(f"Не удалось получить письмо с id {email_id}")

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = message_from_bytes(response_part[1])

                    
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or "utf-8")
                    from_ = decode_header(msg.get("From"))[0][0]
                    if isinstance(from_, bytes):
                        from_ = from_.decode(encoding or "utf-8")

                    
                    body = _get_body(msg)

                    emails.append({
                        "subject": subject,
                        "from": from_,
                        "body": body,
                    })

        
        mail.logout()

    except Exception as e:
        print(f"Ошибка при чтении писем: {e}")
    return emails

def _get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                return clean_html(body)
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        return clean_html(body)
    return ""

def clean_html(text):
    text = unescape(text)  
    soup = BeautifulSoup(text, "html.parser")
    
    
    for unwanted_tag in soup.find_all(["script", "style", "noscript", "iframe", "span", "div"]):
        unwanted_tag.decompose()  

    
    cleaned_text = soup.get_text("\n", strip=True)
    
    
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    
    return cleaned_text