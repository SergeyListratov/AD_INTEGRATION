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
        other_name: str,
        last_name: str,
        login_name: str,
        division: str,
        role: str,
        action: str,
        number: int
    ):
        self.first_name = first_name,
        self.other_name = other_name,
        self.last_name = last_name,
        self.login_name = login_name,
        self.division = division,
        self.role = role,
        self.action = action,
        self.tabel_number = number






