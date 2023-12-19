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

OBJECT_CLASS = ['top', 'person', 'organizationalPerson', 'user']
LDAP_BASE_DN = settings.AD_BASE

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
        with ldap_conn() as conn:
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
            # enable_account = {"userAccountControl": (MODIFY_REPLACE, [544])}
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
    # dn = f"CN={role},OU=Roles,OU={main},{LDAP_BASE_DN}"
    dn = f"CN={role},OU=Roles,OU={main},OU=AO_RPZ,{LDAP_BASE_DN}"
    set_descript = {'description': descr}
    result = conn.add(dn, 'Group', set_descript)
    print(f'set role + descript : {role}, {result}')
    return dn


def get_main(dn):
    main = dn.split(',')[-4][3:]
    return main
