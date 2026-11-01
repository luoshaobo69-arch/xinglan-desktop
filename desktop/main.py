"""Run `python desktop/main.py`; the Windows release also runs without Python."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk

if __package__:
    from .core import ATLAS_SIZE, CELL, LABELS, SIZES, STATES, Player, Settings, frame_at, load_settings, look_cell, save_settings, scene_for_process, visible_position
    from .windows import foreground_process_name, no_activate
else:
    from core import ATLAS_SIZE, CELL, LABELS, SIZES, STATES, Player, Settings, frame_at, load_settings, look_cell, save_settings, scene_for_process, visible_position
    from windows import foreground_process_name, no_activate

VERSION = "1.0.0"
CLEAR = "#030609"
SPRITE_SHA256 = "99b0f0a1adf78c56b2dba9d1780ac0291ca082801986ca62fff704c41b3a60ae"


def asset_path() -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / "assets" / "xinglan-v2.png"


def data_directory() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Xinglan"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "Xinglan"


def validate_atlas(path: Path) -> dict:
    if hashlib.sha256(path.read_bytes()).hexdigest() != SPRITE_SHA256:
        raise ValueError("角色素材校验失败，请重新解压完整下载包。")
    with Image.open(path) as sprite:
        sprite.load()
        if sprite.size != ATLAS_SIZE or sprite.mode != "RGBA":
            raise ValueError("角色素材尺寸或透明通道不正确。")
        populated = 0
        for row in range(11):
            expected = len(list(STATES.values())[row][1]) if row < 9 else 8
            for column in range(8):
                alpha = sprite.crop((column * 192, row * 208, (column + 1) * 192, (row + 1) * 208)).getchannel("A")
                if (alpha.getbbox() is not None) != (column < expected):
                    raise ValueError(f"角色帧布局异常：第 {row + 1} 行第 {column + 1} 格。")
                populated += column < expected
    return {"width": 1536, "height": 2288, "frames": populated, "sha256": SPRITE_SHA256}


class PetApp:
    def __init__(self, root: tk.Tk, directory: Path, *, visible: bool = True, schedule: bool = True):
        self.root = root
        self.directory = directory
        self.config_path = directory / "settings.json"
        self.settings = load_settings(self.config_path)
        self.closed = False
        self.player = Player(self.settings.mode, time.monotonic())
        self.pause_started = time.monotonic() if self.settings.paused else None
        self._save_id = None
        self._click_id = None
        self.press = None
        self.dragging = False
        self.drag_direction = "running-right"
        self.drag_started = 0.0
        self.last_drag_x = None
        self.double_triggered = False
        self.last_cell = None
        self.photos: dict[tuple[int, int], ImageTk.PhotoImage] = {}
        validate_atlas(asset_path())
        self.atlas = Image.open(asset_path()).convert("RGBA")

        root.withdraw()
        root.title("星澜 Xinglan")
        root.configure(background=CLEAR)
        root.overrideredirect(os.name == "nt")
        root.attributes("-topmost", self.settings.topmost)
        if os.name == "nt":
            root.attributes("-transparentcolor", CLEAR)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.report_callback_exception = self.callback_error
        self.character = tk.Label(root, bg=CLEAR, borderwidth=0, highlightthickness=0, cursor="hand2")
        self.character.pack()
        self.caption = tk.Label(root, text="", bg="#122137", fg="#dcecff", padx=10, pady=4,
                                font=("Microsoft YaHei UI", 9), borderwidth=0, cursor="hand2")
        self.mode_var = tk.StringVar(value=self.settings.mode)
        self.width_var = tk.IntVar(value=self.settings.width)
        self.flags = {name: tk.BooleanVar(value=getattr(self.settings, name))
                      for name in ("automatic", "gaze", "topmost", "caption", "paused")}
        self.menu = self.create_menu()
        for widget in (self.character, self.caption):
            widget.bind("<ButtonPress-1>", self.on_press)
            widget.bind("<B1-Motion>", self.on_drag)
            widget.bind("<ButtonRelease-1>", self.on_release)
            widget.bind("<Double-Button-1>", self.on_double)
            widget.bind("<Button-3>", self.show_menu)
        self.refresh_size()
        self.refresh_caption()
        root.update_idletasks()
        x, y = visible_position(self.settings.x, self.settings.y, self.settings.width,
                                root.winfo_reqheight(), root.winfo_screenwidth(), root.winfo_screenheight())
        root.geometry(f"+{x}+{y}")
        if visible:
            self.show()
        if schedule:
            self.tick()
            self.poll_scene()

    def show(self):
        self.root.update_idletasks()  # Create our HWND while still withdrawn.
        no_activate(self.root.winfo_id())
        # On Windows, Tk's `wm state normal` uses SW_SHOWNOACTIVATE and
        # omits the restack/focus operations performed by `wm deiconify`.
        self.root.state("normal")
        self.root.update_idletasks()

    def create_menu(self) -> tk.Menu:
        menu = tk.Menu(self.root, tearoff=False, background="#11223a", foreground="#e6f0ff",
                       activebackground="#28486b", activeforeground="white", font=("Microsoft YaHei UI", 10))
        menu.add_command(label="星澜 Xinglan · 离线桌面伙伴", state="disabled")
        menu.add_separator()
        for mode, title in LABELS.items():
            menu.add_radiobutton(label=title, variable=self.mode_var, value=mode,
                                 command=lambda selected=mode: self.choose_mode(selected))
        menu.add_separator()
        menu.add_command(label="招手 / Wave", command=lambda: self.react("waving"))
        menu.add_command(label="跳跃 / Jump", command=lambda: self.react("jumping"))
        menu.add_checkbutton(label="暂停动作 / Pause", variable=self.flags["paused"], command=lambda: self.toggle("paused"))
        menu.add_separator()
        menu.add_checkbutton(label="跟随前台应用（场景提示）", variable=self.flags["automatic"], command=lambda: self.toggle("automatic"))
        menu.add_checkbutton(label="鼠标靠近时看向鼠标", variable=self.flags["gaze"], command=lambda: self.toggle("gaze"))
        menu.add_checkbutton(label="保持置顶 / Always on top", variable=self.flags["topmost"], command=lambda: self.toggle("topmost"))
        menu.add_checkbutton(label="显示下方状态提示", variable=self.flags["caption"], command=lambda: self.toggle("caption"))
        sizes = tk.Menu(menu, tearoff=False)
        for width in SIZES:
            sizes.add_radiobutton(label=f"{width} px" + (" · 默认" if width == 260 else ""), value=width,
                                  variable=self.width_var, command=lambda selected=width: self.choose_size(selected))
        menu.add_cascade(label="角色大小 / Size", menu=sizes)
        menu.add_command(label="回到屏幕右下角", command=self.reset_position)
        menu.add_separator()
        menu.add_command(label="使用说明 / Help", command=self.show_help)
        menu.add_command(label="退出 / Exit", command=self.close)
        return menu

    def show_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def show_help(self):
        messagebox.showinfo("星澜 Xinglan", "单击招手，双击跳跃；拖动角色移动。右键可选择姿态、大小、暂停或退出。\n\n"
            "“跟随前台应用”默认关闭。开启后仅在本机查看前台进程名：VS Code / PyCharm / ChatGPT → 工作，"
            "Codex → 检查，DeepSeek → 等待。它是场景提示，不代表 AI 的真实任务状态。\n\n"
            "不联网、不读取聊天或代码、不记录前台应用历史，不设置开机自启。关闭窗口即退出。\n\n"
            f"配置与日志：{self.directory}", parent=self.root)

    def photo(self, cell: tuple[int, int]) -> ImageTk.PhotoImage:
        if cell not in self.photos:
            row, col = cell
            frame = self.atlas.crop((col * CELL[0], row * CELL[1], (col + 1) * CELL[0], (row + 1) * CELL[1]))
            height = round(self.settings.width * CELL[1] / CELL[0])
            if frame.size != (self.settings.width, height):
                frame = frame.resize((self.settings.width, height), Image.Resampling.LANCZOS)
            self.photos[cell] = ImageTk.PhotoImage(frame, master=self.root)
        return self.photos[cell]

    def refresh_size(self):
        cell = self.last_cell or self.player.frame(self.animation_now())
        self.photos.clear()
        self.last_cell = None
        self.render_cell(cell)

    def animation_now(self):
        # Mode changes made while paused belong to the same frozen clock as
        # the current frame. Resuming shifts that clock exactly once.
        if self.settings.paused and self.pause_started is not None:
            return self.pause_started
        return time.monotonic()

    def render_cell(self, cell):
        if cell != self.last_cell:
            self.character.configure(image=self.photo(cell))
            self.last_cell = cell

    def refresh_caption(self):
        text = "已暂停" if self.settings.paused else LABELS[self.player.mode]
        prefix = "场景 · " if self.settings.automatic else ""
        self.caption.configure(text=f"星澜 · {prefix}{text}   |   右键设置")
        if self.settings.caption:
            self.caption.pack(pady=(0, 2))
        else:
            self.caption.pack_forget()

    def choose_mode(self, mode):
        self.settings.mode = mode
        self.settings.automatic = False
        self.flags["automatic"].set(False)
        self.mode_var.set(mode)
        self.player.set_mode(mode, self.animation_now())
        self.refresh_caption()
        self.request_save()

    def choose_size(self, width):
        self.settings.width = width
        self.width_var.set(width)
        self.refresh_size()
        self.root.update_idletasks()
        self.move_to(self.root.winfo_x(), self.root.winfo_y())
        self.request_save()

    def toggle(self, name):
        value = self.flags[name].get()
        setattr(self.settings, name, value)
        now = time.monotonic()
        if name == "topmost":
            self.root.attributes("-topmost", value)
        elif name == "paused":
            if value:
                self.pause_started = now
            elif self.pause_started is not None:
                elapsed = now - self.pause_started
                self.player.started += elapsed
                self.player.transient_started += elapsed
                self.pause_started = None
        elif name == "automatic" and not value:
            self.player.set_mode(self.settings.mode, self.animation_now())
        self.refresh_caption()
        self.request_save()

    def react(self, state):
        if not self.settings.paused:
            self.player.react(state, time.monotonic())

    def on_press(self, event):
        self.press = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())
        self.last_drag_x = event.x_root
        self.dragging = False

    def on_drag(self, event):
        if self.press is None:
            return
        dx, dy = event.x_root - self.press[0], event.y_root - self.press[1]
        if not self.dragging and dx * dx + dy * dy < 36:
            return
        if not self.dragging:
            self.drag_started = time.monotonic()
            self.cancel_click()
        self.dragging = True
        movement_x = event.x_root - (self.last_drag_x if self.last_drag_x is not None else self.press[0])
        if movement_x:
            self.drag_direction = "running-left" if movement_x < 0 else "running-right"
        self.last_drag_x = event.x_root
        self.move_to(self.press[2] + dx, self.press[3] + dy)

    def move_to(self, x, y):
        x, y = visible_position(x, y, self.settings.width, self.root.winfo_reqheight(),
                                self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        self.root.geometry(f"+{x}+{y}")
        self.settings.x, self.settings.y = x, y

    def on_release(self, _event):
        if self.dragging:
            self.request_save()
        elif self.double_triggered:
            self.double_triggered = False
        else:
            self.cancel_click()
            self._click_id = self.root.after(260, self.single_click)
        self.dragging = False
        self.press = None
        self.last_drag_x = None

    def cancel_click(self):
        if self._click_id is not None:
            self.root.after_cancel(self._click_id)
            self._click_id = None

    def single_click(self):
        self._click_id = None
        self.react("waving")

    def on_double(self, _event):
        self.cancel_click()
        self.double_triggered = True
        self.react("jumping")

    def reset_position(self):
        x, y = visible_position(None, None, self.settings.width, self.root.winfo_reqheight(),
                                self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        self.move_to(x, y)
        self.request_save()

    def tick(self):
        if self.closed:
            return
        if not self.settings.paused:
            now = time.monotonic()
            cell = self.player.frame(now)
            if self.dragging:
                cell = frame_at(self.drag_direction, (now - self.drag_started) * 1000)
            elif self.settings.gaze and self.player.mode == "idle" and self.player.transient is None:
                px, py = self.root.winfo_pointerxy()
                dx = px - (self.root.winfo_x() + self.settings.width / 2)
                dy = py - (self.root.winfo_y() + self.settings.width * .30)
                distance = dx * dx + dy * dy
                if 25 ** 2 < distance < 320 ** 2:
                    cell = look_cell(dx, dy)
            self.render_cell(cell)
        self.root.after(50 if not self.settings.paused else 200, self.tick)

    def poll_scene(self):
        if self.closed:
            return
        if self.settings.automatic and not self.settings.paused:
            process = foreground_process_name()
            if process != "__self__":
                self.player.set_mode(scene_for_process(process), time.monotonic())
                self.refresh_caption()
        self.root.after(1000, self.poll_scene)

    def request_save(self):
        if self._save_id is not None:
            self.root.after_cancel(self._save_id)
        self._save_id = self.root.after(400, self.persist)

    def persist(self):
        self._save_id = None
        try:
            save_settings(self.config_path, self.settings)
        except OSError:
            logging.exception("Could not save local preferences")

    def callback_error(self, error_type, error, traceback):
        logging.error("Desktop callback failed", exc_info=(error_type, error, traceback))
        self.close()
        messagebox.showerror("星澜遇到问题", f"请重新打开星澜。错误记录：\n{self.directory / 'xinglan.log'}")

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.persist()
        self.atlas.close()
        self.root.destroy()


def self_test(report_path: Path | None = None) -> dict:
    resource = validate_atlas(asset_path())
    scratch_parent = report_path.resolve().parent if report_path else Path.cwd()
    scratch_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xinglan-selftest-", dir=scratch_parent) as temp:
        root = tk.Tk()
        app = PetApp(root, Path(temp), visible=False, schedule=False)
        no_activate(root.winfo_id())
        visited = 0
        for row in range(11):
            count = len(list(STATES.values())[row][1]) if row < 9 else 8
            for col in range(count):
                app.render_cell((row, col))
                root.update_idletasks()
                visited += 1
        assert visited == 73 and root.winfo_exists()
        app.player.react("jumping", 1)
        assert app.player.frame(1) == (4, 0)
        assert app.player.frame(2) == (0, 0)
        assert look_cell(100, 0) == (9, 4)
        assert look_cell(0, 100) == (10, 0)
        save_settings(app.config_path, app.settings)
        assert load_settings(app.config_path) == app.settings
        app.close()
    report = {"ok": True, "version": VERSION, "frozen": bool(getattr(sys, "frozen", False)),
              "resource": resource, "tk_created": True, "rendered_frames": visited, "preferences_roundtrip": True,
              "network_used": False, "foreground_process_accessed": False}
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if sys.stdout:
        print(json.dumps(report, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Xinglan / 星澜 offline desktop companion")
    parser.add_argument("--self-test", action="store_true", help="Validate assets and render all frames in a hidden Tk window, then exit.")
    parser.add_argument("--self-test-report", type=Path, help="Write the self-test result as JSON (also works in the windowed EXE).")
    parser.add_argument("--version", action="version", version=f"Xinglan {VERSION}")
    args = parser.parse_args()
    if args.self_test:
        try:
            self_test(args.self_test_report)
            return 0
        except Exception as error:
            failure = {"ok": False, "error": str(error)}
            if args.self_test_report:
                args.self_test_report.parent.mkdir(parents=True, exist_ok=True)
                args.self_test_report.write_text(json.dumps(failure, ensure_ascii=False) + "\n", encoding="utf-8")
            if sys.stderr:
                print(str(error), file=sys.stderr)
            return 1
    directory = data_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler
        logging.basicConfig(level=logging.WARNING, handlers=[RotatingFileHandler(directory / "xinglan.log", maxBytes=256 * 1024, backupCount=1, encoding="utf-8")])
        root = tk.Tk()
        PetApp(root, directory)
        root.mainloop()
        return 0
    except Exception:
        logging.exception("Xinglan failed to start")
        try:
            messagebox.showerror("星澜无法启动", f"请保留完整解压目录后重试。\n错误记录：{directory / 'xinglan.log'}")
        except tk.TclError:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
