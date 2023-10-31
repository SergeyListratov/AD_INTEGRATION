from datetime import datetime
from typing import Optional

from sqlalchemy import Date, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped


from app.database import Base, timestamp


class AdUsers(Base):
    __tablename__ = "ad_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str]
    first_name: Mapped[str]
    other_name: Mapped[str]
    last_name: Mapped[str]
    login_name: Mapped[Optional[str]]
    division: Mapped[str]
    role: Mapped[str]
    number: Mapped[str]
    action_data: Mapped[Optional[timestamp]] = mapped_column(default=datetime.utcnow())
    # action_data: Mapped[Date] = mapped_column(Date)
    action: Mapped[str]
    message: Mapped[str]
    email: Mapped[str]
    source: Mapped[str]

    def __str__(self):
        return f"User AD {self.login_name}"

