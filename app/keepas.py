import tempfile

from app.config import settings
from pykeepass import PyKeePass
from smb.SMBConnection import SMBConnection
import os


def get_smb_conn():
    smb_conn = SMBConnection(settings.SMB_USER, settings.SMB_PASS, settings.SMB_SRV,
                             domain=settings.SMB_DOMAIN, use_ntlm_v2=True,
                             remote_name=settings.SMB_SRV)
    smb_conn.connect(settings.SMB_IP, settings.SMB_PORT)

    return smb_conn


def to_kee(smb_conn, title, username, password, description):

    descript = f'NEW+ \n {description}'
    temp_path = '/home/project/AD_INTEGRATION/data'
    group_name = 'Терминальный интернет'
    with tempfile.NamedTemporaryFile(prefix='InetUser', suffix='.kdbx', dir=temp_path) as file_obj:
        file_attr, old_size = smb_conn.retrieveFile(settings.SMB_SERVICE, settings.KEEPASS_URL, file_obj)
        kee_path = file_obj.name

        with PyKeePass(kee_path, password=settings.KEEPASS_MASTER_KEY) as kp:
            while kp.find_entries(title=title, first=True):
                title = f'{title}_$'
            group = kp.find_groups(name=group_name, first=True)
            kp.add_entry(group, title=title, username=username, password=password, notes=descript)
            kp.save()
            entry = kp.find_entries(title=title, first=True)
        with open(kee_path, 'rb+') as kee_obj:
            new_size = smb_conn.storeFile(settings.SMB_SERVICE, settings.KEEPASS_URL, kee_obj)
    kee_dict = {'old_size': old_size, 'new_size': new_size, 'user': entry}

    return kee_dict


