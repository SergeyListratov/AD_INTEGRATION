import json
from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, Tls, MODIFY_REPLACE, ALL
from app.config import settings
from transliterate import translit
from typing import Optional

OBJECT_CLASS = ['top', 'person', 'organizationalPerson', 'user']
# LDAP_BASE_DN = 'OU=New_users,OU=TEST33,DC=rpz,DC=local'
LDAP_BASE_DN = 'DC=rpz,DC=local'


# search_filter = "(displayName={0}*)"
# search_filter = f"(sAMAccountName={sAMAccountName})"


# def find_ad_users(username):
#     with ldap_conn() as c:
#         c.search(search_base=LDAP_BASE_DN,
#                  search_filter=search_filter.format(username),
#                  search_scope=SUBTREE,
#                  attributes=ALL_ATTRIBUTES,
#                  get_operational_attributes=True)
#
#     return json.loads(c.response_to_json())

'''
Функция find_ad_users ищет всех пользователей в AD по ФИО и табельному. 
В итог также попадают пользователи: Если у них нет отчества, и Если них нет тебельного.
'''
def find_ad_users(
        first_name: str, other_name: str, last_name: str, initials: str, ldap_base_dn: str = LDAP_BASE_DN
) -> Optional[list[dict]]:
    pattern_tuple: tuple = (f'{first_name} {other_name} {last_name}', f'{first_name} {last_name}')
    find_usr_list: Optional[list[dict]] = []
    with ldap_conn() as c:
        for patt in pattern_tuple:
            search_filter = f"(cn={patt})"
            c.search(search_base=ldap_base_dn,
                     search_filter=search_filter,
                     search_scope=SUBTREE,
                     attributes=ALL_ATTRIBUTES,
                     get_operational_attributes=True)
            ad_atr_list: Optional[list[dict]] = json.loads(c.response_to_json())['entries']
            if ad_atr_list:
                for ad_atr in ad_atr_list:
                    if 'initials' in ad_atr['attributes']:
                        if ad_atr['attributes']['initials'] == initials:
                            ad_dict = {'distinguishedName': ad_atr['attributes']['distinguishedName'],
                                       'CommonName': ad_atr['attributes']['cn'],
                                       'initials': ad_atr['attributes']['initials'],
                                       'sAMAccountName': ad_atr['attributes']['sAMAccountName']}
                            find_usr_list.append(ad_dict)
                    else:
                        ad_dict = {'distinguishedName': ad_atr['attributes']['distinguishedName'],
                                   'CommonName': ad_atr['attributes']['cn'],
                                   'sAMAccountName': ad_atr['attributes']['sAMAccountName']}
                        find_usr_list.append(ad_dict)
        return find_usr_list


def transfer_ad_user(first_name, other_name, last_name, initials):
    pass


def dismiss_ad_user(first_name, other_name, last_name, initials):
    with ldap_conn() as conn:
        msg_fail = f'User {first_name} {other_name}, {last_name} not found.'
        user_list = find_ad_users(first_name, other_name, last_name, initials)
        dism_password = 'Qwerty1234509876f'
        dism_unit = 'OU=Dismissed_users'
        if user_list:
            d_n = user_list["distinguishedName"]
            msg_suss = f'User {d_n.split(",")[0][3:]} blocked and move to Dismissed_users.'
            disable_account = {"userAccountControl": (MODIFY_REPLACE, [514])}
            conn.modify(d_n, changes=disable_account)
            conn.extend.microsoft.modify_password(user=d_n,
                                                  new_password=dism_password,
                                                  old_password=None)
            d_n_list = d_n.split(",")
            d_n_list[1] = dism_unit
            c_n = d_n_list.pop(0)
            d_n_diss = ','.join(d_n_list)
            print(c_n)
            print(d_n_diss)
            conn.modify_dn(d_n, c_n, new_superior=d_n_diss)
            if conn.result['result'] == 0:
                return msg_suss
            else:
                return f'Error. User not blocked {conn.result["message"]}'
        else:
            return msg_fail


def create_ad_user(username, forename, surname, division, new_password):
    with ldap_conn() as conn:
        attributes = get_attributes(username, forename, surname)
        user_dn = get_dn(username, division)
        print(user_dn, attributes)
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
    return f"CN={username},OU=New_users,OU={division},DC=rpz,DC=local"


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
    postfix = ',OU=Roles,OU=TEST33,DC=rpz,DC=local'
    # return [f'CN=ConnectDB_1C_83_01_TASKS_TEST{postfix}']
    return [f'CN=TEST33_TU_01{postfix}']


def get_translit(text: str) -> str:
    en_text = translit(text, language_code='ru', reversed=True)
    return en_text


def get_division(st: str) -> str:
    new_st = ''
    symbol_dict = {' ': '_', '(': '', ')': '', '.': ''}
    en_st = get_translit(st).upper()
    for s in en_st:
        if s in symbol_dict:
            s = symbol_dict[s]
        new_st = new_st + s
    new_st = new_st.strip('_')
    return new_st


def login_generator(first_name: str, other_name: str, last_name: str) -> str:
    f, o, lst = map(get_translit, (first_name.lower(), other_name.lower(), last_name.lower()))
    login_t = (
        f'{f[0]}.{lst}',
        f'{f[0]}.{o[0]}.{lst}',
        f'{lst}',
        f'{f[0]}.{lst}1',
        f'{f[0]}.{lst}2',
        f'{f[0]}.{lst}3'
    )
    for log in login_t:
        yield log


if __name__ == '__main__':
    # print(get_division('ТИ31 (УИТ ПРО)'))

    # first, middle, last = 'Сергей', 'Олегович', 'Листратов'
    #
    # ad_attr = find_ad_users(first, middle, last, '33014')

    # create_ad_user(username, forename, surname, division, new_password)

    # distinguishedName = e['entries'][0]['attributes']['distinguishedName']
    # initials = e['entries'][0]['attributes']['initials']
    # sAMAccountName = e['entries'][0]['attributes']['sAMAccountName']

    # ad_dict = {'distinguishedName': ad_attr['entries'][0]['attributes']['distinguishedName'],
    #             'CommonName': ad_attr['entries'][0]['attributes']['cn'],
    #             'initials': ad_attr['entries'][0]['attributes']['initials'],
    #            'sAMAccountName': ad_attr['entries'][0]['attributes']['sAMAccountName']}
    #
    # #
    # # for k, v in e['entries'][0]['attributes'].items():
    # #     print(k, v)
    # print(ad_dict)
    #
    # a = login_generator(first, middle, last)
    # print(next(a))
    # print(next(a))
    # print(next(a))
    # print(next(a))
    # print(next(a))

    first_name, other_name, last_name, initials = 'Джеймс', 'Д', 'Бонд', '33999'

    # print(dismiss_ad_user(first_name, other_name, last_name, initials))

    print(find_ad_users(first_name, other_name, last_name, initials))
