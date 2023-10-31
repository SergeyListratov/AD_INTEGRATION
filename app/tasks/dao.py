from sqlalchemy import insert, select

from app.dao.base import BaseDAO
from app.tasks.models import From1C
from app.database import async_session_maker


class From1CDAO(BaseDAO):
    model = From1C
    data: dict = {'first_name': '', 'other_name': '', 'last_name': '', 'division': '', 'role': '', 'action': '',
                  'number': '', 'message': '', 'source': '', 'status': '', 'email': '', 'login_name': ''}

    @classmethod
    async def get(cls):
        async with async_session_maker() as session:

            query = select(cls.model)._all_selected_columns
            await session.execute(query)

            await session.commit()

    @classmethod
    async def add(cls):
        async with async_session_maker() as session:
            query = insert(cls.model).values(**cls.data)
            await session.execute(query)
            await session.commit()
