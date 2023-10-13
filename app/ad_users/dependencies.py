import json
from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, Tls, MODIFY_REPLACE, ALL
from app.config import settings

OBJECT_CLASS = ['top', 'person', 'organizationalPerson', 'user']
LDAP_BASE_DN = 'OU=NEW_USERS,OU=Test33,DC=rpz,DC=local'
search_filter = "(displayName={0}*)"


def find_ad_users(username):
    with ldap_conn() as c:
        c.search(search_base=LDAP_BASE_DN,
                 search_filter=search_filter.format(username),
                 search_scope=SUBTREE,
                 attributes=ALL_ATTRIBUTES,
                 get_operational_attributes=True)

    return json.loads(c.response_to_json())


def create_ad_user(username, forename, surname, division, new_password):
    with ldap_conn() as conn:
        attributes = get_attributes(username, forename, surname)
        user_dn = get_dn(username, division)
        result = conn.add(dn=user_dn, object_class=OBJECT_CLASS, attributes=attributes)
        if not result:
            msg = f'ERROR: User {username} was not created: {conn.result.get("description")}'
            raise Exception(msg)

        # unlock and set password
        conn.extend.microsoft.unlock_account(user=user_dn)
        conn.extend.microsoft.modify_password(user=user_dn,
                                           new_password=new_password,
                                           old_password=None)
        # Enable account - must happen after user password is set
        enable_account = {"userAccountControl": (MODIFY_REPLACE, [512])}
        conn.modify(user_dn, changes=enable_account)

        # Add groups
        conn.extend.microsoft.add_members_to_groups([user_dn], get_groups())


def ldap_conn():
    server = Server(settings.AD_SERVER_IP, use_ssl=False, get_info=ALL)
    return Connection(server, user=settings.AD_USER, password=settings.AD_PASS, auto_bind=True)


def get_dn(username, division):
    return f"CN={username},OU=NEW_USERS,OU={division},DC=rpz,DC=local"


def get_attributes(username, forename, surname):
    return {
        "displayName": username,
        "sAMAccountName": username,
        "userPrincipalName": f'{username}@rpz.local',
        "name": username,
        "givenName": forename,
        "sn": surname
    }


def get_groups():
    postfix = ',OU=Access,OU=Groups,DC=rpz,DC=local'
    return [f'CN=ConnectDB_1C_83_01_TASKS_TEST{postfix}']


create_ad_user('D.Bond', 'Jimmy', 'Bond', 'Test33', 'Qwerty1')

print(ldap_conn())
