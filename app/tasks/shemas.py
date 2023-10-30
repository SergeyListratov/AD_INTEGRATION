from datetime import date

from pydantic import BaseModel
from fastapi import Query


class SFrom1C(BaseModel):

    status: Query(pattern='new|done')
    first_name: str
    other_name: str
    last_name: str
    number: str
    division: str
    role: str
    action_data: date
    action: str = Query(pattern='dismiss|create|transfer')

