from datetime import datetime
from typing import Optional

from sqlalchemy import Date, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped


from app.database import Base, timestamp


class AdUsers(Base):
    __tablename__ = "ad_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    api_user_id: Mapped[str] = mapped_column(ForeignKey('api_users.id'))
    first_name: Mapped[str]
    middle_name: Mapped[str]
    last_name: Mapped[str]
    login_name: Mapped[Optional[str]]
    department: Mapped[str]
    job_title: Mapped[str]
    tabel_number: Mapped[int]
    action_data: Mapped[Optional[timestamp]] = mapped_column(default=datetime.utcnow())
    action: Mapped[str]



    def __str__(self):
        return f"User AD {self.login_name}"