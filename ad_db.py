import json
from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, Tls, MODIFY_REPLACE, ALL
from app.config import settings
from transliterate import translit
from typing import Optional, Dict, Any

from ldap3.extend.microsoft.addMembersToGroups import ad_add_members_to_groups
from ldap3.extend.microsoft.removeMembersFromGroups import ad_remove_members_from_groups

OBJECT_CLASS = ['top', 'person', 'organizationalPerson', 'user']
LDAP_BASE_DN = 'DC=rpz,DC=local'


'''
Функция find_ad_users ищет всех пользователей в AD по ФИО и табельному. 
В результат поиска также попадают пользователи: без отчества и без тебельного номера.
Возврещеет список словарей с найдеными пользователями.
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
                                       'sAMAccountName': ad_atr['attributes']['sAMAccountName'],
                                       # 'memberOf': ad_atr['attributes']['memberOf']
                                       }
                            find_usr_list.append(ad_dict)
                    else:
                        ad_dict = {'distinguishedName': ad_atr['attributes']['distinguishedName'],
                                   'CommonName': ad_atr['attributes']['cn'],
                                   'sAMAccountName': ad_atr['attributes']['sAMAccountName'],
                                   # 'memberOf': ad_atr['attributes']['memberOf']
                                   }
                        find_usr_list.append(ad_dict)
                    if 'memberOf' in ad_atr['attributes']:
                        find_usr_list[-1]['memberOf'] = ad_atr['attributes']['memberOf']

        return find_usr_list


'''
Функция find_ad_groups ищет все группы в AD по наименованию подразделения из 1с ЗиК. 
Использует get_translit для перевода на английский, 
get_division удаления символов.
Возврещеет список словарей с правами по умолчанию для перемещаемого польователя
и путь для нового SN .
'''


def find_ad_groups(
        division: str, ldap_base_dn: str = LDAP_BASE_DN
) -> Optional[list[dict]]:
    find_grp_list: Optional[list[dict]] = []
    with ldap_conn() as c:
        gp = get_division(get_translit(division))
        search_filter = f"(cn={gp})"
        c.search(search_base=ldap_base_dn,
                 search_filter=search_filter,
                 search_scope=SUBTREE,
                 attributes=ALL_ATTRIBUTES,
                 get_operational_attributes=True)
        ad_atr_list: Optional[list[dict]] = json.loads(c.response_to_json())['entries']
        if ad_atr_list:
            for ad_atr in ad_atr_list:
                if 'memberOf' in ad_atr['attributes']:
                    ad_dict = {'pre_distinguishedName': ad_atr['attributes']['distinguishedName'],
                               'group_distinguishedName': ad_atr['attributes']['distinguishedName'],
                               'Division': ad_atr['attributes']['cn'],
                               'memberOf': ad_atr['attributes']['memberOf']
                               }
                    find_grp_list.append(ad_dict)
                else:
                    ad_dict = {'pre_distinguishedName': ad_atr['attributes']['distinguishedName'],
                               'group_distinguishedName': ad_atr['attributes']['distinguishedName'],
                               'Division': ad_atr['attributes']['cn']
                               }
                    find_grp_list.append(ad_dict)
    if find_grp_list:
        pre_sn = find_grp_list[0]['pre_distinguishedName'].split(',')
        pre_sn.pop(0)
        pre_sn.pop(0)
        pre_sn = 'OU=Users,' + (','.join(pre_sn))
        find_grp_list[0]['pre_distinguishedName'] = pre_sn

        return find_grp_list

    return []


'''
Функция transfer_ad_user использует find_ad_users.
Перемещает всех найденых find_ad_users пользователей в AD по ФИО и табельному
в новое подразделение. Удаляет все группы доступа пользователя и добавляет группe доступа по умолчанию для нового 
подразделения (новой должности) через включение ее в группу в UO=Divivsion.
Возврещеет список словарей с описанием действия и статусом.
'''


def transfer_ad_user(
        first_name: str, other_name: str, last_name: str, initials: str, new_division: str, new_role: str
) -> Optional[list[dict]]:
    result_list: Optional[list[dict]] = []
    find_user = find_ad_users(first_name, other_name, last_name, initials)
    find_group = find_ad_groups(new_division)
    if find_user and find_group:
        d_n_user = find_user[0]['distinguishedName']
        c_n_user = f'CN={find_user[0]["CommonName"]}'
        pre_d_n_new = find_group[0]['pre_distinguishedName']
        d_n_new = f'{c_n_user},{pre_d_n_new}'
        member_of = [find_group[0]['group_distinguishedName']]
        # if 'memberOf' in find_group[0]:
        #     m_of.extend(find_group[0]['memberOf'])    #Добавление групп напрямую в дополнение к наследованию через Division
        removed_groups = []
        if 'memberOf' in find_user[0]:
            removed_groups = find_user[0]['memberOf']
        msg_suss = f'OK. User {d_n_new} remove from {removed_groups} to {member_of} division with new role:{new_role}.'
        with ldap_conn() as conn:
            conn.modify_dn(d_n_user, c_n_user, new_superior=pre_d_n_new)
            transfer_user_info = {'department': [(MODIFY_REPLACE, f'{new_division}')],
                             'company': [(MODIFY_REPLACE, 'АО РПЗ')],
                             'title': [MODIFY_REPLACE, f'{new_role}']}
            conn.modify(d_n_new, changes=transfer_user_info)

            if removed_groups:
                ad_remove_members_from_groups(conn, d_n_new, removed_groups, fix=False)
            ad_add_members_to_groups(conn, d_n_new, member_of)
            result = conn.result
        if result['result'] == 0:
            result_list.append(
                {'status': 'OK', 'msg': msg_suss})
        else:
            msg_fail = f'Error. User not transferred: {conn.result["message"]}'
            result_list.append({'status': 'ERROR', 'msg': msg_fail, 'user': d_n_user})

    return result_list


'''
Функция dismiss_ad_user использует find_ad_users.
Отключает всех найденых find_ad_users пользователей в AD по ФИО и табельному. 
Отключает пльзователей с заданным ФИО, но без табельного.
Перемещает отключенных пользоватлей в OU = Dismissed_user. Меняет табельный на '00000'.
Меняет пароль на 'Qwerty1234509876f'.
Возврещеет список словарей с описанием действия и cтатусом.
'''


def dismiss_ad_user(
        first_name: str, other_name: str, last_name: str, initials: str
) -> Optional[list[dict]]:
    with ldap_conn() as conn:
        result_list: Optional[list[dict]] = []
        find_usr_list: Optional[list[dict]] = find_ad_users(first_name, other_name, last_name, initials)
        dism_password = 'Qwerty1234509876f'
        dism_unit = 'OU=Dismissed_users'
        if find_usr_list:
            for usr in find_usr_list:
                d_n = usr["distinguishedName"]
                msg_suss = f'OK. User {d_n.split(",")[0][3:]} blocked and move to Dismissed_users.'
                disable_account = {"userAccountControl": (MODIFY_REPLACE, [514])}
                diss_initials = {'initials': '00000'}
                conn.modify(d_n, changes=disable_account)
                # conn.modify(d_n, changes=diss_initials)
                conn.extend.microsoft.modify_password(user=d_n,
                                                      new_password=dism_password,
                                                      old_password=None)
                d_n_list = d_n.split(",")
                d_n_list[1] = dism_unit
                c_n = d_n_list.pop(0)
                d_n_diss = ','.join(d_n_list)
                conn.modify_dn(d_n, c_n, new_superior=d_n_diss)
                if conn.result['result'] == 0:
                    result_list.append(
                        {'status': 'OK', 'msg': msg_suss, 'user': d_n, 'dismissed_user': f'{c_n},{d_n_diss}'})
                else:
                    msg_fail = f'Error. User not blocked: {conn.result["message"]}'
                    result_list.append({'status': 'ERROR', 'msg': msg_fail, 'user': d_n, 'dismissed_user': d_n_diss})

            return result_list
        else:
            msg_fail = f'Error. User {first_name} {other_name}, {last_name} not found.'
            result_list.append({'status': 'ERROR', 'msg': msg_fail, 'user': None, 'dismissed_user': None})
            return result_list




def create_ad_user(
        first_name: str, other_name: str, last_name: str, initials: str, division: str, role: str
) -> Optional[list[dict]]:
    result_list: Optional[list[dict]] = []
    find_user = find_ad_users(first_name, other_name, last_name, initials)
    find_group = find_ad_groups(division)
    if not find_user and find_group:
        pre_d_n_user = find_group[0]['pre_distinguishedName']
        d_n_group = find_group[0]['group_distinguishedName']
        at = get_attributes(first_name, other_name, last_name, initials, division, role)

    return result_list



# def create_ad_user(username, forename, surname, division, new_password):
#     with ldap_conn() as conn:
#         attributes = get_attributes(username, forename, surname)
#         user_dn = get_dn(username, division)
#         print(user_dn, attributes)
#         result = conn.add(dn=user_dn, object_class=OBJECT_CLASS, attributes=attributes)
#         if not result:
#             msg = f'ERROR: User {username} was not created: {conn.result.get("description")}'
#             raise Exception(msg)
#
#         # unlock and set password
#         conn.extend.microsoft.unlock_account(user=user_dn)
#         conn.extend.microsoft.modify_password(user=user_dn,
#                                               new_password=new_password,
#                                               old_password=None)
#         # Enable account - must happen after user password is set
#         enable_account = {"userAccountControl": (MODIFY_REPLACE, [512])}
#         conn.modify(user_dn, changes=enable_account)
#
#         # Add groups
#         conn.extend.microsoft.add_members_to_groups([user_dn], get_groups())


def ldap_conn():
    server = Server(settings.AD_SERVER_IP, use_ssl=False, get_info=ALL)
    return Connection(server, user=settings.AD_USER, password=settings.AD_PASS, auto_bind=True)


def get_dn(first_name: str, other_name: str, last_name: str, initials: str, division: str):
    c_n = f'{first_name} {other_name} {last_name}'
    return f"CN={c_n},OU=New_users,OU={division},DC=rpz,DC=local"


def get_attributes(
        first_name: str, other_name: str, last_name: str, initials: str, division: str, role: str
) -> dict[str, str | Any]:
    c_n = f'{first_name} {other_name} {last_name}'
    username = login_generator(first_name, other_name, last_name)
    s_n = f"CN={c_n},OU=New_users,OU={division},DC=rpz,DC=local"
    return {
        "displayName": c_n,
        "sAMAccountName": username,
        "userPrincipalName": f'{username}@rpz.local',
        "name": c_n,
        "givenName": first_name,
        "sn": s_n,
        'department': division,
        'company': 'АО РПЗ',
        'title': role
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
    return new_st


def login_generator(first_name: str, other_name: str, last_name: str) -> str:
    f_n, o_n, l_n = map(get_translit, (first_name.lower(), other_name.lower(), last_name.lower()))
    login_tuple = (
        f'{f_n[0]}.{l_n}',
        f'{f_n[0]}.{o_n[0]}.{l_n}',
        f'{l_n}',
        f'{f_n[0]}.{l_n}1',
        f'{f_n[0]}.{l_n}2',
        f'{f_n[0]}.{l_n}3'
    )
    for login in login_tuple:
        yield login


if __name__ == '__main__':
    # print(get_division('0013 (Цех13 СВП )'))
    # print(get_division('УТ (ТЕСТ БТ )'))
    # print(get_division('УТ (ТЕСТ БТ )'))
    print(get_division('МТ (ТЕСТ1 БО)'))
    # print(find_ad_groups('УТ (ТЕСТ1 БТ)'))

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

    first_name, other_name, last_name, initials, division, rol = 'Джеймс', 'Д', 'Бонд', '33999', 'МТ (ТЕСТ1 БО))', 'Специальный агент3'
    first_name, other_name, last_name, initials, division, rol = 'Джеймс', 'Д', 'Бонд', '33999', 'УТ (ТЕСТ БТ )', 'Специальный агент007'
    # print(find_ad_users(first_name, other_name, last_name, initials))
    print(transfer_ad_user(first_name, other_name, last_name, initials, division, rol))
