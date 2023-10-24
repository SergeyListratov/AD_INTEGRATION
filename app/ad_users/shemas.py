from datetime import date

from pydantic import BaseModel, EmailStr


class SAdUser(BaseModel):

    action: str
    first_name: str
    other_name: str
    last_name: str
    division: str
    role: str
    tabel_number: int



