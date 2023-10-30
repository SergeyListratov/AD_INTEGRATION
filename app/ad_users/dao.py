from sqlalchemy import insert

from app.dao.base import BaseDAO
from app.ad_users.models import AdUsers
from app.database import async_session_maker


class AdUsersDAO(BaseDAO):
    model = AdUsers

    @classmethod
    async def add(cls):
        async with async_session_maker() as session:
            query = insert(cls.model).values(**cls.model)
            await session.execute(query)
            await session.commit()
