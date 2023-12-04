from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import validator


class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    SECRET_KEY: str
    ALG: str

    AD_LDAP_CON: str
    AD_LDAP_CONN: str
    AD_USER: str
    AD_PASS: str
    AD_BASE: str
    AD_DOMEN: str
    AD_USER: str
    AD_SERVER_IP: str
    AD_USR: str

    I_AD_LDAP_CON: str
    I_AD_LDAP_CONN: str
    I_AD_USER: str
    I_AD_PASS: str
    I_AD_BASE: str
    I_AD_DOMEN: str
    I_AD_USER: str
    I_AD_SERVER_IP: str
    I_AD_USR: str

    post_user: str
    post_user_pass: str



    @property
    def DATABASE_URL(self):
        return f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

