from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import inspect
import logging
from pathlib import Path
import sys
from typing import Any, TextIO

from loguru import logger as _backend


log = _backend


@dataclass
class OutputConfig(ABC):
    serialize: bool = False
    level: str | int = "TRACE"
    format: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __json__(self) -> dict[str, Any]:
        return {
            "serialize": self.serialize,
            "level": self.level,
            "format": self.format,
            "extra": self.extra,
        }

    @abstractmethod
    def getKwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "serialize": self.serialize,
            "level": self.level,
            **self.extra,
            "enqueue": True,
        }
        if self.format is not None:
            kwargs["format"] = self.format
        return kwargs

    @abstractmethod
    def register(self, log_dirpath: Path) -> int: ...


@dataclass
class FileOutputConfig(OutputConfig):
    filename: str = field(kw_only=True)

    def __json__(self) -> dict[str, Any]:
        result: dict[str, Any] = super().__json__()
        result.update({"filename": self.filename})
        return result

    def getKwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = super().getKwargs()
        kwargs.update({"watch": True})
        return kwargs

    def register(self, log_dirpath: Path) -> int:
        path = log_dirpath / Path(self.filename).name
        return _backend.add(path, **self.getKwargs())


@dataclass
class ConsoleOutputConfig(OutputConfig):
    sink: TextIO = sys.stderr
    colorize: bool = True

    def __json__(self) -> dict[str, Any]:
        result: dict[str, Any] = super().__json__()
        stream_name: str | None = getattr(self.sink, "name", None)
        if not isinstance(stream_name, str):
            stream_name = type(self.sink).__name__
        result.update({"sink": stream_name, "colorize": self.colorize})
        return result

    def getKwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = super().getKwargs()
        kwargs.update({"colorize": self.colorize})
        return kwargs

    def register(self, log_dirpath: Path) -> int:
        return _backend.add(self.sink, **self.getKwargs())


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            try:
                level: str | int = _backend.level(record.levelname).name
            except ValueError:
                level = record.levelno
            frame = inspect.currentframe()
            depth = 0
            while frame is not None and (depth == 0 or frame.f_code.co_filename == logging.__file__):
                frame = frame.f_back
                depth += 1
            _backend.opt(depth=depth, exception=record.exc_info).log(level, "{}", record.getMessage())
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


class LoggerManager:
    def __init__(
        self,
        log_dirpath: Path | str,
        outputs: list[OutputConfig],
    ) -> None:
        self.log_dirpath = Path(log_dirpath)
        self.outputs: list[OutputConfig] = outputs
        self._handler_ids: list[int] = []
        self._stdlib_handlers: list[logging.Handler] | None = None
        self._stdlib_level: int | None = None
        self.setup()

    def setup(self) -> None:
        _backend.remove()
        self._handler_ids.clear()
        if any(isinstance(config, FileOutputConfig) for config in self.outputs):
            self.log_dirpath.mkdir(parents=True, exist_ok=True)
        for config in self.outputs:
            self._handler_ids.append(config.register(self.log_dirpath))
        self._forward_stdlib()

    def _forward_stdlib(self) -> None:
        root = logging.getLogger()
        if self._stdlib_handlers is None:
            self._stdlib_handlers = list(root.handlers)
            self._stdlib_level = root.level
        logging.basicConfig(handlers=[_InterceptHandler()], level=logging.NOTSET, force=True)

    def _restore_stdlib(self) -> None:
        if self._stdlib_handlers is None:
            return
        root = logging.getLogger()
        root.handlers = self._stdlib_handlers
        if self._stdlib_level is not None:
            root.setLevel(self._stdlib_level)
        self._stdlib_handlers = None
        self._stdlib_level = None

    def onReload(
        self,
        log_dir: Path | str | None = None,
        outputs: list[OutputConfig] | None = None,
    ) -> None:
        if log_dir is not None:
            self.log_dirpath = Path(log_dir)
        if outputs is not None:
            self.outputs = outputs
        self.setup()

    def complete(self) -> None:
        _backend.complete()

    def close(self) -> None:
        _backend.complete()
        _backend.remove()
        self._handler_ids.clear()
        self._restore_stdlib()
