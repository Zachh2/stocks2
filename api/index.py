from fastapi import FastAPI
from fastapi.responses import JSONResponse
import cloudscraper
from bs4 import BeautifulSoup
import re, logging, time, asyncio
from fake_useragent import UserAgent
from typing import Dict

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

# Global cache
stock_cache: Dict[str, dict] = {
    "data": {"gear_stock": {}, "egg_stock": {}, "seeds_stock": {}},
    "timestamp": 0
}

def scrape_stock_data():
    url = f"https://vulcanvalues.com/grow-a-garden/stock?_={int(time.time())}"
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    scraper = cloudscraper.create_scraper()

    for attempt in range(3):
        try:
            logger.info(f"Fetching stock data (attempt {attempt+1})...")
            response = scraper.get(url, headers=headers, timeout=15)

            if not response.text:
                logger.warning("Empty response received")
                continue

            soup = BeautifulSoup(response.text, 'lxml')
            stock_data = {
                'gear_stock': {'items': [], 'updates_in': 'Unknown'},
                'egg_stock': {'items': [], 'updates_in': 'Unknown'},
                'seeds_stock': {'items': [], 'updates_in': 'Unknown'}
            }

            stock_grid = soup.find('div', class_=re.compile(r'grid.*grid-cols'))
            if not stock_grid:
                logger.warning("Grid not found in HTML.")
                continue

            stock_sections = stock_grid.find_all('div', recursive=False)
            if not stock_sections:
                logger.warning("No sections found inside stock grid.")
                continue

            for section in stock_sections:
                title_tag = section.find('h2')
                if not title_tag: continue
                title = title_tag.text.strip().upper()
                items_list = section.find('ul')
                if not items_list: continue
                items = items_list.find_all('li')
                parsed_items = []

                for item in items:
                    span = item.find('span')
                    if not span: continue
                    name = span.contents[0].strip()
                    qty_span = span.find('span')
                    quantity = int(re.search(r'\d+', qty_span.text).group()) if qty_span else 0
                    parsed_items.append({'name': name, 'quantity': quantity})

                countdown = section.find('p', class_=re.compile(r'text-yellow.*'))
                updates_in = countdown.find('span').text.strip() if countdown and countdown.find('span') else 'Unknown'

                if 'GEAR' in title:
                    stock_data['gear_stock'] = {'items': parsed_items, 'updates_in': updates_in}
                elif 'EGG' in title:
                    stock_data['egg_stock'] = {'items': parsed_items, 'updates_in': updates_in}
                elif 'SEEDS' in title:
                    stock_data['seeds_stock'] = {'items': parsed_items, 'updates_in': updates_in}

            # Only return if valid data is found
            if any(stock_data[key]['items'] for key in stock_data):
                return stock_data
            else:
                logger.warning("Parsed data is empty. Retrying...")

        except Exception as e:
            logger.error(f"Scraping Error: {e}")
            continue

    return {'error': 'Failed to retrieve valid data'}

async def auto_update_cache():
    while True:
        logger.info("Auto-updating cache...")
        data = scrape_stock_data()
        if data and "error" not in data:
            stock_cache["data"] = data
            stock_cache["timestamp"] = time.time()
        else:
            logger.warning("Stock data was not updated due to scraping failure.")
        await asyncio.sleep(300)  # Refresh every 5 minutes

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(auto_update_cache())

@app.get("/")
async def all_data():
    return JSONResponse(content=stock_cache["data"])

@app.get("/gear")
async def gear_data():
    return JSONResponse(content=stock_cache["data"].get("gear_stock", {}))

@app.get("/egg")
async def egg_data():
    return JSONResponse(content=stock_cache["data"].get("egg_stock", {}))

@app.get("/seeds")
async def seeds_data():
    return JSONResponse(content=stock_cache["data"].get("seeds_stock", {}))
