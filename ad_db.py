import json
from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, Tls, MODIFY_REPLACE, ALL

from app.ad_users.dao import AdUsersDAO
from app.ad_users.router import SAdUser
from app.config import settings
from transliterate import translit
from typing import Optional, Dict, Any
from datetime import datetime
from asyncio import set_event_loop, new_event_loop

from ldap3.extend.microsoft.addMembersToGroups import ad_add_members_to_groups
from ldap3.extend.microsoft.removeMembersFromGroups import ad_remove_members_from_groups

OBJECT_CLASS = ['top', 'person', 'organizationalPerson', 'user']
LDAP_BASE_DN = 'DC=rpz,DC=local'

'''
Функция director  через фабрику функций запускает нужную функцию по ключу "action" из POST запроса 
'''


def director(jsn: dict):
    selector = {
        'transfer': transfer_ad_user,
        'dismiss': dismiss_ad_user,
        'create': create_ad_user
    }
    return selector[jsn['action']](**jsn)


'''
Функция find_ad_users ищет всех пользователей в AD по ФИО и табельному. 
В результат поиска также попадают пользователи: без отчества и без тебельного номера.
Возврещеет список словарей с найдеными пользователями.
'''


def find_ad_users(
        first_name: str, other_name: str, last_name: str, number: str, ldap_base_dn: str = LDAP_BASE_DN
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
                        if ad_atr['attributes']['initials'] == number:
                            ad_dict = {'distinguishedName': ad_atr['attributes']['distinguishedName'],
                                       'CommonName': ad_atr['attributes']['cn'],
                                       'initials': ad_atr['attributes']['initials'],
                                       'sAMAccountName': ad_atr['attributes']['sAMAccountName'],
                                       }
                            find_usr_list.append(ad_dict)
                    else:
                        ad_dict = {'distinguishedName': ad_atr['attributes']['distinguishedName'],
                                   'CommonName': ad_atr['attributes']['cn'],
                                   'sAMAccountName': ad_atr['attributes']['sAMAccountName'],
                                   }
                        find_usr_list.append(ad_dict)
                    if 'memberOf' in ad_atr['attributes'] and find_usr_list:
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
                               'new_pre_distinguishedName': ad_atr['attributes']['distinguishedName'],
                               'Division': ad_atr['attributes']['cn'],
                               'memberOf': ad_atr['attributes']['memberOf']
                               }
                    find_grp_list.append(ad_dict)
                else:
                    ad_dict = {'pre_distinguishedName': ad_atr['attributes']['distinguishedName'],
                               'group_distinguishedName': ad_atr['attributes']['distinguishedName'],
                               'new_pre_distinguishedName': ad_atr['attributes']['distinguishedName'],
                               'Division': ad_atr['attributes']['cn']
                               }
                    find_grp_list.append(ad_dict)
    if find_grp_list:
        pre_sn = find_grp_list[0]['pre_distinguishedName'].split(',')
        pre_sn.pop(0)
        pre_sn.pop(0)
        pre_sn_user = 'OU=Users,' + (','.join(pre_sn))
        find_grp_list[0]['pre_distinguishedName'] = pre_sn_user
        pre_sn_new = 'OU=New_users,' + (','.join(pre_sn))
        find_grp_list[0]['new_pre_distinguishedName'] = pre_sn_new

        return find_grp_list

    return []


'''
Функция transfer_ad_user использует find_ad_users.
Перемещает всех найденых find_ad_users пользователей в AD по ФИО и табельному
в новое подразделение. Удаляет все группы доступа пользователя и добавляет группe доступа по умолчанию для нового 
подразделения (новой должности) через включение ее в группу в UO=Divivsion.
Возврещеет список словарей с описанием действия и статусом.
'''


def transfer_ad_user(first_name: str, other_name: str, last_name: str, number: str, division: str, role: str,
                     action='transfer') -> dict[str, str | Any]:
    user = f'{first_name}, {other_name}, {last_name}'
    find_user = find_ad_users(first_name, other_name, last_name, number)
    find_group = find_ad_groups(division)
    if find_user and find_group:
        user = find_user[0]['sAMAccountName']
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
        with ldap_conn() as conn:
            conn.modify_dn(d_n_user, c_n_user, new_superior=pre_d_n_new)
            transfer_user_info = {'department': [(MODIFY_REPLACE, f'{division}')],
                                  'company': [(MODIFY_REPLACE, 'АО РПЗ')],
                                  'title': [MODIFY_REPLACE, f'{role}'],
                                  'description': [MODIFY_REPLACE, f'{role}']}
            conn.modify(d_n_new, changes=transfer_user_info)

            if removed_groups:
                ad_remove_members_from_groups(conn, d_n_new, removed_groups, fix=False)
            ad_add_members_to_groups(conn, d_n_new, member_of)
            result = conn.result
        if result['result'] == 0:
            msg = f'OK: User {user} was remove from {removed_groups} to {member_of} division with new role:{role}.'
            AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'] = 'OK', msg, 'OK'
        else:
            msg = f'ERROR: User {user} not transferred: {conn.result["message"]}'
            AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'] = 'ERROR', msg, 'ERROR'

    else:
        msg = f'ERROR: User {user} was not transferred: user or division not found. find_ad_groups or find_ad_users get: []'
        AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'] = 'ERROR', msg, 'ERROR'

    result_dict = get_result(AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'])
    return result_dict


'''
Функция dismiss_ad_user использует find_ad_users.
Отключает всех найденых find_ad_users пользователей в AD по ФИО и табельному. 
Отключает пльзователей с заданным ФИО, но без табельного.
Перемещает отключенных пользоватлей в OU = Dismissed_user. Меняет табельный на '00000'.
Меняет пароль на 'Qwerty1234509876f'.
Возврещеет список словарей с описанием действия и cтатусом.
'''


def dismiss_ad_user(
        first_name: str, other_name: str, last_name: str, number: str, division='', role='', action='dismiss'
) -> dict[str, str | Any]:
    user = f'{first_name} {other_name} {last_name}'
    with ldap_conn() as conn:
        find_usr_list: Optional[list[dict]] = find_ad_users(first_name, other_name, last_name, number)
        dism_password = 'Qwerty1234509876f'
        dism_unit = 'OU=Dismissed_users'
        if find_usr_list:
            for usr in find_usr_list:
                d_n = usr["distinguishedName"]
                disable_account = {"userAccountControl": (MODIFY_REPLACE, [514]),
                                   'initials': [(MODIFY_REPLACE, '00000')],
                                   'description': [MODIFY_REPLACE,
                                                   f'Увольнение: {datetime.now().replace(microsecond=0)}']
                                   }
                conn.modify(d_n, changes=disable_account)
                conn.extend.microsoft.modify_password(user=d_n, new_password=dism_password, old_password=None)
                d_n_list = d_n.split(",")
                d_n_list[1] = dism_unit
                c_n = d_n_list.pop(0)
                d_n_diss = ','.join(d_n_list)
                conn.modify_dn(d_n, c_n, new_superior=d_n_diss)
                if conn.result['result'] == 0:
                    msg = f'OK: User {user} was dismissed and blocked in path: {d_n_diss}'
                    AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'] = 'OK', msg, 'OK'

                else:
                    msg = f'ERROR: User {user} not blocked: {conn.result["message"]}'
                    AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'] = 'ERROR', msg, 'ERROR'
        else:
            msg = f'ERROR: User {user} not found. find_ad_users get: [], Name or tabel_number not found'
            AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'] = 'ERROR', msg, 'ERROR'

    result_dict = get_result(AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'])
    return result_dict


'''
Функция create_ad_user использует find_ad_users find_ad_groups.
Создает пользователя в AD по ФИО и табельному. 
Заполняет реквизиты ползователя: должнссть отдел организация.
Перемещает пользоватлея в OU = отдела. 
Меняет пароль на 'Qwerty1' с обязательной сменой при вследующем входе.
# Возврещеет список словарей с описанием действия, cтатусом и ключем 'email'
c почтой пользовалеля для кадровой службы.
'''


def create_ad_user(
        first_name: str, other_name: str, last_name: str, number: str, division: str, role: str, action='creat'
) -> dict[str, str | Any]:
    new_pass = 'Qwerty1'
    c_n = f'{first_name} {other_name} {last_name}'
    find_user = find_ad_users(first_name, other_name, last_name, number)
    init = any(map(lambda i: 'initials' in i, find_user))
    find_group = find_ad_groups(division)
    login = get_login(first_name, other_name, last_name)
    if find_group and not init:
        pre_d_n_user = find_group[0]['new_pre_distinguishedName']
        d_n_group = find_group[0]['group_distinguishedName']
        new_user_dn = f'CN={c_n},{pre_d_n_user}'
        user_ad_attr = {
            "displayName": c_n,
            "sAMAccountName": login,
            "userPrincipalName": f'{login}@rpz.local',
            "name": c_n,
            "givenName": first_name,
            "sn": last_name,
            'department': division,
            'company': 'АО РПЗ',
            'title': role,
            'initials': number,
            'description': role
        }
        with (ldap_conn() as conn):
            result = conn.add(dn=new_user_dn, object_class=OBJECT_CLASS, attributes=user_ad_attr)
            if not result:
                msg = f'ERROR: User {new_user_dn} was not created: {conn.result.get("description")}'
                AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'] = 'ERROR', msg, 'ERROR'

                result_dict = get_result(SAdUser.status, SAdUser.msg, SAdUser.email)
                return result_dict

            # unlock and set password
            conn.extend.microsoft.unlock_account(user=new_user_dn)
            conn.extend.microsoft.modify_password(user=new_user_dn,
                                                  new_password=new_pass,
                                                  old_password=None)
            # Enable account - must happen after user password is set
            # enable_account = {"userAccountControl": (MODIFY_REPLACE, [512])}
            # conn.modify(new_user_dn, changes=enable_account)
            # Add groups
            conn.extend.microsoft.add_members_to_groups([new_user_dn], d_n_group)
            msg = f'OK. User {new_user_dn} was created in division {d_n_group}.'
            AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'], AdUsersDAO.data['login_name'] ='OK', msg, user_ad_attr['userPrincipalName'], login
    else:
        msg = (f'ERROR: User {c_n} was not created: tabel_number in use, or division not found. '
               f'find_ad_groups or find_ad_users get: []')
        AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'] = 'ERROR', msg, 'ERROR'

    result_dict = get_result(AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'])
    return result_dict


def get_result(status, msg, email):
    return {
        'status': status,
        'message': msg,
        'email': email
    }


def get_login(first_name, other_name, last_name):
    with ldap_conn() as conn:
        ad_attr = ['1']
        login_iterator = login_generator(first_name, other_name, last_name)
        while ad_attr:
            login = next(login_iterator)
            search_filter = f'(&(objectCategory=Person)(sAMAccountName={login}))'
            conn.search(search_base=LDAP_BASE_DN,
                        search_filter=search_filter,
                        search_scope=SUBTREE,
                        attributes=['sAMAccountName'])
            ad_attr: Optional[list[dict]] = json.loads(conn.response_to_json())['entries']
    return login


def ldap_conn():
    server = Server(settings.AD_SERVER_IP, use_ssl=False, get_info=ALL)
    return Connection(server, user=settings.AD_USER, password=settings.AD_PASS, auto_bind=True)


def get_dn(first_name: str, other_name: str, last_name: str, number: str, division: str):
    c_n = f'{first_name} {other_name} {last_name}'
    return f"CN={c_n},OU=New_users,OU={division},DC=rpz,DC=local"


def get_attributes(
        first_name: str, other_name: str, last_name: str, number: str, division: str, role: str
) -> dict[str, str | Any]:
    c_n = f'{first_name} {other_name} {last_name}'
    username = login_generator(first_name, other_name, last_name)
    return {
        "displayName": c_n,
        "sAMAccountName": username,
        "userPrincipalName": f'{username}@rpz.local',
        "name": username,
        "givenName": first_name,
        "sn": c_n,
        'department': division,
        'company': 'АО РПЗ',
        'title': role
    }


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
    # print(get_division('УТ (ТЕСТ БТ )'))
    # print(get_division('МТ (ТЕСТ1 БО)'))

    # first_name, other_name, last_name, initials, division, rol, action = 'Дмитрий', 'Петрович', 'Бонl', '33991', 'УТ (ТЕСТ1 БТ )', 'Специальный агент000', 'create'
    # first_name, other_name, last_name, initials, division, rol, action = 'Дмитрий', 'Петрович', 'Бонl', '33991', 'МТ (ТЕСТ1 БО)', 'Специальный агент007', 'transfer'
    # first_name, other_name, last_name, initials, division, rol, action = 'Дмитрий', 'Петрович', 'Бонl', '33991', 'УТ (ТЕСТ1 БТ )', 'Специальный агент000', 'dismiss'

    jsn1 = {

        "first_name": "Дмитрий",
        "other_name": "Петрович",
        "last_name": "Бондд",
        "number": "33997",
        "division": "УТ (ТЕСТ1 БТ )",
        "role": "Спецагент 001",
        "action": "create"

    }

    jsn2 = {
        "first_name": "Дмитрий",
        "other_name": "Петрович",
        "last_name": "Бондд",
        "number": "33997",
        "division": "МТ (ТЕСТ1 БО)",
        "role": "Спецагент007",
        "action": "transfer"
    }

    jsn3 = {
        "first_name": "Дмитрий",
        "other_name": "Петрович",
        "last_name": "Бондд",
        "number": "33997",
        "division": "МТ (ТЕСТ1 БО)",
        "role": "Спецагент007",
        "action": "dismiss"
    }

ad = director(jsn3)
print(ad)
