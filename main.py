import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.utils import executor
import requests

API_TOKEN = "7713222984:AAE8YB1IVBc4O6tdlsd3kT2f2IF3QL993YU"

MINDEE_API_KEY = "c35b1aae8ca3df0dca228ceb9ac16327"
MINDEE_URL = "https://api.mindee.net/v1/products/mindee/passport/v1/predict"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def analyze_image_with_mindee(image_path):
    """Анализ изображения с использованием Mindee API."""
    headers = {
        "Authorization": f"Token {MINDEE_API_KEY}"
    }
    try:
        with open(image_path, "rb") as image_file:
            files = {"document": image_file}
            response = requests.post(MINDEE_URL, headers=headers, files=files)
        if response.status_code == 201:
            result = response.json()
            logger.info(f"Ответ JSON от Mindee API: {result}")
            
            pages = result.get("document", {}).get("inference", {}).get("pages", [])
            if pages:
                prediction = pages[0].get("prediction", {})
                mrz1 = prediction.get("mrz1", {}).get("value", "")
                mrz2 = prediction.get("mrz2", {}).get("value", "")
                
                if mrz1 and mrz2:
                    return mrz1, mrz2
                else:
                    logger.error("MRZ строки отсутствуют в данных JSON.")
                    return None, None
            else:
                logger.error("Отсутствуют страницы в JSON ответе.")
                return None, None
        else:
            logger.error(f"Ошибка API Mindee: {response.status_code} - {response.text}")
            return None, None
    except Exception as e:
        logger.error(f"Ошибка при отправке запроса в Mindee: {e}")
        return None, None

def parse_mrz(mrz_line1, mrz_line2):
    """Парсинг данных MRZ строк."""
    document_type = mrz_line1[0]
    country_code = mrz_line1[2:5]
    surname = mrz_line1[5:].split('<<')[0].replace('<', ' ').strip()
    name_parts = mrz_line1[5:].split('<<')[1].split('<')
    first_name = name_parts[0].strip()
    dob_formatted = datetime.strptime(mrz_line2[13:19], "%y%m%d").strftime("%d%b%y").lower()
    expiration_formatted = datetime.strptime(mrz_line2[21:27], "%y%m%d").strftime("%d%b%y").lower()
    return f"{document_type}/{country_code.lower()}/{mrz_line2[:9].strip('<')}/{country_code.lower()}/{dob_formatted}/{mrz_line2[20].lower()}/{expiration_formatted}/{surname}/{first_name}".upper()

@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    """Приветственное сообщение."""
    await message.reply("Привет! Отправьте мне фото с MRZ или текст с двумя строками MRZ, и я распарсю данные.")

@dp.message_handler(content_types=["photo"])
async def handle_photo(message: types.Message):
    """Обработка отправленного изображения."""
    image_path = "temp_image.jpg"
    await message.photo[-1].download(destination_file=image_path)
    await message.reply("Идет распознавание текста, пожалуйста, подождите...")
    try:
        mrz1, mrz2 = await analyze_image_with_mindee(image_path)
        os.remove(image_path)
        if mrz1 and mrz2:
            try:
                result = parse_mrz(mrz1, mrz2)
                await message.reply(f"Распарсенные данные MRZ:\n<code>SSR DOCS CZ HK1 {result}</code>", parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(f"Ошибка при парсинге MRZ: {e}")
                await message.reply(f"Ошибка при парсинге MRZ: {e}")
        else:
            await message.reply("Не удалось найти данные MRZ на фото. Убедитесь, что на фото видны строки MRZ.")
    except Exception as e:
        logger.error(f"Ошибка обработки изображения: {e}")
        await message.reply(f"Ошибка обработки изображения: {e}")

@dp.message_handler(lambda message: len(message.text.splitlines()) == 2)
async def parse_mrz_handler(message: types.Message):
    """Обработка текстовых данных MRZ."""
    lines = message.text.strip().splitlines()
    try:
        result = parse_mrz(lines[0], lines[1])
        await message.reply(f"Распарсенные данные MRZ:\n<code>{result}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Ошибка при парсинге MRZ: {e}")
        await message.reply(f"Ошибка при парсинге MRZ: {e}")

if __name__ == "__main__":
    logger.info("Запуск бота...")
    executor.start_polling(dp, skip_updates=True)
