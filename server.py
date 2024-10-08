import asyncio, playwright, os
import random, httpx, uvicorn, logging
from fastapi import FastAPI, Response
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright

from config import *

##############################################################################
logging.basicConfig(format=u'%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)

current_dir = os.path.dirname(os.path.abspath(__file__))
index_file_path = os.path.join(current_dir, r'assets\index.html')

app = FastAPI()


##############################################################################


class FSM:
    def __init__(self):
        self.browser = None
        self.context = None
        self.pages = []
        self.context_pool = []


class ProxyManager:
    def __init__(self, proxy_path: str = None, proxies: list = []):
        if proxy_path and os.path.exists(proxy_path):
            self.proxies_to_check = [x.strip() for x in
                                     list(set(open(proxy_path, 'r', encoding='utf-8').read().splitlines())) if
                                     x.strip() != '']
        else:
            self.proxies_to_check = {proxy: 0 for proxy in proxies}
        self.proxies = {}
        self.proxies_dict = {}

    def get_proxy(self, alr_formated: bool = True):
        try:
            min_usage_proxy = min(self.proxies, key=self.proxies.get)
            self.proxies[min_usage_proxy] += 1
            return {'http': min_usage_proxy, 'https': min_usage_proxy} if alr_formated else self.proxies_dict[min_usage_proxy]
        except:
            return None

    async def proxy_check_(self, proxy):
        if '@' in proxy:
            proxy_formated = proxy
            _proxy = proxy.split('@')
            _proxy = [*_proxy[1].split(':'), *_proxy[0].split(':')]
        else:
            _proxy = proxy.split(':')
            proxy_formated = f'{_proxy[2]}:{_proxy[3]}@{_proxy[0]}:{_proxy[1]}'
        proxy_formated = f'{"http" if proxy_protocol["http"] else "socks5"}://{proxy_formated}'
        try:
            async with httpx.AsyncClient(proxies={'http://': proxy_formated, 'https://': proxy_formated}) as client:
                await client.get('http://ip.bablosoft.com')
            self.proxies[proxy_formated] = 0
            self.proxies_dict[proxy_formated] = dict(ip=_proxy[0], port=_proxy[1], login=_proxy[2], password=_proxy[3])
        except:
            logging.info(f'[proxy_check] Invalid proxy: {proxy}')

    async def proxy_check(self):
        logging.info(f'Checking {len(self.proxies_to_check)} proxies')
        futures = []
        for proxy in list(self.proxies_to_check):
            futures.append(self.proxy_check_(proxy))
        await asyncio.gather(*futures)


storage = FSM()
storage.user_agents = open('assets/useragets.txt', 'r', encoding='utf-8').read().split('\n')

USER_AGENTS = storage.user_agents

LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
]

VIEWPORTS = [
    (1920, 1080),
    (1366, 768),
    (1440, 900),
    (1536, 864),
    (1600, 900),
]

TIMEZONES = [
    'America/New_York',
    'Europe/London',
    'Asia/Tokyo',
    'America/Los_Angeles',
    'Australia/Sydney',
    'Europe/Berlin',
]


async def randomize_browser_settings():
    user_agent = random.choice(USER_AGENTS)
    viewport = random.choice(VIEWPORTS)
    language = random.choice(LANGUAGES)
    timezone = random.choice(TIMEZONES)

    return user_agent, viewport, language, timezone


async def launch_browser(proxy_client: ProxyManager):
    while True:
        try:
            async with async_playwright() as p:
                if storage.browser is not None:
                    try:
                        await storage.browser.close()
                    except:
                        ...
                proxy = proxy_client.get_proxy(False)
                launch_options = {
                    'headless': True,
                    'args': [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-extensions",
                        "--disable-gpu",
                        "--disable-dev-shm-usage"
                    ],
                    'proxy': {
                        'server': f"{proxy['ip']}:{proxy['port']}",
                        'username': proxy['login'],
                        'password': proxy['password']
                    } if proxy else None
                }
                storage.browser = await p.chromium.launch(**launch_options)
                print('Browser inited')
                await asyncio.sleep(3600)
        except Exception as e:
            print(f'browser error ({type(e)}): e')


@asynccontextmanager
async def lifespan(app: FastAPI):
    proxy_client = ProxyManager(proxy_path=proxy_path)
    await proxy_client.proxy_check()
    tasks = []
    tasks.append(asyncio.get_event_loop().create_task(launch_browser(proxy_client)))
    tasks.append(asyncio.get_event_loop().create_task(context_pool_filler()))
    yield
    await storage.browser.close()
    print('Browser closed')
    exit()


app = FastAPI(lifespan=lifespan)


async def context_pool_filler():
    pool_size = 100
    last_pool_size = 0
    while True:
        if last_pool_size >= len(storage.context_pool) and len(storage.context_pool) >= pool_size:
            await asyncio.sleep(.5)
            continue
        print('pool_size', len(storage.context_pool))
        while len(storage.context_pool) < pool_size:
            while storage.browser is None:
                await asyncio.sleep(.5)
                continue
            tasks = [create_context_and_page(True) for x in range(pool_size - len(storage.context_pool))]
            print('filling_pool', len(tasks))
            res = await asyncio.gather(*tasks)
        last_pool_size = len(storage.context_pool)
        await asyncio.sleep(.5)


async def create_context_and_page(add_to_pool: True):
    user_agent, viewport, language, timezone = await randomize_browser_settings()
    context = await storage.browser.new_context(
        user_agent=user_agent,
        viewport={"width": viewport[0], "height": viewport[1]},
        locale=language,
        timezone_id=timezone
    )
    page = await context.new_page()
    try:
        await page.goto(index_file_path)
        await asyncio.sleep(2)
        await page.evaluate('''() => {
    return new Promise((resolve, reject) => {
        const maxTime = 10000;  // Максимальное время ожидания в миллисекундах
        const interval = 100;  // Интервал между проверками в миллисекундах
        let elapsed = 0;       // Время, прошедшее с начала проверки

        function checkCastle() {
            if (typeof _castle === 'function') {
                _castle('createRequestToken').then(requestToken => {
                    resolve(requestToken);
                }).catch(err => {
                    reject(err);
                });
            } else {
                if (elapsed >= maxTime) {
                    reject(new Error('_castle is not defined after 2 seconds'));
                } else {
                    elapsed += interval;
                    setTimeout(checkCastle, interval);  // Повтор через каждые 100 мс
                }
            }
        }

        checkCastle();
    });
}
''')
    except playwright._impl._errors.TimeoutError as e:
        print('Error on page.goto', type(e), '|', e)
        asyncio.create_task(close_context_and_page(context, page))
        return None, None, None, 0
    except playwright._impl._errors.Error as e:
        print('Error on page.goto', type(e), '|', e)
        asyncio.create_task(close_context_and_page(context, page))
        return None, None, None, 0
    except Exception as e:
        print('Error on page.goto', type(e), '|', e)
        asyncio.create_task(close_context_and_page(context, page))
        return None, None, None, 0
    if add_to_pool: storage.context_pool.append([context, page, user_agent, 0])
    return context, page, user_agent, 0


async def get_token():
    while True:
        if len(storage.context_pool) == 0:
            context, page, user_agent, uses = await create_context_and_page(False)
            if not context: continue
        else:
            context, page, user_agent, uses = storage.context_pool.pop(0)
            if not context: continue
        token = await page.evaluate('''() => {
    return new Promise((resolve, reject) => {
        const maxTime = 2000;  // Максимальное время ожидания в миллисекундах
        const interval = 100;  // Интервал между проверками в миллисекундах
        let elapsed = 0;       // Время, прошедшее с начала проверки

        function checkCastle() {
            if (typeof _castle === 'function') {
                _castle('createRequestToken').then(requestToken => {
                    resolve(requestToken);
                }).catch(err => {
                    reject(err);
                });
            } else {
                if (elapsed >= maxTime) {
                    reject(new Error('_castle is not defined after 2 seconds'));
                } else {
                    elapsed += interval;
                    setTimeout(checkCastle, interval);  // Повтор через каждые 100 мс
                }
            }
        }

        checkCastle();
    });
}
''')
        if uses >= 2:
            asyncio.create_task(close_context_and_page(context, page))
        else:
            storage.context_pool.append([context, page, user_agent, uses + 1])
        return token, user_agent


async def close_context_and_page(context, page):
    try:
        await page.close()
        await context.close()
    except Exception as e:
        print(f"Error closing page or context: {e}")


@app.get("/token")
async def route_token():
    try:
        token, user_agent = await get_token()
        return {'status': True, 'token': token, 'user-agent': user_agent}
    except Exception as e:
        return {'status': False, 'error': str(e)}


@app.get("/html_page")
async def get_html_page():
    html_content = open(index_file_path, 'r', encoding='utf-8').read()
    return Response(content=html_content, media_type="text/html")


if __name__ == '__main__':
    uvicorn.run("server:app", port=9001, log_level="info")
