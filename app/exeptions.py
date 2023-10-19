from fastapi import HTTPException, status


class Api_User_Exception(HTTPException):  # <-- наследуемся от HTTPException, который наследован от Exception
    status_code = 500  # <-- задаем значения по умолчанию
    detail = ""

    def __init__(self):
        super().__init__(status_code=self.status_code, detail=self.detail)


class UserAlreadyExistsException(Api_User_Exception):
    status_code = status.HTTP_409_CONFLICT
    detail = "Пользователь уже существует"


# UserAlreadyExistException = HTTPException(
#     status_code=status.HTTP_409_CONFLICT,
#     detail='Пользователь уже существует'
# )

class IncorrectEmailOrPassword(Api_User_Exception):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Неверный логин или пароль"


# IncorrectEmailOrPassword = HTTPException(
#     status_code=status.HTTP_401_UNAUTHORIZED,
#     detail='Неверная почта или пароль'
# )

class TokenExpireException(Api_User_Exception):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = 'Токен истек'


class TokenAbsentException(Api_User_Exception):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = 'Токен отсутствует'


class IncorrectTokenException(Api_User_Exception):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = 'Токен имеет неверный формат'


class UserIsNotPresent(Api_User_Exception):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = 'Неверные данные о пользователе в токене'


class PermissionDenied(Api_User_Exception):
    status_code = status.HTTP_403_FORBIDDEN
    detail = 'Неавторизованный пользоваетель'


class NotAuthorizedAction(Api_User_Exception):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = 'Неавторизованные действия'


