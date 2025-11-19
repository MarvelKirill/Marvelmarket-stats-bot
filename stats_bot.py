import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from telegram import Bot
from telegram.constants import ParseMode
from aiohttp import web
import logging
import traceback

# ================ НАСТРОЙКИ ================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_ANALYST_BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')
CMC_API_KEY = os.environ.get('CMC_API_KEY')
PORT = int(os.environ.get('PORT', 10001))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================ API URLs ================
CMC_CRYPTO_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
CMC_GLOBAL_URL = "https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest"
CMC_FEAR_GREED_URL = "https://api.alternative.me/fng/"

# Ключевые активы для анализа
KEY_CRYPTO_SYMBOLS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'LINK', 'MATIC']

# Хранилище предыдущих данных
previous_data = {}

# ================ ФУНКЦИИ ================

async def make_cmc_request(url, params=None):
    """Универсальная функция для запросов к CMC API"""
    headers = {
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
        'Accept': 'application/json'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Ошибка CMC API {url}: {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Ошибка запроса к CMC {url}: {e}")
        return None

async def get_crypto_data(limit=50):
    """Получаем данные по криптовалютам"""
    params = {'limit': limit, 'convert': 'USD'}
    data = await make_cmc_request(CMC_CRYPTO_URL, params)
    return data['data'] if data else []

async def get_global_metrics():
    """Получаем глобальную статистику"""
    data = await make_cmc_request(CMC_GLOBAL_URL)
    return data['data'] if data else None

async def get_fear_greed_index():
    """Получаем индекс страха и жадности"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(CMC_FEAR_GREED_URL) as response:
                data = await response.json()
                return data['data'][0]
    except Exception as e:
        logger.error(f"Ошибка получения индекса страха/жадности: {e}")
        return {'value': 50, 'value_classification': 'Neutral'}

def analyze_market_sentiment(cryptos, global_data, fear_greed):
    """Анализируем настроение рынка"""
    sentiments = []
    
    # Анализ глобальных метрик
    if global_data:
        total_change = global_data['quote']['USD']['total_market_cap_yesterday_percentage_change']
        if total_change > 3:
            sentiments.append("📈 <b>Бычий тренд</b> - рынок демонстрирует уверенный рост")
        elif total_change > 0:
            sentiments.append("↗️ <b>Умеренный рост</b> - позитивная динамика")
        elif total_change > -3:
            sentiments.append("↘️ <b>Коррекция</b> - незначительное снижение")
        else:
            sentiments.append("📉 <b>Медвежий тренд</b> - давление на рынке")
    
    # Анализ индекса страха/жадности
    fg_value = int(fear_greed['value'])
    if fg_value >= 75:
        sentiments.append("😊 <b>Экстремальная жадность</b> - инвесторы активно покупают")
    elif fg_value >= 55:
        sentiments.append("🙂 <b>Жадность</b> - позитивные настроения")
    elif fg_value >= 45:
        sentiments.append("😐 <b>Нейтрально</b> - рынок в неопределенности")
    elif fg_value >= 25:
        sentiments.append("😟 <b>Страх</b> - осторожность преобладает")
    else:
        sentiments.append("😱 <b>Экстремальный страх</b> - возможности для покупок")
    
    return sentiments

def analyze_crypto_movements(cryptos, previous_cryptos):
    """Анализируем движения криптовалют"""
    movements = []
    
    if not previous_cryptos:
        return ["📊 <b>Первая аналитика</b> - отслеживаем начальные позиции"]
    
    current_prices = {c['symbol']: c['quote']['USD']['price'] for c in cryptos}
    previous_prices = {c['symbol']: c['quote']['USD']['price'] for c in previous_cryptos}
    
    # Анализ ключевых активов
    for symbol in KEY_CRYPTO_SYMBOLS:
        if symbol in current_prices and symbol in previous_prices:
            current_price = current_prices[symbol]
            previous_price = previous_prices[symbol]
            
            if previous_price > 0:
                change_percent = ((current_price - previous_price) / previous_price) * 100
                
                if abs(change_percent) > 8:
                    direction = "🟢 выросла" if change_percent > 0 else "🔴 упала"
                    movements.append(f"• <b>{symbol}</b> {direction} на <b>{abs(change_percent):.1f}%</b>")
    
    # Если значительных движений нет
    if not movements:
        movements.append("• Рынок демонстрирует <b>стабильность</b>, значительных колебаний нет")
    
    return movements

def get_trading_recommendation(cryptos, fear_greed):
    """Генерируем торговые рекомендации"""
    recommendations = []
    fg_value = int(fear_greed['value'])
    
    # Рекомендации на основе индекса страха/жадности
    if fg_value <= 25:
        recommendations.append("💰 <b>Отличная возможность для покупок</b> - рынок в страхе")
    elif fg_value <= 45:
        recommendations.append("📥 <b>Рассмотреть накопление</b> - хорошие точки входа")
    elif fg_value >= 75:
        recommendations.append("⚠️ <b>Осторожность с покупками</b> - рынок перегрет")
    elif fg_value >= 55:
        recommendations.append("📊 <b>Выборочные покупки</b> - искать недооцененные активы")
    
    # Анализ волатильности
    price_changes = [abs(c['quote']['USD']['percent_change_24h']) for c in cryptos[:20]]
    avg_volatility = sum(price_changes) / len(price_changes)
    
    if avg_volatility > 15:
        recommendations.append("🎯 <b>Высокая волатильность</b> - используйте стоп-ордера")
    elif avg_volatility > 8:
        recommendations.append("⚡ <b>Умеренная волатильность</b> - подходит для свинг-трейдинга")
    else:
        recommendations.append("🛌 <b>Низкая волатильность</b> - рынок консолидируется")
    
    return recommendations

def get_market_insights(cryptos, global_data):
    """Получаем инсайты по рынку"""
    insights = []
    
    # Анализ объема
    if global_data:
        volume_24h = global_data['quote']['USD']['total_volume_24h']
        market_cap = global_data['quote']['USD']['total_market_cap']
        volume_ratio = (volume_24h / market_cap) * 100 if market_cap > 0 else 0
        
        if volume_ratio > 8:
            insights.append("💹 <b>Высокая активность</b> - значительный объем торгов")
        elif volume_ratio > 4:
            insights.append("📈 <b>Умеренная активность</b> - стабильный интерес")
        else:
            insights.append("📉 <b>Низкая активность</b> - рынок в ожидании")
    
    # Анализ альткойнов
    top_10_changes = [c['quote']['USD']['percent_change_24h'] for c in cryptos[:10]]
    positive_changes = sum(1 for change in top_10_changes if change > 0)
    
    if positive_changes >= 8:
        insights.append("🌟 <b>Сила альткойнов</b> - большинство в плюсе")
    elif positive_changes <= 3:
        insights.append("🌒 <b>Слабость альткойнов</b> - преобладают продажи")
    
    return insights

async def create_analyst_digest():
    """Создаем аналитический дайджест"""
    try:
        logger.info("Создание аналитического дайджеста...")
        
        # Получаем текущие данные
        current_cryptos = await get_crypto_data()
        global_data = await get_global_metrics()
        fear_greed = await get_fear_greed_index()
        
        if not current_cryptos:
            return "❌ Не удалось получить данные для анализа"
        
        # Анализируем данные
        sentiment = analyze_market_sentiment(current_cryptos, global_data, fear_greed)
        movements = analyze_crypto_movements(current_cryptos, previous_data.get('cryptos'))
        recommendations = get_trading_recommendation(current_cryptos, fear_greed)
        insights = get_market_insights(current_cryptos, global_data)
        
        # Сохраняем текущие данные для следующего сравнения
        previous_data['cryptos'] = current_cryptos
        previous_data['timestamp'] = datetime.now()
        
        # Формируем сообщение
        message = "🎯 <b>ANALYST DIGEST</b> 🎯\n\n"
        
        message += "📈 <b>НАСТРОЕНИЕ РЫНКА</b>\n"
        for item in sentiment:
            message += f"{item}\n"
        message += "\n"
        
        if movements:
            message += "⚡ <b>КЛЮЧЕВЫЕ ДВИЖЕНИЯ</b>\n"
            for movement in movements:
                message += f"{movement}\n"
            message += "\n"
        
        if insights:
            message += "🔍 <b>РЫНОЧНЫЕ ИНСАЙТЫ</b>\n"
            for insight in insights:
                message += f"{insight}\n"
            message += "\n"
        
        message += "💡 <b>ТОРГОВЫЕ ИДЕИ</b>\n"
        for recommendation in recommendations:
            message += f"{recommendation}\n"
        message += "\n"
        
        # Текущие показатели
        if global_data:
            total_cap = global_data['quote']['USD']['total_market_cap']
            total_change = global_data['quote']['USD']['total_market_cap_yesterday_percentage_change']
            message += f"📊 <b>ТЕКУЩИЕ ПОКАЗАТЕЛИ</b>\n"
            message += f"• Капитализация: ${total_cap/1_000_000_000:.1f}B\n"
            message += f"• Изменение за 24ч: {total_change:+.2f}%\n"
            message += f"• Индекс страха/жадности: {fear_greed['value']} ({fear_greed['value_classification']})\n"
        
        message += f"\n⏰ Анализ от: {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n"
        message += "\n💎 <b>MarvelMarket Analytics</b> - Умные инсайты для ваших инвестиций!"
        
        return message
        
    except Exception as e:
        logger.error(f"Ошибка в create_analyst_digest: {e}", exc_info=True)
        return f"❌ Ошибка при создании аналитического дайджеста: {str(e)}"

async def send_analyst_digest():
    """Отправляем аналитический дайджест"""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Первое сообщение при запуске
    try:
        logger.info("🚀 ПЕРВЫЙ ЗАПУСК - отправляем аналитику...")
        message = await create_analyst_digest()
        await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode=ParseMode.HTML)
        logger.info(f"✅ Первая аналитика отправлена: {datetime.now()}")
    except Exception as e:
        logger.error(f"❌ Ошибка при первой отправке: {e}")
    
    while True:
        try:
            logger.info("🔄 Подготовка аналитического дайджеста...")
            
            message = await create_analyst_digest()
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            logger.info(f"✅ Аналитический дайджест отправлен: {datetime.now()}")
            
            # Ждем 4 часа до следующего дайджеста
            logger.info("⏰ Ожидание 4 часа до следующего дайджеста...")
            await asyncio.sleep(14400)  # 4 часа
            
        except Exception as e:
            logger.error(f"❌ Ошибка в send_analyst_digest: {e}")
            await asyncio.sleep(300)  # Ждем 5 минут при ошибке

async def health_check(request):
    return web.Response(text="🎯 MarvelMarket Analyst Bot is running!")

async def start_http_server():
    """Запускаем минимальный HTTP сервер только для проверки порта"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"🌐 HTTP сервер запущен на порту {PORT} (только для проверки Render)")
    return runner

async def main():
    # ПРОВЕРЯЕМ ПЕРЕМЕННЫЕ ПРИ СТАРТЕ
    logger.info("🔍 Проверка переменных окружения...")
    logger.info(f"TELEGRAM_ANALYST_BOT_TOKEN: {'✅' if TELEGRAM_BOT_TOKEN else '❌'}")
    logger.info(f"CHANNEL_ID: {'✅' if CHANNEL_ID else '❌'}")
    logger.info(f"CMC_API_KEY: {'✅' if CMC_API_KEY else '❌'}")
    
    if not all([TELEGRAM_BOT_TOKEN, CHANNEL_ID, CMC_API_KEY]):
        logger.error("❌ Не установлены все необходимые переменные окружения!")
        exit(1)
    
    logger.info("✅ Все переменные окружения установлены")
    
    # Запускаем HTTP сервер на 30 секунд чтобы Render увидел порт
    logger.info("🔄 Запускаем HTTP сервер для проверки порта...")
    runner = await start_http_server()
    
    # Ждем 30 секунд чтобы Render успел проверить порт
    logger.info("⏳ Ожидаем 30 секунд для проверки порта Render...")
    await asyncio.sleep(30)
    
    # Останавливаем HTTP сервер - он больше не нужен
    logger.info("🛑 Останавливаем HTTP сервер...")
    await runner.cleanup()
    
    # Запускаем основную задачу
    logger.info("🎯 Запуск основной задачи отправки аналитики...")
    await send_analyst_digest()

if __name__ == "__main__":
    asyncio.run(main())
