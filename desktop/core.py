"""Portable animation and configuration rules; no desktop or network access."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import tempfile

CELL = (192, 208)
ATLAS_SIZE = (1536, 2288)
STATES = {
    "idle": (0, (280, 110, 110, 140, 140, 320)),
    "running-right": (1, (120, 120, 120, 120, 120, 120, 120, 220)),
    "running-left": (2, (120, 120, 120, 120, 120, 120, 120, 220)),
    "waving": (3, (140, 140, 140, 280)),
    "jumping": (4, (140, 140, 140, 140, 280)),
    "failed": (5, (140, 140, 140, 140, 140, 140, 140, 240)),
    "waiting": (6, (150, 150, 150, 150, 150, 260)),
    "running": (7, (120, 120, 120, 120, 120, 220)),
    "review": (8, (150, 150, 150, 150, 150, 280)),
}
LABELS = {"idle": "休息", "running": "工作", "waiting": "等待", "review": "检查", "failed": "遇到问题"}
SIZES = (192, 240, 260, 288)


def frame_at(state: str, elapsed_ms: float) -> tuple[int, int]:
    row, durations = STATES[state]
    elapsed = max(0, elapsed_ms) % sum(durations)
    for index, duration in enumerate(durations):
        if elapsed < duration:
            return row, index
        elapsed -= duration
    return row, 0


def look_cell(dx: float, dy: float) -> tuple[int, int]:
    """Screen coordinates: zero is up, positive angles turn clockwise."""
    index = int((math.degrees(math.atan2(dx, -dy)) % 360 + 11.25) // 22.5) % 16
    return 9 + index // 8, index % 8


def scene_for_process(executable: str) -> str:
    """An application hint, never a claim about an AI agent's actual activity."""
    basename = executable.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    return {
        "code.exe": "running", "code - insiders.exe": "running",
        "pycharm64.exe": "running", "pycharm.exe": "running",
        "chatgpt.exe": "running", "codex.exe": "review",
        "deepseek harness.exe": "waiting", "deepseek.exe": "waiting",
    }.get(basename, "idle")


@dataclass
class Settings:
    version: int = 1
    width: int = 260
    x: int | None = None
    y: int | None = None
    mode: str = "idle"
    automatic: bool = False
    gaze: bool = True
    topmost: bool = True
    caption: bool = True
    paused: bool = False

    @classmethod
    def from_mapping(cls, raw: object) -> "Settings":
        clean = cls()
        if not isinstance(raw, dict):
            return clean
        if type(raw.get("width")) is int and raw["width"] in SIZES:
            clean.width = raw["width"]
        for field in ("x", "y"):
            value = raw.get(field)
            if type(value) is int and -100_000 <= value <= 100_000:
                setattr(clean, field, value)
        if isinstance(raw.get("mode"), str) and raw["mode"] in LABELS:
            clean.mode = raw["mode"]
        for field in ("automatic", "gaze", "topmost", "caption", "paused"):
            if type(raw.get(field)) is bool:
                setattr(clean, field, raw[field])
        return clean


def load_settings(path: Path) -> Settings:
    try:
        if path.stat().st_size > 64 * 1024:
            return Settings()
        return Settings.from_mapping(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return Settings()


def save_settings(path: Path, settings: Settings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".settings-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(asdict(settings), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def visible_position(x: int | None, y: int | None, width: int, height: int,
                     screen_width: int, screen_height: int) -> tuple[int, int]:
    right = max(0, screen_width - width)
    bottom = max(0, screen_height - height - 48)
    return min(right, max(0, right - 24 if x is None else x)), min(bottom, max(0, bottom - 16 if y is None else y))


class Player:
    def __init__(self, mode: str = "idle", now: float = 0):
        self.mode = mode
        self.started = now
        self.transient: str | None = None
        self.transient_started = now

    def set_mode(self, mode: str, now: float) -> None:
        if mode not in LABELS:
            raise ValueError("Unknown resting/work mode")
        if self.mode != mode:
            self.mode, self.started = mode, now

    def react(self, state: str, now: float) -> None:
        if state not in ("waving", "jumping"):
            raise ValueError("Unsupported temporary reaction")
        self.transient, self.transient_started = state, now

    def frame(self, now: float) -> tuple[int, int]:
        if self.transient is not None:
            elapsed = max(0, (now - self.transient_started) * 1000)
            if elapsed < sum(STATES[self.transient][1]):
                return frame_at(self.transient, elapsed)
            self.transient = None
            self.started = now
        return frame_at(self.mode, (now - self.started) * 1000)
