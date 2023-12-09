import smtplib
from app.config import settings
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def post(sub, text, to, letter_from="rpz_bot1@rpz.local"):
    with smtplib.SMTP("mail.rpz.local", 587) as smtp_server:
        smtp_server.starttls()
        smtp_server.login(settings.post_user, settings.post_user_pass)

        # Создание объекта сообщения
        msg = MIMEMultipart()

        # Настройка параметров сообщения
        msg["From"] = letter_from
        msg["To"] = to
        msg["Subject"] = sub

        # Добавление текста в сообщение
        text = text
        msg.attach(MIMEText(text, "plain"))

        # Отправка письма
        smtp_server.sendmail(letter_from, to, msg.as_string())

    return True
