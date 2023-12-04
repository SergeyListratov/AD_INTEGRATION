import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy import insert, select

from app.config import settings
from app.dao.base import BaseDAO
from app.tasks.models import Inet
from app.database import async_session_maker



class InetDAO(BaseDAO):
    model = Inet
    data: dict = {'first_name': '', 'other_name': '', 'last_name': '', 'division': '', 'role': '', 'number': '',
                  'status': '', 'message': '', 'i_password': '', 'login_name': ''}

    @classmethod
    async def add(cls):
        async with async_session_maker() as session:
            query = insert(cls.model).values(**cls.data)
            await session.execute(query)
            await session.commit()

    @classmethod
    def post(cls, sub, text, to):
        letter_from = "rpz_bot1@rpz.local"
        with smtplib.SMTP("mail.rpz.local", 587) as smtp_server:
            # smtp_server = smtplib.SMTP("mail.rpz.local", 587)
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
