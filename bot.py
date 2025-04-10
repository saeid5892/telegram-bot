import asyncio
import logging
import requests
from bs4 import BeautifulSoup  # برای وب اسکرپینگ
from telegram import Bot
from telegram.error import TelegramError
import time
import sys

# تنظیمات اصلی
TOKEN = "8001091966:AAE1VH5ySDWqEmxtH2SUCQeNawLTDpOPnQI"  # توکن مستقیم تعریف شده است
CHANNEL_ID = "@sv_btc2025"

# API ها
USD_TO_IRR_API = "https://api.exchangerate-api.com/v4/latest/USD"  # نرخ رسمی
CRYPTO_API_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd"
TETHER_IRR_API = "https://api.nobitex.ir/v2/orderbook/USDTIRT"  # قیمت تتر از نوبیتکس
TGJU_URL = "https://en.tgju.org/profile/sekee"  # آدرس سایت قیمت سکه طلای تمام امامی

# تنظیمات پیشرفته
REQUEST_TIMEOUT = 10  # ثانیه
UPDATE_INTERVAL = 5  # دقیقه

# تنظیمات لاگینگ با کدگذاری مناسب
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),  # برای ذخیره لاگ‌ها در فایل
        logging.StreamHandler(sys.stdout)  # نمایش در کنسول
    ]
)

class PriceBot:
    def __init__(self):
        if not TOKEN:
            raise ValueError("توکن ربات تلگرام تنظیم نشده است! لطفاً توکن معتبر را وارد کنید.")
        self.bot = Bot(token=TOKEN)
        self.session = requests.Session()

    async def get_tether_price(self):
        """دریافت قیمت واقعی تتر از بازار ایران"""
        try:
            response = self.session.get(TETHER_IRR_API, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            return float(data.get("lastTradePrice", 0))  # قیمت آخرین معامله یا 0 به صورت پیش‌فرض
        except requests.exceptions.Timeout:
            logging.error("زمان درخواست قیمت تتر تمام شد.")
        except requests.exceptions.RequestException as e:
            logging.error(f"خطا در دریافت قیمت تتر: {str(e)}")
        return None

    async def get_crypto_prices(self):
        """دریافت قیمت ارزهای دیجیتال"""
        try:
            response = self.session.get(CRYPTO_API_URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            return data.get("bitcoin", {}).get("usd", None), data.get("ethereum", {}).get("usd", None)
        except requests.exceptions.Timeout:
            logging.error("زمان درخواست قیمت ارزهای دیجیتال تمام شد.")
        except requests.exceptions.RequestException as e:
            logging.error(f"خطا در دریافت قیمت ارزهای دیجیتال: {str(e)}")
        return None, None

    async def format_price(self, value, currency="USD"):
        """قالب‌بندی قیمت‌ها"""
        if value is None:
            return "نامعلوم"
        return f"{value:,.2f} {currency}" if currency == "USD" else f"{value:,.0f} ریال"

    async def send_update(self):
        """تهیه و ارسال گزارش"""
        try:
            # دریافت قیمت‌ها به صورت همزمان
            tether_price, crypto_prices = await asyncio.gather(
                self.get_tether_price(),
                self.get_crypto_prices()
            )

            btc_usd, eth_usd = crypto_prices or (None, None)

            # محاسبه قیمت‌ها
            btc_irr = btc_usd * tether_price if all([btc_usd, tether_price]) else None
            eth_irr = eth_usd * tether_price if all([eth_usd, tether_price]) else None

            # ساخت پیام
            message = (
                "📊 به‌روزرسانی قیمت‌ها:\n\n"
                f"💎 بیت‌کوین:\n"
                f"  {await self.format_price(btc_usd)}\n"
                f"  {await self.format_price(btc_irr, 'IRR')}\n\n"
                f"🔷 اتریوم:\n"
                f"  {await self.format_price(eth_usd)}\n"
                f"  {await self.format_price(eth_irr, 'IRR')}\n\n"
                f"💵 تتر (USDT):\n"
                f"  قیمت بازار: {await self.format_price(tether_price, 'IRR')}\n\n"
                f"🔄 آخرین به‌روزرسانی: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await self.bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                disable_web_page_preview=True
            )
            logging.info("پیام با موفقیت ارسال شد.")

        except TelegramError as e:
            logging.error(f"خطا در ارسال پیام به تلگرام: {str(e)}")
        except Exception as e:
            logging.error(f"خطا در ارسال به‌روزرسانی: {str(e)}")

    async def run(self):
        """اجرای اصلی ربات"""
        try:
            # بررسی اتصال
            await self.bot.get_chat(CHANNEL_ID)
            logging.info(f"ربات به کانال {CHANNEL_ID} متصل شد.")

            # اجرای اولیه
            await self.send_update()

            # حلقه اصلی
            while True:
                await asyncio.sleep(UPDATE_INTERVAL * 60)
                await self.send_update()

        except TelegramError as e:
            logging.error(f"خطا در اتصال به تلگرام: {str(e)}")
        except Exception as e:
            logging.error(f"خطای بحرانی: {str(e)}")
        finally:
            self.session.close()  # بستن جلسه درخواست‌ها

if __name__ == "__main__":
    bot = PriceBot()

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logging.info("ربات متوقف شد.")
    except Exception as e:
        logging.error(f"خطای بحرانی: {str(e)}")
