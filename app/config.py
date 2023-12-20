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
    AD_GP_IN: str
    AD_GP_OUT: str

    I_AD_LDAP_CON: str
    I_AD_LDAP_CONN: str
    I_AD_USER: str
    I_AD_PASS: str
    I_AD_BASE: str
    I_AD_DOMEN: str
    I_AD_USER: str
    I_AD_SERVER_IP: str
    I_AD_USR: str
    I_AD_GROUP: str
    I_AD_OU: str

    POST_USER: str
    POST_USER_PASS: str
    POST_SERVER: str
    POST_ADM_GROUP: str

    SMB_USER: str
    SMB_PASS: str
    SMB_SRV: str
    SMB_IP: str
    SMB_PORT: str
    SMB_SERVICE: str
    SMB_DOMAIN: str

    KEEPASS_PATH: str
    KEEPASS_USER: str
    KEEPASS_PASS: str
    KEEPASS_DB: str
    KEEPASS_MASTER_KEY: str
    KEEPASS_IP: str
    KEEPASS_TEMP_PATH: str
    KEEPASS_GROUP_NAME: str

    SCHEDULE_TIME:int

    @property
    def DATABASE_URL(self):
        return f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'

    @property
    def NO_ASYNC_DATABASE_URL(self):
        return f'postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'

    @property
    def KEEPASS_URL(self):
        return f'{self.KEEPASS_PATH}{self.KEEPASS_DB}'

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
