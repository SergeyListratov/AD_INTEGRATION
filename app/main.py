import uvicorn
from fastapi import FastAPI, Query, Depends
from typing import Optional
from datetime import date
from pydantic import BaseModel

from app.api_users.router import router as router_api_users


app = FastAPI()

app.include_router(router_api_users)


class UserSearchArgs:
    def __init__(
        self,
        first_name: str,
        middle_name: str,
        last_name: str,
        login_name: str,
        department: str,
        job_title: str,
        location: str,
        tabel_number: int
    ):
        self.first_name = first_name,
        self.middle_name = middle_name,
        self.last_name = last_name,
        self.login_name = login_name,
        self.department = department,
        self.job_title = job_title,
        self.location = location,
        self.tabel_number = tabel_number

#
# @app.get("/user")
# def get_user(search_args: UserSearchArgs = Depends()):
#     pass
# #
# #     return search_args
#
#
# class SUser(BaseModel):
#     tabel_number: int
#     login_name: str
#     date_to: str
#     department: str
#
#
# @app.post('/user')
# def add_user(user: SUser):
#     pass




if __name__ == "__main__":
    uvicorn.run(app, host="173.34.4.14", port=8000)
