from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.tasks.iso import decrypt_xor
from pydantic import validator


class Settings(BaseSettings):
    MODE: Literal["DEV", "TEST", "PROD"]

    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    H_DB_PASS: str
    DB_NAME: str

    TEST_DB_HOST: str
    TEST_DB_PORT: int
    TEST_DB_USER: str
    TEST_H_DB_PASS: str
    TEST_DB_NAME: str

    H_SECRET_KEY: str
    ALG: str

    AD_LDAP_CON: str
    AD_LDAP_CONN: str
    AD_USER: str
    H_AD_PASS: str
    AD_BASE: str
    AD_DOMEN: str
    AD_USER: str
    AD_SERVER_IP: str
    AD_USR: str
    AD_GP_IN: str
    AD_GP_OUT: str
    OU_DEPARTMENT: str
    H_DISM_PASS: str
    NEW_PASS: str

    I_AD_LDAP_CON: str
    I_AD_LDAP_CONN: str
    I_AD_USER: str
    H_I_AD_PASS: str
    I_AD_BASE: str
    I_AD_DOMEN: str
    I_AD_USER: str
    I_AD_SERVER_IP: str
    I_AD_USR: str
    I_AD_GROUP: str
    I_AD_OU: str

    POST_USER: str
    H_POST_USER_PASS: str
    POST_SERVER: str
    POST_ADM_GROUP: str

    SMB_USER: str
    H_SMB_PASS: str
    SMB_SRV: str
    SMB_IP: str
    SMB_PORT: str
    SMB_SERVICE: str
    SMB_DOMAIN: str

    KEEPASS_PATH: str
    KEEPASS_USER: str
    H_KEEPASS_PASS: str
    KEEPASS_DB: str
    H_KEEPASS_MASTER_KEY: str
    KEEPASS_IP: str
    KEEPASS_TEMP_PATH: str
    KEEPASS_GROUP_NAME: str
    TEST_KEEPASS_DB: str

    SCHEDULE_TIME: int

    @property
    def DATABASE_URL(self):
        return f'postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'

    @property
    def NO_ASYNC_DATABASE_URL(self):
        return f'postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'

    @property
    def TEST_DATABASE_URL(self):
        return f'postgresql+asyncpg://{self.TEST_DB_USER}:{self.TEST_DB_PASS}@{self.TEST_DB_HOST}:{self.TEST_DB_PORT}/{self.TEST_DB_NAME}'

    @property
    def TEST_NO_ASYNC_DATABASE_URL(self):
        return f'postgresql+psycopg2://{self.TEST_DB_USER}:{self.TEST_DB_PASS}@{self.TEST_DB_HOST}:{self.TEST_DB_PORT}/{self.TEST_DB_NAME}'

    @property
    def KEEPASS_URL(self):
        return f'{self.KEEPASS_PATH}{self.KEEPASS_DB}'

    @property
    def TEST_KEEPASS_URL(self):
        return f'{self.KEEPASS_PATH}{self.TEST_KEEPASS_DB}'

    @property
    def DB_PASS(self):
        return decrypt_xor(self.H_DB_PASS)

    @property
    def TEST_DB_PASS(self):
        return decrypt_xor(self.TEST_H_DB_PASS)

    @property
    def AD_PASS(self):
        return decrypt_xor(self.H_AD_PASS)

    @property
    def I_AD_PASS(self):
        return decrypt_xor(self.H_I_AD_PASS)

    @property
    def SECRET_KEY(self):
        return decrypt_xor(self.H_SECRET_KEY)

    @property
    def POST_USER_PASS(self):
        return decrypt_xor(self.H_POST_USER_PASS)

    @property
    def SMB_PASS(self):
        return decrypt_xor(self.H_SMB_PASS)

    @property
    def KEEPASS_PASS(self):
        return decrypt_xor(self.H_KEEPASS_PASS)

    @property
    def KEEPASS_MASTER_KEY(self):
        return decrypt_xor(self.H_KEEPASS_MASTER_KEY)

    @property
    def DISM_PASS(self):
        return decrypt_xor(self.H_DISM_PASS)

    # @property
    # def NEW_PASS(self):
    #     return decrypt_xor(self.H_NEW_PASS)

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
