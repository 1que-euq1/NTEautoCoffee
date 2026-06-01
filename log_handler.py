import logging
from logging.handlers import TimedRotatingFileHandler
import os
from PyQt5.QtCore import QObject, pyqtSignal
LOG_FILE = "NTEautoCoffee.log"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_logger = None
_ui_handler = None
class UILogHandler(logging.Handler, QObject):
    
    new_log = pyqtSignal(str)
    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        ))
    def emit(self, record):
        try:
            msg = self.format(record)
            self.new_log.emit(msg)
        except Exception:
            pass
def setup_logging(log_file=None):
    
    global _logger, _ui_handler
    if _logger is not None:
        return _logger, _ui_handler
    if log_file is None:
        log_file = os.path.join(BASE_DIR, LOG_FILE)
    logger = logging.getLogger("NTEautoCoffee")
    logger.setLevel(logging.DEBUG)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(console)
    try:
        file_handler = TimedRotatingFileHandler(
            log_file, when="midnight", interval=1, backupCount=7, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(file_handler)
    except Exception:
        pass
    _ui_handler = UILogHandler()
    _ui_handler.setLevel(logging.INFO)
    logger.addHandler(_ui_handler)
    _logger = logger
    return _logger, _ui_handler
def get_logger():
    if _logger is None:
        setup_logging()
    return _logger
def get_ui_handler():
    if _ui_handler is None:
        setup_logging()
    return _ui_handler
