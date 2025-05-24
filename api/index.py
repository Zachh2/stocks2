from fastapi import FastAPI
from fastapi.responses import JSONResponse
import cloudscraper
from bs4 import BeautifulSoup
import re, logging, time
from fake_useragent import UserAgent
from cachetools import TTLCache

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

# Cache with 5 minutes TTL
cache = TTLCache(maxsize=100, ttl=300)

def scrape_stock_data():
    cache_key = f"stock_data_{int(time.time() // 300)}"
    if cache_key in cache:
        return cache[cache_key]

    url = f"https://vulcanvalues.com/grow-a-garden/stock?_={int(time.time())}"
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    scraper = cloudscraper.create_scraper()

    try:
        response = scraper.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return {'error': f"Failed to fetch page, status code: {response.status_code}"}

        soup = BeautifulSoup(response.text, 'lxml')

        stock_data = {
            'gear_stock': {'items': [], 'updates_in': 'Unknown'},
            'egg_stock': {'items': [], 'updates_in': 'Unknown'},
            'seeds_stock': {'items': [], 'updates_in': 'Unknown'}
        }

        stock_grid = soup.find('div', class_=re.compile(r'grid.*grid-cols'))
        if not stock_grid:
            return {'error': 'Stock grid not found'}

        stock_sections = stock_grid.find_all('div', recursive=False)
        for section in stock_sections:
            title_tag = section.find('h2')
            if not title_tag:
                continue

            title = title_tag.text.strip().upper()
            items_list = section.find('ul')
            if not items_list:
                continue

            items = items_list.find_all('li')
            parsed_items = []

            for item in items:
                # Extract visible text
                text = item.get_text(separator=" ", strip=True)

                # Extract quantity (number) and name
                quantity_match = re.search(r'\d+', text)
                quantity = int(quantity_match.group()) if quantity_match else 0
                name = re.sub(r'\d+', '', text).strip()

                parsed_items.append({'name': name, 'quantity': quantity})

            countdown = section.find('p', class_=re.compile(r'text-yellow.*'))
            updates_in = countdown.find('span').text.strip() if countdown and countdown.find('span') else 'Unknown'

            if 'GEAR' in title:
                stock_data['gear_stock'] = {'items': parsed_items, 'updates_in': updates_in}
            elif 'EGG' in title:
                stock_data['egg_stock'] = {'items': parsed_items, 'updates_in': updates_in}
            elif 'SEEDS' in title:
                stock_data['seeds_stock'] = {'items': parsed_items, 'updates_in': updates_in}

        cache[cache_key] = stock_data
        return stock_data

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return {'error': f'Exception occurred: {str(e)}'}

# Routes
@app.get("/")
async def all_data():
    return JSONResponse(content=scrape_stock_data())

@app.get("/gear")
async def gear_data():
    return JSONResponse(content=scrape_stock_data().get("gear_stock", {}))

@app.get("/egg")
async def egg_data():
    return JSONResponse(content=scrape_stock_data().get("egg_stock", {}))

@app.get("/seeds")
async def seeds_data():
    return JSONResponse(content=scrape_stock_data().get("seeds_stock", {}))
