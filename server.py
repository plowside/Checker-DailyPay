import sqlite3
import threading
import uvicorn
from fastapi import FastAPI, Response
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service as ChromeService

# Инициализация FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    print('closed')

app = FastAPI(lifespan=lifespan)

# Глобальная переменная для подключения к базе данных
conn = None

# Инициализация базы данных SQLite3
def init_db():
    global conn
    conn = sqlite3.connect("tokens.db", check_same_thread=False)  # Постоянное подключение с параметром check_same_thread=False
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        token TEXT NOT NULL,
                        timestamp INTEGER NOT NULL
                      )''')
    conn.commit()

init_db()

# Функция для пакетного сохранения токенов в базу данных с временной меткой
def save_tokens_to_db(tokens):
    global conn
    cursor = conn.cursor()
    timestamp = int(datetime.now().timestamp())
    # Используем пакетное добавление токенов
    cursor.executemany("INSERT INTO tokens (token, timestamp) VALUES (?, ?)", [(token, timestamp) for token in tokens])
    cursor.execute('DELETE FROM tokens WHERE ? - timestamp > 40', [timestamp])
    conn.commit()

# Функция для получения токенов из антидетектного Chromium (упрощена)
def fetch_token(driver):
    try:
        tokens = []
        for _ in range(1, 1000):
            token = driver.execute_script("""
                return new Promise((resolve) => {
                    _castle('createRequestToken').then(requestToken => {
                        resolve(requestToken);
                    });
                });
            """)
            tokens.append(token)
        print(token)
        return tokens
    except Exception as e:
        print('Error in fetch_token:', e)
        return None

# Генерация и сохранение токенов
def generate_tokens():
    options = uc.ChromeOptions()
    # options.add_argument("--no-sandbox")
    # options.add_argument("--disable-blink-features=AutomationControlled")
    # options.add_argument("--disable-web-security")
    options.add_argument("--incognito")
    driver = uc.Chrome(options=options, driver_executable_path='chromedriver.exe')
    driver.set_window_size(1, 1)
    driver.get("http://localhost:8000/html_page")
    while True:
        tokens = fetch_token(driver)
        if tokens:
            save_tokens_to_db(tokens)
        print(f'Tokens generated: {len(tokens)}')
        threading.Event().wait(60)  # Генерация раз в минуту
    driver.quit()

# Синхронный маршрут для получения токена
@app.get("/token")
def get_token():
    global conn
    cursor = conn.cursor()
    current_timestamp = int(datetime.now().timestamp())
    
    # Получаем токен, который не старше 80 секунд
    cursor.execute("SELECT token, timestamp FROM tokens WHERE ? - timestamp <= 80 ORDER BY timestamp DESC LIMIT 1", (current_timestamp,))
    row = cursor.fetchone()
    
    if row:
        token, timestamp = row
        return {'status': True, 'token': token, 'timestamp': timestamp}
    else:
        return {'status': False, 'error': 'No valid tokens available'}

# Маршрут для возврата HTML страницы
@app.get("/html_page")
async def get_html_page():
    html_content = open('index.html', 'r', encoding='utf-8').read()
    return Response(content=html_content, media_type="text/html")

# Основная точка входа для запуска сервера
if __name__ == '__main__':
    threading.Thread(target=generate_tokens).start()
    uvicorn.run("server:app", log_level="info")
