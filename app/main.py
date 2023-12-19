from fastapi import FastAPI, Query, Depends
from starlette.middleware.cors import CORSMiddleware

# from starlette.middleware.cors import CORSMiddleware

from app.api_users.router import router as router_api_users
from app.ad_users.router import router as router_ad_users
from app.tasks import ad_tasks

from apscheduler.schedulers.background import BackgroundScheduler


app = FastAPI()

app.include_router(router_api_users)
app.include_router(router_ad_users)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event('startup')
def init_data():
    scheduler = BackgroundScheduler()
    scheduler.add_job(ad_tasks.create_i_ad_user, 'cron', minute='*/10')
    scheduler.start()


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


