import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_format = '%(asctime)s [%(levelname)s] %(message)s'
log_formatter = logging.Formatter(log_format)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

load_dotenv()
PRACTICUM_TOKEN = os.getenv('TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    if None not in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        return True
    logger.critical('Отсутствие обязательных переменных'
                    'окружения во время запуска бота')


def send_message(bot: telegram.bot.Bot, message: str):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение отправлено в Telegram: {message}')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в Telegram. {error}')


def get_api_answer(timestamp: int) -> dict:
    """Делает запрос к эндпоинту API-сервиса Практикум.Домашка."""
    try:
        homeworks = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.RequestException():
        pass
    if homeworks.status_code != HTTPStatus.OK:
        raise requests.HTTPError('Сервис Практикум.Домашка не отвечает.')
    return homeworks.json()


def check_response(response: dict) -> bool:
    """Проверяет ответ API на соответствие документации Практикум.Домашка."""
    if type(response) != dict:
        raise TypeError('В функцию check_response '
                        'вместо словаря передан другой тип данных')
    if type(response.get('homeworks')) != list:
        raise TypeError('В ответе API значение ключа '
                        'homeworks должно являться списком')
    expected_keys = {'homeworks', 'current_date'}
    if not expected_keys.issubset(response.keys()):
        raise KeyError('Ожидаемые ключи {} или {} отсутствуют '
                       'в ответе API'.format(*expected_keys))
    if response.get('homeworks'):
        return True
    logger.debug('Новые статусы отсутствуют.')


def parse_status(homework: dict) -> str:
    """Извлекает статус конерктной домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('Ключа homework_name не найдено.')
    verdict = HOMEWORK_VERDICTS.get(homework.get('status'))
    if verdict is None:
        raise ValueError('Непредвиденный статус домашней работы.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Работа чат-бота Telegramm по проверке статуса Практикум.Домашка."""
    last_error_message_telegram = ""
    while True:
        if not check_tokens():
            sys.exit()

        try:
            bot = telegram.Bot(token=TELEGRAM_TOKEN)
            timestamp = int(time.time())
            homework = get_api_answer(timestamp - RETRY_PERIOD)
            if check_response(homework):
                message = parse_status(homework.get('homeworks')[0])
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if last_error_message_telegram != message:
                send_message(bot, message)
                last_error_message_telegram = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
