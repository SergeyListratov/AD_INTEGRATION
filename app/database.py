from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, mapped_column

from app.config import settings

from typing_extensions import Annotated

from sqlalchemy import create_engine

import psycopg2


timestamp = Annotated[
    datetime,
    mapped_column(nullable=False),
]

DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

no_async_engine = create_engine(settings.NO_ASYNC_DATABASE_URL)
#
connection = no_async_engine.connect()


class Base(DeclarativeBase):
    pass



