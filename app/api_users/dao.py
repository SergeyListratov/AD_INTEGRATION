from app.dao.base import BaseDAO
from app.api_users.models import ApiUsers


class ApiUsersDAO(BaseDAO):
    model = ApiUsers
