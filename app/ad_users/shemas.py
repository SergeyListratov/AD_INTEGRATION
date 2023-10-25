from datetime import date

from pydantic import BaseModel, EmailStr


class SAdUser(BaseModel):

    first_name: str
    other_name: str
    last_name: str
    number: str
    division: str
    role: str
    action: str


class SAdUserResponse(BaseModel):

    status: str
    user: str
    action: str
    massage: dict
    email: str


