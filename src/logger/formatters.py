from abc import ABC, abstractmethod
from enum import Enum
import logging
from logging import Formatter, LogRecord
from typing import Any, Optional, Type

from logger.logger import TRACE


class BaseFormatter(ABC):
    @abstractmethod
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    @abstractmethod
    def prepareFormat(self, fmt: str) -> str: ...

    @abstractmethod
    def format(self, record: LogRecord) -> None: ...


class CodeLocationLogFormatter(BaseFormatter):
    def __init__(self, code_location_format: str, *args: Any, **kwargs: Any) -> None:
        self.code_location_format: str = code_location_format

    def prepareFormat(self, fmt: str) -> str:
        return fmt

    def format(self, record: LogRecord) -> None:
        record.code_location = self.code_location_format % {
            "filename": record.filename,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }


class ColoredLogFormatter(BaseFormatter):
    COLORS = {
        logging.CRITICAL: "\033[1;35m",  # bright/bold magenta
        logging.ERROR: "\033[1;31m",  # bright/bold red
        logging.WARNING: "\033[1;33m",  # bright/bold yellow
        logging.INFO: "\033[0;37m",  # white/light gray
        logging.DEBUG: "\033[1;30m",  # bright/bold dark gray
        TRACE: "\033[1;30m",  # bright/bold dark gray
    }
    NC = "\033[0m"  # no color

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def prepareFormat(self, fmt: str) -> str:
        return "%(color_on)s" + fmt + "%(color_off)s"

    def format(self, record: LogRecord) -> None:
        record.color_on = self.COLORS[record.levelno]
        record.color_off = self.NC


class FormatterName(str, Enum):
    COLORED = "colored"
    CODE_LOCATION = "code_location"


formatter_mapping: dict[FormatterName, Type[BaseFormatter]] = {
    FormatterName.COLORED: ColoredLogFormatter,
    FormatterName.CODE_LOCATION: CodeLocationLogFormatter,
}


class LogFormatterFactory(Formatter):
    def __init__(
        self, fmt: str, formatter_names: list[str], data: Optional[dict[str, Any]] = None, *args: Any, **kwargs: Any
    ) -> None:
        self.formatters: list[BaseFormatter] = []
        for formatter_name in formatter_names:
            if formatter_name not in formatter_mapping.keys():
                raise RuntimeError(f"Unknown log formatter: {formatter_name}")
            formatter: BaseFormatter = formatter_mapping[FormatterName(formatter_name)](
                **data if data is not None else {}
            )
            self.formatters.append(formatter)
        for formatter in self.formatters:
            fmt = formatter.prepareFormat(fmt)
        super(LogFormatterFactory, self).__init__(fmt, *args, **kwargs)

    def format(self, record: LogRecord) -> str:
        for formatter in self.formatters:
            formatter.format(record)
        return super(LogFormatterFactory, self).format(record)
