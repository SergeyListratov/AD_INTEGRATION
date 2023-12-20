from sqlalchemy import insert, select

from app.config import settings
from app.dao.base import BaseDAO
from app.keepas import to_kee, get_smb_conn
from app.tasks.models import Inet
from app.database import async_session_maker, connection
from app.smpt import post


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
    def postal(cls, to=settings.POST_ADM_GROUP):
        if to == settings.POST_ADM_GROUP:

            sub = f"{cls.data['status']}! Регистрация {cls.data['last_name']} в сети интернет"
            text = (f" Регистрация пользователя: {cls.data['last_name']} в сети интернет.\n"
                    f" Статус проведения регистрации: {cls.data['status']}!\n"
                    f" Логин: {cls.data['login_name']}\n"
                    f" Пароль: {cls.data['i_password']} \n"
                    f" Информация: {cls.data['message']}"
                    f" Отправлено rpz_bot1.")
        else:

            sub = f"Регистрация пользователя: {cls.data['last_name']} в сети интернет"
            text = (f" Регистрация пользователя: {cls.data['last_name']} в сети интернет.\n"
                    f" Статус проведения регистрации: {cls.data['status']}!\n"
                    f" Ваш логин для доступа к ресурсам интернет: {cls.data['login_name']}\n"
                    f" Ваш пароль: {cls.data['i_password']} \n\n"
                    f" Успехов в труде! Коллектив УИТ.")

        post(sub, text, to)

    @classmethod
    def keepass(cls):
        name = cls.data['first_name']
        last_name = cls.data['last_name']
        div = cls.data['division']
        role = cls.data['role']
        title = f'{name} {last_name}'
        description = f'{div} {role}'
        result = to_kee(
            get_smb_conn(),
            title,
            cls.data['login_name'],
            cls.data['i_password'],
            description
        )

        return result

    @classmethod
    def no_async_add(cls):
        with connection as session:
            query = insert(cls.model).values(**cls.data)
            session.execute(query)
            session.commit()
