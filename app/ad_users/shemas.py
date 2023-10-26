from datetime import date

from pydantic import BaseModel
from fastapi import Query


class SAdUser(BaseModel):

    first_name: str
    other_name: str
    last_name: str
    number: str
    division: str
    role: str
    action: str = Query(pattern='dismiss|create|transfer')


class SAdUserResponse(BaseModel):

    status: str
    user: str
    action: str
    massage: dict
    email: str


