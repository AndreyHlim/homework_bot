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
log_format = ('%(asctime)s [%(levelname)s] - Function::'
              '%(funcName)s (line %(lineno)s):: %(message)s')
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
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot: telegram.bot.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение отправлено в Telegram: {message}')
    except Exception as error:
        logger.error('Сбой при отправке сообщения в Telegram. '
                     f'Ошибка: {error}; Сообщение: {message}')


def get_api_answer(timestamp: int) -> dict:
    """Делает запрос к эндпоинту API-сервиса Практикум.Домашка."""
    try:
        homeworks = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.RequestException:
        raise ConnectionError('Не удалось выполнить запрос '
                              'к Практикум.Домашка')
    if homeworks.status_code != HTTPStatus.OK:
        raise ConnectionError('Сервис Практикум.Домашка не отвечает. '
                              f'Статус: {homeworks.status_code}')
    return homeworks.json()


def check_response(response: dict) -> None:
    """Проверяет ответ API на соответствие документации Практикум.Домашка."""
    if not isinstance(response, dict):
        raise TypeError('В функцию check_response '
                        'вместо словаря передан другой тип данных')
    if 'homeworks' not in response:
        raise KeyError('Ожидаемый ключ homeworks отсутствует в ответе API')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('В ответе API значение ключа '
                        'homeworks должно являться списком')
    if 'current_date' not in response:
        raise KeyError('Ожидаемый ключ current_date отсутствует в ответе API')


def parse_status(homework: dict) -> str:
    """Извлекает статус конкретной домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Ключа homework_name не найдено.')
    homework_name = homework.get('homework_name')

    if 'status' not in homework:
        raise KeyError('Ключа status не найдено.')
    homework_status = homework.get('status')

    if (verdict := HOMEWORK_VERDICTS.get(homework_status)) is None:
        raise ValueError('Непредвиденный статус '
                         f'домашней работы: {homework_status}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Работа чат-бота Telegramm по проверке статуса Практикум.Домашка."""
    if not check_tokens():
        logger.critical('Отсутствие обязательных переменных'
                        'окружения во время запуска бота')
        sys.exit(1)

    last_error_message_telegram = ""
    last_message_telegram = ""

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD

    while True:
        try:
            check_response(homework := get_api_answer(timestamp))
            timestamp = homework['current_date']
            if (work := homework.get('homeworks')):
                if last_message_telegram != (message := parse_status(work[0])):
                    send_message(bot, message)
                    last_error_message_telegram = ""
            else:
                logger.debug('Новые статусы работ отсутствуют.')
        except Exception as error:
            logger.error(message := f'Сбой в работе программы: {error}')
            if last_error_message_telegram != message:
                send_message(bot, message)
                last_error_message_telegram = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
