from dataclasses import dataclass, field
import inspect
import logging
from pathlib import Path
import sys
from typing import Any, TextIO

from loguru import logger as _backend


log = _backend


@dataclass
class OutputConfig:
    serialize: bool = False
    level: str | int = "TRACE"
    format: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FileOutputConfig(OutputConfig):
    filename: str = field(kw_only=True)


@dataclass
class ConsoleOutputConfig(OutputConfig):
    sink: TextIO = sys.stderr
    colorize: bool = True
    level: str | int = "INFO"


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
        log_dir: Path | str,
        outputs: list[FileOutputConfig | ConsoleOutputConfig],
    ) -> None:
        self.log_dir = Path(log_dir)
        self.outputs: list[FileOutputConfig | ConsoleOutputConfig] = outputs
        self._handler_ids: list[int] = []
        self._stdlib_handlers: list[logging.Handler] | None = None
        self._stdlib_level: int | None = None
        self.setup()

    def _sink_kwargs(self, config: OutputConfig, **overrides: Any) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "level": config.level,
            "serialize": config.serialize,
            **config.extra,
            "enqueue": True,
            **overrides,
        }
        if config.format is not None:
            kwargs["format"] = config.format
        return kwargs

    def _add_output(self, config: FileOutputConfig | ConsoleOutputConfig) -> None:
        if isinstance(config, ConsoleOutputConfig):
            handler_id = _backend.add(
                config.sink,
                **self._sink_kwargs(config, colorize=config.colorize),
            )
        else:
            path = self.log_dir / Path(config.filename).name
            handler_id = _backend.add(path, **self._sink_kwargs(config, watch=True))
        self._handler_ids.append(handler_id)

    def setup(self) -> None:
        _backend.remove()
        self._handler_ids.clear()
        if any(isinstance(config, FileOutputConfig) for config in self.outputs):
            self.log_dir.mkdir(parents=True, exist_ok=True)
        for config in self.outputs:
            self._add_output(config)
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
        outputs: list[FileOutputConfig | ConsoleOutputConfig] | None = None,
    ) -> None:
        if log_dir is not None:
            self.log_dir = Path(log_dir)
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
