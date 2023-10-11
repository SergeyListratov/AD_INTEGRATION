from pydantic import BaseModel, EmailStr


class SApiUserAuth(BaseModel):
    login: str
    password: str
