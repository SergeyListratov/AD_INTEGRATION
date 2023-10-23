# from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
# import re
#
# # Global varsBindUser = 'domain\\username'BindPassword = '<yourpassword>'SearchGroup = 'Domain Admins'ADServer = 'dc01.domain.tld'SearchBase = 'DC=domain,DC=tld'
#
#
# def getUsersInGroup(username, password, group):
#     server = Server(ADServer)
#     conn = Connection(server, user=username, password=password, authentication=NTLM, auto_bind=True)
#     conn.bind()
#
#     conn.search(search_base=SearchBase,
#                 search_filter='(&(objectClass=GROUP)(cn=' + group +'))', search_scope=SUBTREE,
#                 attributes=['member'], size_limit=0)
#     result = conn.entries
#
#     conn.unbind()
#     return result
#
# def getUserDescription(username, password, userdn):
#     server = Server(ADServer)
#     conn = Connection(server, user=username, password=password, authentication=NTLM, auto_bind=True)
#     conn.bind()
#
#     conn.search(search_base=SearchBase,
#                 search_filter='(&(objectClass=person)(cn=' + userdn + '))', search_scope=SUBTREE,
#                 attributes=['description'], size_limit=0)
#     result = conn.entries
#
#     conn.unbind()
#     return result
# print('Querying group: ' + SearchGroup)
#
# regex_short = r" +CN=([a-zA-Z ]+)" # extracts username onlyregex_long = r" +(?:[O|C|D][U|N|C]=[a-zA-Z ]+,?)+" # extracts complete DNmatches = re.findall(regex_short, str(getUsersInGroup(username=BindUser, password=BindPassword, group=SearchGroup)))
#
# print('Found ' + str(len(matches)) + ' users associated with this group...')
#
# for match in matches:
#     print('Getting description for account: ' + match + '...')
#     match_description = str(getUserDescription(username=BindUser, password=BindPassword, userdn=match))
#
#     # check if user has a valid description    regex_desc = r"description:[ A-Za-z]+"    if re.search(regex_desc, match_description):
#         print(re.search(regex_desc, match_description)