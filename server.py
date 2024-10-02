import asyncio, playwright, os
import random
from fastapi import FastAPI, Response
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright
import uvicorn

current_dir = os.path.dirname(os.path.abspath(__file__))
index_file_path = os.path.join(current_dir, r'assets\index.html')

app = FastAPI()

class FSM:
    def __init__(self):
        self.browser = None
        self.context = None
        self.pages = []
        self.context_pool = []

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

async def launch_browser():
    while True:
        try:
            async with async_playwright() as p:
                if storage.browser is not None:
                    try: await storage.browser.close()
                    except: ...
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
                        'server': 'residential.digiproxy.cc:5959',
                        'username': 'KoCLLHFAo2MMXER-res-us',
                        'password': 'S9aTfmMlcaxESWo'
                    }
                }
                storage.browser = await p.chromium.launch(**launch_options)
                print('Browser inited')
                await asyncio.sleep(3600)
        except Exception as e:
            print('browser error:', e)

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.get_event_loop().create_task(launch_browser())
    asyncio.get_event_loop().create_task(context_pool_filler())
    yield
    await storage.browser.close()
    print('Browser closed')

app = FastAPI(lifespan=lifespan)

async def context_pool_filler():
    pool_size = 1
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
    except playwright._impl._errors.TimeoutError:
        asyncio.create_task(close_context_and_page(context, page))
        return None, None, None
    except Exception as e:
        print('Error on page.goto', type(e), '|', e)
        asyncio.create_task(close_context_and_page(context, page))
        return None, None, None
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
            return new Promise((resolve) => {
                _castle('createRequestToken').then(requestToken => {
                    resolve(requestToken);
                }).catch(err => {
                    resolve(null);
                });
            });
        }''')
        if uses >= 2:
            asyncio.create_task(close_context_and_page(context, page))
        else:
            storage.context_pool.append([context, page, user_agent, uses+1])
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
    uvicorn.run("server:app", host="0.0.0.0", port=8000, log_level="info")