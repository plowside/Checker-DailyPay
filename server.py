import asyncio, os
import random
from fastapi import FastAPI, Response
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright
import uvicorn

current_dir = os.path.dirname(os.path.abspath(__file__))
index_file_path = os.path.join(current_dir, 'assets\index.html')

app = FastAPI()

class FSM:
    def __init__(self):
        self.browser = None
        self.context = None
        self.pages = []

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

def randomize_browser_settings():
    user_agent = random.choice(USER_AGENTS)
    viewport = random.choice(VIEWPORTS)
    language = random.choice(LANGUAGES)
    timezone = random.choice(TIMEZONES)

    return user_agent, viewport, language, timezone

async def launch_browser():
    while True:
        try:
            async with async_playwright() as p:
                launch_options = {'headless': True, 'slow_mo': random.randint(50, 150), 'args': [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-extensions",
                    "--disable-gpu",
                    "--disable-dev-shm-usage"
                ], 'proxy': {
                    'server': 'residential.digiproxy.cc:5959',
                    'username': 'KoCLLHFAo2MMXER-res-us',
                    'password': 'S9aTfmMlcaxESWo'
                }}

                browser = await p.chromium.launch(**launch_options)
                storage.pages = []
                storage.browser = browser
                await asyncio.sleep(99999)
        except Exception as e:
            print('browser', e)

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.get_event_loop().create_task(launch_browser())
    yield
    await storage.browser.close()
    print('Browser closed')

app = FastAPI(lifespan=lifespan)

@app.get("/token")
async def get_token():
    try:
        user_agent, viewport, language, timezone = randomize_browser_settings()
        context = await storage.browser.new_context(
            user_agent=user_agent,
            viewport={"width": viewport[0], "height": viewport[1]},
            locale=language,
            timezone_id=timezone
        )
        page = await context.new_page()
        await page.goto(index_file_path)
        token = await page.evaluate('''() => {
            return new Promise((resolve) => {
                _castle('createRequestToken').then(requestToken => {
                    resolve(requestToken);
                }).catch(err => {
                    resolve(null);
                });
            });
        }''')
        await page.close()
        return {'status': True, 'token': token, 'user-agent': user_agent}
    except Exception as e:
        return {'status': False, 'error': str(e)}

@app.get("/html_page")
async def get_html_page():
    html_content = open(index_file_path, 'r', encoding='utf-8').read()
    return Response(content=html_content, media_type="text/html")

# Main entry point for server
if __name__ == '__main__':
    uvicorn.run("server:app", host="0.0.0.0", port=8000, log_level="info")
