from app.config import settings
from pykeepass import PyKeePass
from smb.SMBConnection import SMBConnection
import os


def get_smb_conn():
    smb_conn = SMBConnection(settings.SMB_USER, settings.SMB_PASS, settings.SMB_SRV,
                             domain='rpz.local', use_ntlm_v2=True,
                             remote_name=settings.SMB_SRV)
    conn = smb_conn.connect(settings.SMB_IP, settings.SMB_PORT)

    return conn


def to_keepass():
    user = settings.KEEPASS_USER
    password = settings.KEEPASS_PASS
    path = settings.KEEPASS_PATH
    db = settings.KEEPASS_DB

    return

if __name__ == '__main__':
    # print(get_smb_conn)
    name = '1'
    login = '2'
    password = 'pass'
    div = 'One'
    role = 'Two'
    # load database
    kp = PyKeePass(settings.KEEPASS_URL, password=settings.KEEPASS_MASTER_KEY)

    # find any group by its name
    group = kp.find_groups(name='Терминальный интернет+АС ФСЗД', first=True)

    entry = kp.add_entry(group, name, login, password)
    entry.notes = f'{div} / {role}'

    kp.save()