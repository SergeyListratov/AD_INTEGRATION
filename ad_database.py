from ldap3 import Server, Connection, ALL, MODIFY_ADD, MODIFY_REPLACE
from ldap3.extend.microsoft.addMembersToGroups import ad_add_members_to_groups as addUsersInGroups
from app.config import settings

group_dn ='CN=ConnectDB_1C_83_01_TASKS_TEST,OU=Access,OU=Groups,DC=rpz,DC=local'
filter = "(&(CN=Жицкий Яков Николаевич))"
row = ['Я', 'Жицкий']
srv = Server(settings.AD_SERVER_IP, use_ssl=False, get_info=ALL)
usr = f'cn={settings.AD_USR},ou=Services,ou=ASUP33,{settings.AD_BASE}'


def ldap_conn():
    server = Server(settings.AD_SERVER_IP, use_ssl=False, get_info=ALL)
    return Connection(server, user=settings.AD_USER, password=settings.AD_PASS, auto_bind=True)


with ldap_conn() as conn:
    conn.search(settings.AD_BASE, f'(&(objectclass=person)(sn={row[1]})(givenName={row[0]}*))', attributes=['CN', 'MemberOf'])
    if 'dn' in conn.response[0]:
        user_dn = conn.response[0]['dn']
        if group_dn not in conn.response[0]['attributes']['memberOf']:
            # conn.modify(group_dn, {'memberOf': [(MODIFY_ADD, [user_dn])]})
            addUsersInGroups(conn, user_dn, group_dn)
            print(f'{row[0]}.{row[1]} added to group {group_dn.split(",")[0][3:]}')
        else:
            print(f'{row[0]}.{row[1]} already in group {group_dn.split(",")[0][3:]}')
    else:
        print()
        print(f'!!!!!------{row[0]}.{row[1]} not registered in AD------!!!!!!', end='\n')
        print()

print('Finish')


# st = 'Иван', 'Иванофф', 'i.invanov', 'TEST33', '333333', '322-223 -322', 'director', 'i.ivanov@rpz.local', 'Qwerty1',

def create_ad_user(first, last, uis_login, dep, tabel_number, phone, position, domain_uis, uis_password):
    conn.bind()

    if not conn.add(f'cn={first} {last}, ou={dep}, {settings.AD_BASE}', 'person',
                 {'displayName': f'{first} {last}',  # Отображаемое имя
                  'givenName': first,  # Имя
                  'sn': last,  # Фамилия
                  'initials': tabel_number, # Табельный номер
                  'userPrincipalName': f'{uis_login}@rpz.local',  # Имя входа пользователя
                  'sAMAccountName': uis_login,  # Имя входа пользователя (пред-Windows 2000)
                  'mobile': phone,  # Телефон
                  'title': position,  # Должность
                  'mail': f'{uis_login}@{domain_uis}',  # E-mail
                  'info': uis_password  # Заметки
                  }):
        return 'Не удалось создать учётную запись в AD'



def create_ad_user1(username, forename, surname, new_password):
    with ldap_conn() as c:
        attributes = get_attributes(username, forename, surname)
        user_dn = get_dn(username)
        result = c.add(dn=user_dn,
                       object_class=OBJECT_CLASS,
                       attributes=attributes)
        if not result:
            msg = "ERROR: User '{0}' was not created: {1}".format(
                username, c.result.get("description"))
            raise Exception(msg)



create_ad_user('Иван', 'Иванофф', 'i.invanov', 'TEST33', '33333',
               '322-223-322', 'director', 'i.ivanov@rpz.local', 'Qwerty1')



# import ldap
# import csv
# # from conf import ldap_con, user, password, base
# from app.config import settings
#
# def ad_connect():
#     try:
#         ad_conn = ldap.initialize(settings.AD_LDAP_CONN)
#         ad_conn.protocol_version = ldap.VERSION3
#         ad_conn.set_option(ldap.OPT_REFERRALS, 0)
#         ad_conn.simple_bind_s(settings.AD_USER, settings.AD_PASS)
#
#         return ad_conn
#     except ldap.SERVER_DOWN:
#         return False
#
#
# base = settings.AD_BASE
# scope = ldap.SCOPE_SUBTREE
# grp_name = 'ConnectDB_1C_83_01_TASKS_TEST'
# grp_str = f'CN={grp_name},OU=Access,OU=Groups,{base}'
#
# filter = "(&(CN=Жицкий Яков Николаевич))"
# # filter = "(&(users=*))"
# attrs = ['givenName', 'sn', 'memderof']
#
# result_set = []
# ad_conn = ad_connect()
# ldap_result_id = ad_conn.search_ext(base, scope, filter, attrs)
# try:
#     while 1:
#         result_type, result_data = ad_conn.result(ldap_result_id, 0)
#         if not result_data:
#             break
#         else:
#             if result_type == ldap.RES_SEARCH_ENTRY and result_data[0][0][3].isalpha() :
#                 result_set.append(result_data)
#                 user_cn = result_data[0][0]
#                 print(result_data[0][0])
#                 print(result_data[0][1]['sn'][0].decode('UTF-8'))
#                 print(result_data[0][1]['givenName'][0].decode('UTF-8')[0])
#
#
#
#
# except ldap.SIZELIMIT_EXCEEDED:
#     print()
# print(ldap_result_id)
