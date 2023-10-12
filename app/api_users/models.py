from sqlalchemy.orm import relationship, mapped_column, Mapped
from app.database import Base


class ApiUsers(Base):
    __tablename__ = "api_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    api_user_login_name: Mapped[str]
    hashed_api_user_password: Mapped[str]
    # initiator: Mapped[str]

    def __str__(self):
        return f"User API {self.api_user_login_name}"
