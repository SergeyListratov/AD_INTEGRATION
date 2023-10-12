from pydantic import BaseModel, EmailStr


class SAdUser(BaseModel):
    login: str
    password: str

    # id: Mapped[int] = mapped_column(primary_key=True)
    # api_user_id: Mapped[int]
    # first_name: Mapped[str]
    # middle_name: Mapped[str]
    # last_name: Mapped[str]
    # login_name: Mapped[Optional[str]]
    # department: Mapped[str]
    # job_title: Mapped[str]
    # tabel_number: Mapped[int]
    # action_data: Mapped[Optional[timestamp]] = mapped_column(default=datetime.utcnow())
    # # action_data: Mapped[Date] = mapped_column(Date)
    # action: Mapped[str]
