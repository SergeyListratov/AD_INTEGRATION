from app.dao.base import BaseDAO
from app.ad_users.models import AdUsers


class AdUsersDAO(BaseDAO):
    model = AdUsers
