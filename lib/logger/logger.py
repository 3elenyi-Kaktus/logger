import logging
from logging import Logger as BasicLogger, handlers
from logging.config import dictConfig
import os
from pathlib import Path
import shutil
from uuid import uuid4

from lib.json.manager import JSONManager, toReadableJSON


__version__ = "0.2.3"

TRACE: int = 5
logging.addLevelName(TRACE, "TRACE")


def listLoggers() -> None:
    loggers: list[BasicLogger] = [logging.getLogger()]
    for name in logging.root.manager.loggerDict:
        loggers.append(logging.getLogger(name))
    logging.info(
        toReadableJSON(
            [
                {
                    "name": logger.name,
                    "level": logger.level,
                    "parent": str(logger.parent),
                    "propagate": logger.propagate,
                    "handlers": str(logger.handlers),
                    "disabled": logger.disabled,
                    "filters": str(logger.filters),
                }
                for logger in loggers
            ]
        )
    )


class MultiprocessingHandler(logging.handlers.WatchedFileHandler):
    def emit(self, record):
        try:
            msg = record.msg
            if issubclass(type(msg), BaseException):
                super(MultiprocessingHandler, self).emit(record)
                return
            if not isinstance(msg, str):
                msg = str(msg)
            while len(msg) > 3900:
                record.msg = msg[:3900] + "..."
                msg = "..." + msg[3900:]
                super(MultiprocessingHandler, self).emit(record)
            record.msg = msg
            super(MultiprocessingHandler, self).emit(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class Logger:
    """
    The global root logger class.
    """

    def __init__(
        self,
        log_config_filepath: Path,
        log_filepath: Path,
        console_log_level: int = logging.INFO,
        file_log_level: int = logging.DEBUG,
        tty_enabled: bool = True,
    ) -> None:
        """
        Initialize the global root logger.
        :param log_config_filepath: Path to the log config file
        :param log_filepath: Path to the log file
        :param console_log_level: level of logging for screen handler
        :param file_log_level: level of logging for file handler
        :param tty_enabled: Enable/Disable logging to screen
        """
        logging.info(
            f"Initializing logger. "
            f"Log config path: {log_config_filepath}, "
            f"log file path: {log_filepath}, "
            f"console log level: {console_log_level}, "
            f"file log level: {file_log_level}, "
            f"tty enabled: {tty_enabled}"
        )
        self.log_config_filepath: Path = log_config_filepath
        self.log_filepath: Path = log_filepath
        self.console_log_level: int = console_log_level
        self.file_log_level: int = file_log_level
        self.tty_enabled: bool = tty_enabled

        self.setup()

    def setup(self):
        manager: JSONManager = JSONManager()
        config: dict = manager.readJSON(self.log_config_filepath)
        if isinstance(config, list):
            raise RuntimeError(f"Expected a dict config in json file")

        # todo make checks on having desired fields in log config (without making assumptions on their existence)
        # Tune screen handler
        if not self.tty_enabled:
            config["handlers"].pop("stream")
            config["root"]["handlers"].remove("stream")
        else:
            config["handlers"]["stream"]["level"] = logging.getLevelName(self.console_log_level)

        # Tune file handler
        log_dir = Path(self.log_filepath).parent
        if not log_dir.exists():
            os.makedirs(log_dir)
        config["handlers"]["file"]["filename"] = self.log_filepath
        config["handlers"]["file"]["level"] = logging.getLevelName(self.file_log_level)

        self.optimizeFieldEvaluation(config)

        dictConfig(config)

        logging.debug("File logging initialized successfully")
        logging.info("Screen logging initialized successfully")

    @staticmethod
    def optimizeFieldEvaluation(config: dict):
        # not all LogRecord fields are actually needed (and consequently computed)
        # if certain patterns are not found in format strings, corresponding parameter evaluations are disabled

        # logging.logAsyncioTasks is not checked as current logging version seems to not have it

        formats: list[str] = []
        for formatter in config["formatters"].values():
            formats.append(formatter["fmt"])

        option_needed: bool = False
        for value in ["thread", "threadName"]:
            for fmt in formats:
                if value in fmt:
                    option_needed = True
                    break
            if option_needed:
                break
        logging.debug(f"Setting logThreads to {option_needed}")
        logging.logThreads = option_needed

        option_needed = False
        for fmt in formats:
            if "processName" in fmt:
                option_needed = True
                break
        logging.debug(f"Setting logMultiprocessing to {option_needed}")
        logging.logMultiprocessing = option_needed

        option_needed = False
        for fmt in formats:
            if "process" in fmt:
                option_needed = True
                break
        logging.debug(f"Setting logProcesses to {option_needed}")
        logging.logProcesses = option_needed

    def onReload(
        self,
        console_log_level: int,
        file_log_level: int,
        tty_enabled: bool,
    ) -> None:
        logging.info(f"Reloading logger")
        self.console_log_level = console_log_level
        self.file_log_level = file_log_level
        self.tty_enabled = tty_enabled
        self.setup()
        logging.info("Logger reloaded")

    def copyLogFile(self):
        new_filepath = self.log_filepath.parent / f"{uuid4()}.log"
        shutil.copyfile(self.log_filepath, new_filepath)
        return new_filepath
