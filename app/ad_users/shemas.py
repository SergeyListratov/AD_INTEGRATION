from datetime import date

from pydantic import BaseModel, EmailStr



class SAdUser(BaseModel):

    first_name: str
    middle_name: str
    last_name: str
    login_name: str
    department: str
    job_title: str
    tabel_number: int
    action_data: date
