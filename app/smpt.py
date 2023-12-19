import smtplib
from app.config import settings
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def post(sub, text, to, letter_from=settings.POST_USER):
    with smtplib.SMTP(settings.POST_SERVER, 587) as smtp_server:
        smtp_server.starttls()
        smtp_server.login(settings.POST_USER, settings.POST_USER_PASS)

        msg = MIMEMultipart()

        msg["From"] = letter_from
        msg["To"] = to
        msg["Subject"] = sub

        text = text
        msg.attach(MIMEText(text, "plain"))

        smtp_server.sendmail(letter_from, to, msg.as_string())

    return True
