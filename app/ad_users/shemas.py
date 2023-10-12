from pydantic import BaseModel, EmailStr


class SAdUserAuth(BaseModel):
    login: str
    password: str
