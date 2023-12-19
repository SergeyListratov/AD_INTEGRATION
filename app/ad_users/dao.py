from sqlalchemy import insert

from app.config import settings
from app.dao.base import BaseDAO
from app.ad_users.models import AdUsers
from app.database import async_session_maker
from app.smpt import post


class AdUsersDAO(BaseDAO):
    model = AdUsers
    data: dict = {'first_name': '', 'other_name': '', 'last_name': '', 'division': '', 'role': '', 'action': '',
                  'number': '', 'message': '', 'source': '', 'status': '', 'email': '', 'login_name': ''}

    @classmethod
    async def add(cls):
        async with async_session_maker() as session:
            query = insert(cls.model).values(**cls.data)
            await session.execute(query)
            await session.commit()

    @classmethod
    def postal(cls, to=settings.POST_ADM_GROUP):
        if to == settings.POST_ADM_GROUP:

            sub = f"{cls.data['status'].upper()}! {cls.data['action'].upper()} пользователя {cls.data['last_name']} в локальной сети."
            text = (f" {cls.data['status'].upper()}! {cls.data['action'].upper()} пользователя {cls.data['last_name']} в локальной сети.\n"
                    f" Статус события: {cls.data['status']}!\n"
                    f" Логин: {cls.data['login_name']}\n"
                    f" Почта: {cls.data['email']} \n"
                    f" Информация: {cls.data['message']}"
                    f" Отправлено rpz_bot1.")
        else:

            sub = f"{cls.data['status'].upper()}! {cls.data['action'].upper()} пользователя {cls.data['last_name']} в локальной сети."
            text = (
                f" {cls.data['status'].upper()}! {cls.data['action'].upper()} пользователя {cls.data['last_name']} в локальной сети.\n"
                f" Статус события: {cls.data['status']}!\n"
                f" Логин: {cls.data['login_name']}\n"
                f" Почта: {cls.data['email']} \n"
                f" Отправлено rpz_bot1.\n"
                f" Успехов в труде! Коллектив УИТ.")

        post(sub, text, to)
