import logging
import sys
from datetime import datetime

class ColoredFormatter(logging.Formatter):

    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
    }
    RESET = '\033[0m'

    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)

def setup_logging(level='INFO', log_file=None, console=True):

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    log_format = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    root_logger.handlers.clear()

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_formatter = ColoredFormatter(log_format, date_format)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    logger = logging.getLogger('CTE')
    logger.info("=" * 60)
    logger.info("Chaos Traffic Engine - Logging initialized")
    logger.info(f"Log level: {level}")
    if log_file:
        logger.info(f"Log file: {log_file}")
    logger.info("=" * 60)

    return root_logger

def get_logger(name):
    return logging.getLogger(f'CTE.{name}')