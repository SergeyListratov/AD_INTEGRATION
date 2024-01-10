import asyncio
import json
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import insert

from app.tasks.models import Inet
from app.config import settings
from app.database import Base, async_session_maker, engine, connection, no_async_engine
from app.ad_users.models import AdUsers
from app.api_users.models import ApiUsers
from app.main import app as fastapi_app


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    assert settings.MODE == "TEST"

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    def open_mock_json(model: str):
        with open(f"app/tests/mock_{model}.json", encoding="utf-8") as file:
            return json.load(file)

    ad_users = open_mock_json("ad_users")
    api_users = open_mock_json("api_users")
    inet = open_mock_json("inet")


    async with async_session_maker() as session:
        for Model, values in [
            (AdUsers, ad_users),
            (ApiUsers, api_users),
            (Inet, inet),
        ]:
            query = insert(Model).values(values)
            await session.execute(query)

        await session.commit()


# Взято из документации к pytest-asyncio
@pytest.fixture(scope="session")
def event_loop(request):
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def ac():
    async with AsyncClient(app=fastapi_app, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session")
async def authenticated_ac():
    async with AsyncClient(app=fastapi_app, base_url="http://test") as ac:
        await ac.post("/api/v1/auth/login", json={
            "email": "test@test.com",
            "password": "test",
        })
        assert ac.cookies["booking_access_token"]
        yield ac


# Фикстура оказалась бесполезной
# @pytest.fixture(scope="function")
# async def session():
#     async with async_session_maker() as session:
#         yield session