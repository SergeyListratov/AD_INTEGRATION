import json

from ldap3 import Server, Connection, SUBTREE, ALL_ATTRIBUTES, Tls, MODIFY_REPLACE, ALL

from app.ad_users.dependencies import find_ad_users, transfer_ad_user
from app.config import settings
from transliterate import translit
from typing import Optional, Dict, Any, Tuple

from ldap3.extend.microsoft.addMembersToGroups import ad_add_members_to_groups
from ldap3.extend.microsoft.removeMembersFromGroups import ad_remove_members_from_groups

from exchangelib import DELEGATE, Account, Credentials

OBJECT_CLASS = ['top', 'person', 'organizationalPerson', 'user']
LDAP_BASE_DN = settings.AD_BASE
PROJECT_PATH = '/home/project/AD_INTEGRATION/data/'


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


def get_infra_ou(main: str):
    return [
        f"OU=Divisions,OU={main},{settings.OU_DEPARTMENT},{LDAP_BASE_DN}", f"OU=Roles,OU={main},{settings.OU_DEPARTMENT},{LDAP_BASE_DN}",
        f"OU=New_users,OU={main},{settings.OU_DEPARTMENT},{LDAP_BASE_DN}", f"OU=Dismissed_users,OU={main},{settings.OU_DEPARTMENT},{LDAP_BASE_DN}"
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
            dn = f"CN={div},OU=Divisions,OU={main},{settings.OU_DEPARTMENT},{LDAP_BASE_DN}"
            set_descript = {'description': descr}
            result = conn.add(dn, 'Group', set_descript)
            print(f'set div + descript : {div}, {result}')

        else:
            dn = f"CN={div},OU=Divisions,OU={main},{settings.OU_DEPARTMENT},{LDAP_BASE_DN}"
            set_descript = {'description': descr}
            result = conn.add(dn, 'Group', set_descript)
            print(f'set div + descript : {div}, {result}')


def file_to_file(file_in, file_out):
    with open(f'{PROJECT_PATH}{file_in}', 'r+', encoding='UTF-8') as file:
        with open(f'{PROJECT_PATH}{file_out}', 'w+', encoding='UTF-8') as new_file:
            for st in file:
                new_st = get_division(st)
                new_file.write(new_st)


def from_file_to_ad_prepare(file_in):
    with open(f'{PROJECT_PATH}{file_in}', 'r+', encoding='UTF-8') as file:
        for st in file:
            main, div, descr = get_division(st.split(';')[0]), get_division(st.split(';')[1]), st.split(';')[2].rstrip(
                '\n')
            set_main_descript(main, div, descr)


###foo1 Подготовка AD создание групп и назначения прав для групп (Roles)
def from_file_role_create(file_in, file_out):
    with open(f'{PROJECT_PATH}{file_in}', 'r+', encoding='UTF-8') as file:
        with open(f'{PROJECT_PATH}{file_out}', 'w+', encoding='UTF-8') as new_file:
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
    with open(f'{PROJECT_PATH}{file_in}', 'r+', encoding='UTF-8') as file:
        with open(f'{PROJECT_PATH}{file_out}', 'w+', encoding='UTF-8') as new_file:
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
    dn = f"CN={role},OU=Roles,OU={main},{settings.OU_DEPARTMENT}{LDAP_BASE_DN}"
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
    with open(f'{PROJECT_PATH}{file1_in}', 'r+', encoding='UTF-8') as all:
        with open(f'{PROJECT_PATH}{file2_in}', 'r+', encoding='UTF-8') as set:
            with open(f'{PROJECT_PATH}{file_out}', 'w+', encoding='UTF-8') as new_file:
                s = set.read().split()
                for single in all:
                    n = single.split(';')[3]
                    if n in s:
                        new_file.write(f'{single}')


def file_prep_role(file_in):
    with open(f'{PROJECT_PATH}{file_in}', 'r+', encoding='UTF-8') as all:
        for single in all:
            division = single.split(';')[0]
            role = single.split(';')[1]

    return division, role


def del_sign_group_div(file_in: str, ldap_base_dn: str = LDAP_BASE_DN, file_out='rem_all.txt') -> bool:
    with open(f'{PROJECT_PATH}{file_in}', 'r+', encoding='UTF-8') as all:
        with open(f'{PROJECT_PATH}{file_out}', 'w+', encoding='UTF-8') as new_file:

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
def search_gp_user(gp_name, ldap_base_dn: str = LDAP_BASE_DN):
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
    with open(f'{PROJECT_PATH}{file_out}', 'w+', encoding='UTF-8') as new_file:
        gp_dict = search_gp_user(group_name)
        gp_dn = gp_dict['dn']
        roles_list = gp_dict['member']
        for gp in roles_list:
            if 'Roles' in gp:
                cn = gp.split(',')[0][3:]
                usr_dict = (search_gp_user(cn))
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



