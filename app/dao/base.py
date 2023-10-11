from app.database import async_session_maker
from sqlalchemy import select, insert


class BaseDAO:
    model = None

    # Метод выполняют одну и ту же функцию
    # @classmethod
    # async def find_by_id(cls, model_id: int):
    #     async with async_session_maker() as session:
    #         query = select(cls.model).filter_by(id=model_id)
    #         result = await session.execute(query)
    #         return result.mappings().one_or_none()

    @classmethod
    async def find_one_or_none(cls, **filter_by):
        async with async_session_maker() as session:
            query = select(cls.model.__table__.columns).filter_by(**filter_by)
            result = await session.execute(query)
            return result.mappings().one_or_none()

    @classmethod
    async def find_all(cls, **filter_by):
        async with async_session_maker() as session:
            query = select(cls.model.__table__.columns).filter_by(**filter_by)
            result = await session.execute(query)
            return result.mappings().all()

    @classmethod
    async def add(cls, **date):
        async with async_session_maker() as session:
            query = insert(cls.model).values(**date)
            await session.execute(query)
            await session.commit()