class CustomConnectError(Exception):
    """Обработка пользовательских исключений."""

    def __init__(self, *args):
        """Инициализация исключения."""
        if args:
            self.message = args[0]
        else:
            self.message = None

    def __str__(self):
        """Отображение исключения."""
        if self.message:
            return f'CustomConnectError: {self.message} '
        else:
            return 'Пользовательское исключение CustomConnectError'
