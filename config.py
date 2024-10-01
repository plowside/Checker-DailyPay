### MAIN
max_concurrent_tasks = 100 # Threads
accounts_path = 'data/accounts.txt' # Accounts
custom_path = 'data/custom.txt' # Custom
hits_save_path = 'data/hits.txt' # Hits

### PROXY
proxy_path = 'data/proxy.txt' # Файл с прокси
proxy_protocol = { # Протокол прокси. Выбирать один
	'http': True,
	'socks5': False
}