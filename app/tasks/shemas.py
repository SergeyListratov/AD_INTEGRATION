from datetime import date

from pydantic import BaseModel
from fastapi import Query


class SInet(BaseModel):

    status: Query(pattern='ok|error')
    first_name: str
    other_name: str
    last_name: str
    number: str
    division: str
    role: str
    action_data: date
    # action: str = Query(pattern='dismiss|create|transfer')

