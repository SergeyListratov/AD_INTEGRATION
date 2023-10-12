from fastapi import FastAPI, Query, Depends
from app.api_users.router import router as router_api_users
from app.ad_users.router import router as router_ad_users


app = FastAPI()

app.include_router(router_api_users)
app.include_router(router_ad_users)


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






