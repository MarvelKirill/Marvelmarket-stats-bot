import os
import asyncio
import aiohttp
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from aiohttp import web

# ================ НАСТРОЙКИ ================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')
CMC_API_KEY = os.environ.get('CMC_API_KEY')
PORT = int(os.environ.get('PORT', 10000))

# ================ API URLs ================
CMC_CRYPTO_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
CMC_GLOBAL_URL = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
CMC_FEAR_GREED_URL = "https://api.alternative.me/fng/"
CMC_GOLD_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
STOCKS_API_URL = "https://query1.finance.yahoo.com/v7/finance/quote"

MUST_INCLUDE = ['BTC', 'ETH', 'SOL']
TOP_STOCKS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA']

# ================ ФУНКЦИИ ================

async def get_crypto_data():
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    params = {'limit': 30, 'convert': 'USD'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(CMC_CRYPTO_URL, headers=headers, params=params) as response:
            data = await response.json()
            return data['data']

async def get_global_metrics():
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(CMC_GLOBAL_URL, headers=headers) as response:
            data = await response.json()
            return data['data']

async def get_fear_greed_index():
    async with aiohttp.ClientSession() as session:
        async with session.get(CMC_FEAR_GREED_URL) as response:
            data = await response.json()
            return data['data'][0]

async def get_gold_price():
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    params = {'symbol': 'PAXG', 'convert': 'USD'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(CMC_GOLD_URL, headers=headers, params=params) as response:
            data = await response.json()
            return data['data']['PAXG']

async def get_stocks_data():
    symbols = ','.join(TOP_STOCKS)
    params = {
        'symbols': symbols,
        'fields': 'symbol,regularMarketPrice,regularMarketChangePercent,marketCap'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(STOCKS_API_URL, params=params) as response:
            data = await response.json()
            return data['quoteResponse']['results']

def format_number(num):
    if num >= 1_000_000_000_000:
        return f"${num/1_000_000_000_000:.2f}T"
    elif num >= 1_000_000_000:
        return f"${num/1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"${num/1_000_000:.2f}M"
    else:
        return f"${num:,.2f}"

def get_emoji(change):
    if change > 5:
        return "🚀"
    elif change > 0:
        return "📈"
    elif change > -5:
        return "📉"
    else:
        return "💀"

def get_fear_greed_emoji(value):
    if value < 25:
        return "😱"
    elif value < 45:
        return "😰"
    elif value < 55:
        return "😐"
    elif value < 75:
        return "😊"
    else:
        return "🤑"

async def create_crypto_message():
    try:
        cryptos = await get_crypto_data()
        global_data = await get_global_metrics()
        fear_greed = await get_fear_greed_index()
        
        top_cryptos = []
        must_have = []
        
        for crypto in cryptos:
            symbol = crypto['symbol']
            if symbol in MUST_INCLUDE:
                must_have.append(crypto)
            else:
                top_cryptos.append(crypto)
        
        remaining_slots = 10 - len(must_have)
        final_list = must_have + top_cryptos[:remaining_slots]
        final_list.sort(key=lambda x: x['cmc_rank'])
        
        message = "🔥 <b>КРИПТО РЫНОК</b> 🔥\n\n"
        message += f"📊 <b>Общая капитализация:</b> {format_number(global_data['quote']['USD']['total_market_cap'])}\n"
        message += f"📈 <b>Изменение 24ч:</b> {global_data['quote']['USD']['total_market_cap_yesterday_percentage_change']:.2f}%\n"
        
        fg_value = int(fear_greed['value'])
        fg_emoji = get_fear_greed_emoji(fg_value)
        message += f"{fg_emoji} <b>Индекс страха/жадности:</b> {fg_value} ({fear_greed['value_classification']})\n\n"
        
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        message += "<b>ТОП-10 КРИПТОВАЛЮТ:</b>\n\n"
        
        for crypto in final_list:
            name = crypto['name']
            symbol = crypto['symbol']
            price = crypto['quote']['USD']['price']
            change_24h = crypto['quote']['USD']['percent_change_24h']
            market_cap = crypto['quote']['USD']['market_cap']
            emoji = get_emoji(change_24h)
            
            if price < 1:
                price_str = f"${price:.6f}"
            else:
                price_str = f"${price:,.2f}"
            
            message += f"{emoji} <b>{symbol}</b> ({name})\n"
            message += f"💰 {price_str} | "
            message += f"{'🟢' if change_24h > 0 else '🔴'} {change_24h:+.2f}%\n"
            message += f"📊 Cap: {format_number(market_cap)}\n\n"
        
        message += f"⏰ Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n"
        message += "\n💎 <b>MarvelMarket</b> - Твой гид в мире крипты!"
        
        return message
    
    except Exception as e:
        return f"❌ Ошибка при получении данных: {str(e)}"

async def create_stocks_message():
    try:
        gold = await get_gold_price()
        gold_price = gold['quote']['USD']['price']
        gold_change = gold['quote']['USD']['percent_change_24h']
        
        stocks = await get_stocks_data()
        
        message = "🏆 <b>ЗОЛОТО И ТОП АКЦИИ</b> 🏆\n\n"
        
        message += "━━━━━━━━━━━━━━━━━━\n"
        message += f"🥇 <b>ЗОЛОТО (PAXG)</b>\n"
        message += f"💰 ${gold_price:,.2f}\n"
        message += f"{'🟢' if gold_change > 0 else '🔴'} {gold_change:+.2f}% (24h)\n\n"
        
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        message += "<b>ТОП АКЦИИ США:</b>\n\n"
        
        for stock in stocks:
            symbol = stock['symbol']
            price = stock['regularMarketPrice']
            change = stock.get('regularMarketChangePercent', 0)
            market_cap = stock.get('marketCap', 0)
            emoji = get_emoji(change)
            
            message += f"{emoji} <b>{symbol}</b>\n"
            message += f"💰 ${price:,.2f} | "
            message += f"{'🟢' if change > 0 else '🔴'} {change:+.2f}%\n"
            if market_cap > 0:
                message += f"📊 Cap: {format_number(market_cap)}\n"
            message += "\n"
        
        message += f"⏰ Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n"
        message += "\n💼 <b>MarvelMarket</b> - Следим за рынками вместе!"
        
        return message
    
    except Exception as e:
        return f"❌ Ошибка при получении данных: {str(e)}"

async def send_updates():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    while True:
        try:
            crypto_msg = await create_crypto_message()
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=crypto_msg,
                parse_mode=ParseMode.HTML
            )
            
            await asyncio.sleep(5)
            
            stocks_msg = await create_stocks_message()
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=stocks_msg,
                parse_mode=ParseMode.HTML
            )
            
            print(f"✅ Обновление отправлено: {datetime.now()}")
            
            await asyncio.sleep(3600)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await asyncio.sleep(300)

async def health_check(request):
    return web.Response(text="🚀 MarvelMarket Stats Bot is running!")

async def start_http_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"🌐 HTTP сервер запущен на порту {PORT}")

async def main():
    await start_http_server()
    print("🚀 MarvelMarket Stats Bot запущен!")
    await send_updates()

if __name__ == "__main__":
    asyncio.run(main())
