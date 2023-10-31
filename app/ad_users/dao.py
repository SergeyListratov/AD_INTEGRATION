from sqlalchemy import insert

from app.dao.base import BaseDAO
from app.ad_users.models import AdUsers
from app.database import async_session_maker


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
