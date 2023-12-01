import json

from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, Tls, MODIFY_REPLACE, ALL
from ldap3.core.exceptions import LDAPInvalidDnError

from app.ad_users.dao import AdUsersDAO
from app.ad_users.router import SAdUser
from app.config import settings
from transliterate import translit
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from ldap3.extend.microsoft.addMembersToGroups import ad_add_members_to_groups
from ldap3.extend.microsoft.removeMembersFromGroups import ad_remove_members_from_groups

from exchangelib import DELEGATE, Account, Credentials

OBJECT_CLASS = ['top', 'person', 'organizationalPerson', 'user']
LDAP_BASE_DN = 'DC=rpz,DC=local'
I_LDAP_BASE_DN = 'DC=rpz,DC=test'


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
    pattern_tuple: tuple = (f'{first_name} {other_name} {last_name}', f'{last_name} {other_name} {first_name}',
                            f'{last_name} {first_name} {other_name}', f'{first_name} {last_name}',
                            f'{last_name} {first_name}')
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
        gp = get_div_rol_descript(division)[0]
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

Доработать: Создание Roles, если не существует. Если не существует Divisions, то создавать в OU 0001_NEW_.
'''


def transfer_ad_user(first_name: str, other_name: str, last_name: str, number: str, division: str, role: str,
                     action='transfer', group_legacy=False, ad_role_present=True) -> dict[str, str | Any]:
    user = f'{first_name}, {other_name}, {last_name}'
    find_user = find_ad_users(first_name, other_name, last_name, number)
    find_group = find_ad_groups(division)
    div_en, rol_en, descript = get_div_rol_descript(division, role)
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
                                  'title': [MODIFY_REPLACE, f'{role} / {division}'],
                                  'description': [MODIFY_REPLACE, f'{role} / {division}']}
            conn.modify(d_n_new, changes=transfer_user_info)
            if not group_legacy:
                if removed_groups:  # Add to group with delete
                    ad_remove_members_from_groups(conn, d_n_new, removed_groups, fix=False)  #

            if ad_role_present:
                # add_user_to_rol(d_n_new, role, conn)

                try:
                    add_user_to_rol(d_n_new, rol_en, conn)
                    msg = f'OK: User {user} was remove from {removed_groups} to {member_of} division with new role:{role}.'
                except LDAPInvalidDnError:

                    new_rol_dn = set_role_descript(get_main(d_n_new), rol_en, descript, conn)

                    add_role_to_div(new_rol_dn, div_en, conn)

                    add_user_to_rol(d_n_new, rol_en, conn)
                    # conn.extend.microsoft.add_members_to_groups(d_n_new, member_of)
                    msg = (
                        f'OK: BUT Role {rol_en} was created: User {user} was remove from {removed_groups} to {member_of} division with new role:{role}.')


            else:
                # conn.extend.microsoft.add_members_to_groups(d_n_new, member_of)  Temproary
                msg = (f'OK BUT ROLE not set: User {user} was remove from {removed_groups} to {member_of} division.'
                       f' BUT not added to role group: {role}. (ad_role_present mode is active)')

            # ad_add_members_to_groups(conn, d_n_new, member_of)
            result = conn.result
        if result['result'] == 0:
            # msg = f'OK: User {user} was remove from {removed_groups} to {member_of} division with new role:{role}.'
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
                    AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data[
                        'email'] = 'ERROR', msg, 'ERROR'
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
    div_en, rol_en, descript = get_div_rol_descript(division, role)
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

            msg = f'OK. User {new_user_dn} was created in role {rol_en}.'

            # try:
            #     add_user_to_rol(new_user_dn, role, conn)
            # except LDAPInvalidDnError:
            #     conn.extend.microsoft.add_members_to_groups(new_user_dn, d_n_group)
            #     msg = f'OK. User {new_user_dn} was created in division {d_n_group}.'

            try:
                add_user_to_rol(new_user_dn, rol_en, conn)
                msg = f'OK: User {new_user_dn} was created in division {div_en} with role:{role}.'
            except LDAPInvalidDnError:

                new_rol_dn = set_role_descript(get_main(new_user_dn), rol_en, descript, conn)

                add_role_to_div(new_rol_dn, div_en, conn)

                add_user_to_rol(new_user_dn, rol_en, conn)
                # conn.extend.microsoft.add_members_to_groups(d_n_new, member_of)
                msg = (
                    f'OK: BUT Role {rol_en} was created. User {new_user_dn} was created in division {div_en} with new role:{role}.')

            # conn.extend.microsoft.add_members_to_groups([new_user_dn], d_n_group)
            # msg = f'OK. User {new_user_dn} was created in division {d_n_group}.'
            AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'], AdUsersDAO.data[
                'login_name'] = 'OK', msg, user_ad_attr['userPrincipalName'], login
    else:
        msg = (f'ERROR: User {c_n} was not created: tabel_number in use, or division not found. '
               f'find_ad_groups or find_ad_users get: []')
        AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'] = 'ERROR', msg, 'ERROR'

    result_dict = get_result(AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'])
    return result_dict


''' Creatre Users in internet domian'''


def find_group_member(group='To_internet'):
    cn = group
    user_list = search_gp_user(cn)['member']

    return user_list

    # if ad_atr_list:
    #     for ad_atr in ad_atr_list:
    #         if 'memberOf' in ad_atr['attributes']:
    #             ad_dict = {'pre_distinguishedName': ad_atr['attributes']['distinguishedName'],
    #                        'group_distinguishedName': ad_atr['attributes']['distinguishedName'],
    #                        'new_pre_distinguishedName': ad_atr['attributes']['distinguishedName'],
    #                        'Division': ad_atr['attributes']['cn'],
    #                        'memberOf': ad_atr['attributes']['memberOf']
    #                        }
    #             find_grp_list.append(ad_dict)
    #         else:
    #             ad_dict = {'pre_distinguishedName': ad_atr['attributes']['distinguishedName'],
    #                        'group_distinguishedName': ad_atr['attributes']['distinguishedName'],
    #                        'new_pre_distinguishedName': ad_atr['attributes']['distinguishedName'],
    #                        'Division': ad_atr['attributes']['cn']
    #                        }
    #             find_grp_list.append(ad_dict)


def create_i_ad_user(
        first_name: str, other_name: str, last_name: str, number: str, division: str, role: str, action='creat'
) -> dict[str, str | Any]:
    new_pass = 'Qwerty1'
    c_n = f'{first_name} {other_name} {last_name}'
    find_user = find_ad_users(first_name, other_name, last_name, number)
    init = any(map(lambda i: 'initials' in i, find_user))
    find_group = find_ad_groups(division)
    login = get_login(first_name, other_name, last_name)
    div_en, rol_en, descript = get_div_rol_descript(division, role)
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

            msg = f'OK. User {new_user_dn} was created in role {rol_en}.'

            # try:
            #     add_user_to_rol(new_user_dn, role, conn)
            # except LDAPInvalidDnError:
            #     conn.extend.microsoft.add_members_to_groups(new_user_dn, d_n_group)
            #     msg = f'OK. User {new_user_dn} was created in division {d_n_group}.'

            try:
                add_user_to_rol(new_user_dn, rol_en, conn)
                msg = f'OK: User {new_user_dn} was created in division {div_en} with role:{role}.'
            except LDAPInvalidDnError:

                new_rol_dn = set_role_descript(get_main(new_user_dn), rol_en, descript, conn)

                add_role_to_div(new_rol_dn, div_en, conn)

                add_user_to_rol(new_user_dn, rol_en, conn)
                # conn.extend.microsoft.add_members_to_groups(d_n_new, member_of)
                msg = (
                    f'OK: BUT Role {rol_en} was created. User {new_user_dn} was created in division {div_en} with new role:{role}.')

            # conn.extend.microsoft.add_members_to_groups([new_user_dn], d_n_group)
            # msg = f'OK. User {new_user_dn} was created in division {d_n_group}.'
            AdUsersDAO.data['status'], AdUsersDAO.data['message'], AdUsersDAO.data['email'], AdUsersDAO.data[
                'login_name'] = 'OK', msg, user_ad_attr['userPrincipalName'], login
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


def i_ldap_conn():
    server = Server(settings.I_AD_SERVER_IP, use_ssl=False, get_info=ALL)
    return Connection(server, user=settings.I_AD_USER, password=settings.I_AD_PASS, auto_bind=True)


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


def get_div_rol_descript(div: str, rol='None') -> tuple[str | Any, str | Any, str]:
    new_div, new_rol, new_full_rol = '', '', ''
    en_div = get_translit(div).upper()
    en_rol = get_translit(rol).upper()
    symbol_dict = {' ': '_', '(': '', ')': '', '.': '', '/': '', ',': '', '-': ''}
    for di in en_div:
        if di in symbol_dict:
            di = symbol_dict[di]
        new_div = new_div + di.rstrip()
        new_div = new_div.replace("'", "")
    for ro in en_rol:
        if ro in symbol_dict:
            ro = symbol_dict[ro]
        new_rol = (new_rol + ro).rstrip()
        new_rol = new_rol.replace("'", "")
    new_full_rol = f'{new_rol}_{new_div.rstrip("_")}'
    descript = f'{rol.rstrip()} / {div}'
    if len(new_full_rol) > 64:
        k = 1 - (len(new_rol) - (63 - len(new_div))) / len(new_rol)
        new_rol_list = new_rol.split('_')
        lst = []
        for i in range(len(new_rol_list)):
            d = len(new_rol_list[i]) * k
            if int(d) != 0:
                lst.append(new_rol_list[i][:int(d)])
        new_rol = '_'.join(lst)
        new_rol = new_rol.replace("'", "")
        new_full_rol = f'{new_rol}_{new_div.rstrip("_")}'

    return new_div, new_full_rol, descript


def get_division(st: str) -> str:
    new_st, counter = '', 64
    symbol_dict = {' ': '_', '(': '', ')': '', '.': '', '/': '', ',': '', '-': ''}
    en_st = get_translit(st).upper()
    for s in en_st:
        counter -= 1
        if s in symbol_dict:
            s = symbol_dict[s]
        new_st = new_st + s
        if not counter:
            break
    new_st = new_st.replace("'", "")

    return new_st


def login_generator(first_name: str, other_name: str, last_name: str) -> str:
    f_n, o_n, l_n = map(get_translit, (del_sign(first_name).lower(), del_sign(other_name).lower(), last_name.lower()))
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


def del_sign(wrd: str) -> str:
    new_wrd = ''
    signs = ('ъ', 'ь')
    for w in wrd:
        if w.lower() not in signs:
            new_wrd = new_wrd + w

    return new_wrd


def get_infra_ou(main: str):
    return [
        f"OU=Divisions,OU={main},DC=rpz,DC=local", f"OU=Roles,OU={main},DC=rpz,DC=local",
        f"OU=New_users,OU={main},DC=rpz,DC=local", f"OU=Dismissed_users,OU={main},DC=rpz,DC=local"
    ]


def set_main_descript(main, div, descr):
    with ldap_conn() as conn:
        if main == div:
            for dn in get_infra_ou(main):
                if dn.startswith('OU=Divisions'):
                    result = conn.add(dn, 'organizationalUnit', {'description': descr})
                else:
                    result = conn.add(dn, 'organizationalUnit')
                print(f'set main structure + descr : {result}')
            dn = f"CN={div},OU=Divisions,OU={main},DC=rpz,DC=local"
            set_descript = {'description': descr}
            result = conn.add(dn, 'Group', set_descript)
            print(f'set div + descript : {div}, {result}')

        else:
            dn = f"CN={div},OU=Divisions,OU={main},DC=rpz,DC=local"
            set_descript = {'description': descr}
            result = conn.add(dn, 'Group', set_descript)
            print(f'set div + descript : {div}, {result}')


def file_to_file(file_in, file_out):
    with open(f'/home/project/AD_INTEGRATION/data/{file_in}', 'r+', encoding='UTF-8') as file:
        with open(f'/home/project/AD_INTEGRATION/data/{file_out}', 'w+', encoding='UTF-8') as new_file:
            for st in file:
                new_st = get_division(st)
                new_file.write(new_st)


def from_file_to_ad_prepare(file_in):
    with open(f'/home/project/AD_INTEGRATION/data/{file_in}', 'r+', encoding='UTF-8') as file:
        for st in file:
            main, div, descr = get_division(st.split(';')[0]), get_division(st.split(';')[1]), st.split(';')[2].rstrip(
                '\n')
            set_main_descript(main, div, descr)


###foo1 Подготовка AD создание групп и назначения прав для групп (Roles)
def from_file_role_create(file_in, file_out):
    with open(f'/home/project/AD_INTEGRATION/data/{file_in}', 'r+', encoding='UTF-8') as file:
        with open(f'/home/project/AD_INTEGRATION/data/{file_out}', 'w+', encoding='UTF-8') as new_file:
            with ldap_conn() as conn:
                for st in file:
                    sts = st.split(';')
                    last, first, other, number = sts[0], sts[1], sts[2], sts[3]
                    div, role, descr = get_div_rol_descript(sts[4], sts[5])
                    div_ru, role_ru = sts[4].rstrip(), sts[5].rstrip()

                    found_user_list = find_ad_users(first, other, last, number)

                    if found_user_list:
                        user_add_attr = {'department': [(MODIFY_REPLACE, f'{sts[4]}')],
                                         'company': [(MODIFY_REPLACE, 'АО РПЗ')],
                                         'title': [MODIFY_REPLACE, f'{descr}'],
                                         'description': [MODIFY_REPLACE, f'{descr}']}
                        d_n = found_user_list[0]['distinguishedName']
                        member_of_user = []
                        # conn.modify(d_n, changes=user_add_attr)
                        if d_n.split(',')[-3][3:] == 'DISMISSED':
                            new_file.write(f'DISMISSED USER {last}, {first}, {other}, {number}\n')
                            continue

                        if d_n.split(',')[-3][3:] not in div:  ## trffnsfer User
                            res = transfer_ad_user(first, other, last, number, div_ru, role_ru, group_legacy=True)
                            new_file.write(
                                f'DivisionNotFound AND USER was transfered: {res}\n')
                            found_user_list = find_ad_users(first, other, last, number)
                            d_n = found_user_list[0]['distinguishedName']
                        d_n_group = set_role_descript(get_main(d_n), role, descr, conn)
                        member_of_group = find_member_of_group(d_n_group, conn)

                        conn.modify(d_n, changes=user_add_attr)

                        add_role_to_div(d_n_group, div, conn)

                        if 'memberOf' in found_user_list[0]:
                            member_of_user = found_user_list[0]['memberOf']
                            ##########################
                            m_set = set_role_member_of(d_n_group, member_of_group, member_of_user, conn, role)
                            new_file.write(f'OK {last}\n{member_of_user}\n{member_of_group}\n{m_set}\n')

                    else:
                        new_file.write(
                            f'ERROR UserNotFound {last}, {first}, {other}, {number}, {div}, {role}, {descr}\n')

    return True


##!!!foo2 Подготовка AD реализация наследования Div -- Role -- User
def from_file_role_security(file_in, file_out):
    with open(f'/home/project/AD_INTEGRATION/data/{file_in}', 'r+', encoding='UTF-8') as file:
        with open(f'/home/project/AD_INTEGRATION/data/{file_out}', 'w+', encoding='UTF-8') as new_file:
            with ldap_conn() as conn:
                for st in file:
                    sts = st.split(';')
                    last, first, other, number = sts[0], sts[1], sts[2], sts[3]
                    div, role, descr = get_div_rol_descript(sts[4], sts[5])

                    found_user_list = find_ad_users(first, other, last, number)
                    if found_user_list:
                        d_n = found_user_list[0]['distinguishedName']
                        d_n_group = set_role_descript(get_main(d_n), role, descr, conn)
                        dn_group_groups_list = find_member_of_group(d_n_group, conn)
                        dn_user_groups_list = find_member_of_group(d_n, conn)
                        dn_remove_list = list(set(dn_user_groups_list) & set(dn_group_groups_list))

                        if d_n.split(',')[-3][3:] == 'DISMISSED':
                            new_file.write(f'DISMISSED USER {last}, {first}, {other}, {number}\n')
                            continue

                        result = ad_remove_members_from_groups(conn, d_n, dn_remove_list, fix=False)
                        if result:
                            new_file.write(f'OK {last} {dn_group_groups_list}\n')

                        else:
                            new_file.write(f'ERROR DeltaNotSet {last}, {number}, {div}, {role}, {descr}\n')
                        print(d_n)
                        print(d_n_group)
                        ad_add_members_to_groups(conn, d_n, d_n_group)

                    else:
                        new_file.write(f'ERROR UserNotFound {last}, {number}, {div}, {role}, {descr}\n')


def add_role_to_div(d_n_group, div, conn):
    d_n_div_l = d_n_group.split(',')
    d_n_div_l[1] = 'OU=Divisions'
    d_n_div_l[0] = f'CN={div}'
    d_n_div = ','.join(d_n_div_l)
    print(d_n_div)
    result = ad_add_members_to_groups(conn, d_n_group, d_n_div)
    return result


def add_user_to_rol(d_n_user, role, conn):
    rol = get_division(role)
    d_n_role = d_n_user.split(',')
    d_n_role[1] = 'OU=Roles'
    d_n_role[0] = f'CN={rol}'
    d_n_group = ','.join(d_n_role)
    result = ad_add_members_to_groups(conn, d_n_user, d_n_group)
    return result


def set_role_descript(main, role, descr, conn):
    dn = f"CN={role},OU=Roles,OU={main},DC=rpz,DC=local"
    set_descript = {'description': descr}
    result = conn.add(dn, 'Group', set_descript)
    print(f'set role + descript : {role}, {result}')
    return dn


def set_role_member_of(d_n_group, member_of_group, member_of_user, conn, role):
    if member_of_group:
        group_set = set(member_of_group)
        user_set = set(member_of_user)
        group_set.intersection_update(user_set)
        member_of_set = list(group_set)
        role_set_groups_attr1 = member_of_set
        ad_remove_members_from_groups(conn, d_n_group, member_of_group, fix=False)
    else:
        role_set_groups_attr1 = member_of_user

    result = ad_add_members_to_groups(conn, d_n_group, role_set_groups_attr1)
    return role_set_groups_attr1


def set_user_role_member_of(d_n, dn_remove_groups, conn, role):
    result = ad_remove_members_from_groups(conn, d_n, dn_remove_groups, fix=False)
    return dn_remove_groups


def get_main(dn):
    main = dn.split(',')[-3][3:]
    return main


def find_member_of_group(dn, conn):
    sn = dn.split(',')[0][3:]
    search_filter = f"(cn={sn})"
    conn.search(search_base=LDAP_BASE_DN,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=ALL_ATTRIBUTES,
                get_operational_attributes=True)
    member_of = []
    ad_atr_list: Optional[list[dict]] = json.loads(conn.response_to_json())['entries']
    if ad_atr_list:
        for ad_atr in ad_atr_list:
            if 'memberOf' in ad_atr['attributes']:
                member_of = ad_atr['attributes']['memberOf']
    return member_of


def create_mailbox():
    credentials = Credentials(
        username='MYDOMAIN\\myusername',  # Or me@example.com for O365
        password='topsecret'
    )
    a = Account(
        primary_smtp_address='john@example.com',
        credentials=credentials,
        autodiscover=True,
        access_type=DELEGATE
    )
    # Print first 100 inbox messages in reverse order
    for item in a.inbox.all().only('subject').order_by('-datetime_received')[:100]:
        print(item.subject)


def file_prep(file1_in, file2_in, file_out):
    with open(f'/home/project/AD_INTEGRATION/data/{file1_in}', 'r+', encoding='UTF-8') as all:
        with open(f'/home/project/AD_INTEGRATION/data/{file2_in}', 'r+', encoding='UTF-8') as set:
            with open(f'/home/project/AD_INTEGRATION/data/{file_out}', 'w+', encoding='UTF-8') as new_file:
                s = set.read().split()
                for single in all:
                    n = single.split(';')[3]
                    if n in s:
                        new_file.write(f'{single}')


def file_prep_role(file_in):
    with open(f'/home/project/AD_INTEGRATION/data/{file_in}', 'r+', encoding='UTF-8') as all:
        for single in all:
            division = single.split(';')[0]
            role = single.split(';')[1]

    return division, role


def del_sign_group_div(file_in: str, ldap_base_dn: str = LDAP_BASE_DN, file_out='rem_all.txt') -> bool:
    with open(f'/home/project/AD_INTEGRATION/data/{file_in}', 'r+', encoding='UTF-8') as all:
        with open(f'/home/project/AD_INTEGRATION/data/{file_out}', 'w+', encoding='UTF-8') as new_file:

            for single in all:
                division = single.split(';')[0]
                roles = single.split(';')[1]

                for j in (0, 1):

                    gp = get_div_rol_descript(division, roles)[j]

                    search_filter = f"(cn={gp})"
                    with ldap_conn() as c:
                        c.search(search_base=ldap_base_dn,
                                 search_filter=search_filter,
                                 search_scope=SUBTREE,
                                 attributes=ALL_ATTRIBUTES,
                                 get_operational_attributes=True)
                        ad_atr_list: Optional[list[dict]] = json.loads(c.response_to_json())['entries']

                        if ad_atr_list:
                            attr_group = ad_atr_list[0]['attributes']
                            dn_group = attr_group['distinguishedName']
                            cn_group = dn_group.split(',')[0]
                            if "'" in cn_group:
                                new_cn_group = cn_group.replace("'", "")
                                # print(new_cn_group)
                                # print(dn_group)
                                # print(cn_group)
                                status, i = ('OK', 'Error in process'), 1
                                c.modify_dn(dn_group, new_cn_group)
                                msg = f'{status[c.result["result"]]}! Rename {cn_group} to {new_cn_group}. {c.result}'
                                new_file.write(f'{msg}\n')
                            else:
                                msg = f'OK. Sign not found in group\n'
                                new_file.write(f'{msg}\n')
                        else:
                            msg = f'Error. {gp} not found\n'
                            new_file.write(f'{msg}')

    return True


# for search_sign
def search_gp_user(gp_name, ldap_base_dn: str = LDAP_BASE_DN, ldap_conn=ldap_conn):
    gp_dict = dict()
    search_filter = f"(cn={gp_name})"
    with ldap_conn() as c:
        c.search(search_base=ldap_base_dn,
                 search_filter=search_filter,
                 search_scope=SUBTREE,
                 attributes=['member'],
                 get_operational_attributes=True)

        ad_atr_list: Optional[list[dict]] = json.loads(c.response_to_json())['entries']
        gp_dict['dn'] = ad_atr_list[0]['dn']
        gp_dict['member'] = ad_atr_list[0]['attributes']['member']

    return gp_dict


# for search_sign
def from_list_to_gp(member_lst: list, dn_group):
    added_usr = list()
    with ldap_conn() as conn:
        for dn_user in member_lst:
            result = ad_add_members_to_groups(conn, dn_user, dn_group)
            if result:
                added_usr.append(dn_user)

    return added_usr


# Возвращение прав пользователям напрямую, для групп рассылки #######
def search_sign(group_name: str, file_out='1.txt') -> dict:
    with open(f'/home/project/AD_INTEGRATION/data/{file_out}', 'w+', encoding='UTF-8') as new_file:
        gp_dict = search_gp_user(group_name)
        gp_dn = gp_dict['dn']
        roles_list = gp_dict['member']
        for gp in roles_list:
            if 'Roles' in gp:
                cn = gp.split(',')[0][3:]
                usr_dict = search_gp_user(cn)
                # result = from_list_to_gp(usr_dict['member'], gp_dn)
                with ldap_conn() as conn:
                    for dn_user in usr_dict['member']:
                        result = ad_add_members_to_groups(conn, dn_user, gp_dn)
                        if result:
                            msg = f'Ok. ({dn_user.split(",")[0][3:]} - {cn}) {result}\n'
                        else:
                            msg = f'Error. ({dn_user.split(",")[0][3:]} - {cn}) {result}\n'
                        new_file.write(msg)

    return True


if __name__ == '__main__':
    # print(i_ldap_conn())
    print(find_group_member())

    # print(get_div_rol_descript(div, rol))
    # print(get_division(div))

    # file_prep('all.csv', 'r2.csv', '1.csv')

    '''
      f = 'roles.csv'
        ff = 'xmo1.txt'
        print(from_file_role_create(f, ff))
        # print(from_file_role_security(f, ff))
    '''

    jsn1 = {

        "first_name": "Дмитрий",
        "other_name": "Петрович",
        "last_name": "Тест",
        "number": "33999",
        "division": "УТ (ТЕСТ1 БТ )",
        "role": "Специальная тестовая должность 1",
        "action": "create"

    }

    jsn2 = {
        "first_name": "Дмитрий",
        "other_name": "Петрович",
        "last_name": "Тест",
        "number": "33999",
        "division": "МТ (ТЕСТ1 БО)",
        "role": "Специальная тестовая должность 2",
        "action": "transfer"
    }

    jsn3 = {
        "first_name": "Дмитрий",
        "other_name": "Петрович",
        "last_name": "Тест",
        "number": "33999",
        "division": "МТ (ТЕСТ1 БО)",
        "role": "Специальная тестовая должность 2",
        "action": "dismiss"
    }

# ad = director(jsn3)
# print(ad)
