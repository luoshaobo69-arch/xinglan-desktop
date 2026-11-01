"""Behavior and portability checks. No client apps or user configuration are accessed."""
from pathlib import Path
import json
import math
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from desktop.core import LABELS, STATES, Player, Settings, frame_at, load_settings, look_cell, save_settings, scene_for_process, visible_position
from desktop.main import PetApp, asset_path, validate_atlas


class MotionTests(unittest.TestCase):
    def test_temporary_reactions_resume_selected_work_mode(self):
        player = Player("review", 10)
        player.react("waving", 11)
        self.assertEqual(player.frame(11), (3, 0))
        player.react("jumping", 11.1)
        self.assertEqual(player.frame(11.1), (4, 0))
        self.assertEqual(player.frame(12.0), (8, 0))
        self.assertIsNone(player.transient)

    def test_long_scheduler_delays_never_select_unused_cells(self):
        for state, (row, durations) in STATES.items():
            for elapsed in (-1, 0, 1, sum(durations) - .001, sum(durations), 10 ** 12):
                observed_row, frame = frame_at(state, elapsed)
                self.assertEqual(observed_row, row)
                self.assertIn(frame, range(len(durations)))
        self.assertEqual(frame_at("waving", 140), (3, 1))
        self.assertEqual(frame_at("waving", 700), (3, 0))

    def test_gaze_covers_all_sixteen_clockwise_directions(self):
        cells = []
        for index in range(16):
            radians = math.radians(index * 22.5)
            cell = look_cell(math.sin(radians) * 100, -math.cos(radians) * 100)
            cells.append(cell)
            self.assertEqual(cell, (9 + index // 8, index % 8))
        self.assertEqual(len(set(cells)), 16)

    def test_unknown_states_are_rejected(self):
        player = Player()
        with self.assertRaises(ValueError):
            player.set_mode("shell", 0)
        with self.assertRaises(ValueError):
            player.react("running", 0)


class SettingsTests(unittest.TestCase):
    def test_hostile_or_old_configuration_falls_back_per_field(self):
        for data in (None, [], "settings", 9):
            self.assertEqual(Settings.from_mapping(data), Settings())
        observed = Settings.from_mapping({"width": True, "x": 10 ** 15, "y": "400",
                                          "mode": [], "automatic": "false", "paused": 1,
                                          "gaze": False, "caption": True, "unknown": "ignored"})
        self.assertEqual(observed.width, 260)
        self.assertIsNone(observed.x)
        self.assertIsNone(observed.y)
        self.assertEqual(observed.mode, "idle")
        self.assertFalse(observed.automatic)
        self.assertFalse(observed.paused)
        self.assertFalse(observed.gaze)

    def test_unicode_path_roundtrip_and_broken_json(self):
        with tempfile.TemporaryDirectory(prefix="prefs-test-", dir=ROOT / "tests") as temporary:
            path = Path(temporary) / "中文用户" / "settings.json"
            wanted = Settings(width=240, x=800, y=500, mode="waiting", automatic=True)
            save_settings(path, wanted)
            self.assertEqual(load_settings(path), wanted)
            self.assertEqual(list(path.parent.iterdir()), [path])
            path.write_text('{"x":', encoding="utf-8")
            self.assertEqual(load_settings(path), Settings())
            path.write_bytes(b"x" * (64 * 1024 + 1))
            self.assertEqual(load_settings(path), Settings())

    def test_display_change_cannot_restore_character_off_screen(self):
        self.assertEqual(visible_position(8000, 9000, 260, 310, 1920, 1080), (1660, 722))
        self.assertEqual(visible_position(-800, -900, 260, 310, 1920, 1080), (0, 0))
        self.assertEqual(visible_position(None, None, 260, 310, 100, 100), (0, 0))


class PausedInteractionTests(unittest.TestCase):
    def paused_app(self):
        # Exercise real callbacks without creating Tk or accessing the desktop.
        app = PetApp.__new__(PetApp)
        app.settings = Settings(paused=True)
        app.pause_started = 10.0
        app.player = Player("idle", 0)
        app.mode_var = Mock()
        app.flags = {name: Mock() for name in ("paused", "automatic")}
        app.refresh_caption = Mock()
        app.request_save = Mock()
        return app

    def resume(self, app):
        app.flags["paused"].get.return_value = False
        with patch("desktop.main.time.monotonic", return_value=30.0):
            app.toggle("paused")

    def test_mode_change_during_pause_does_not_add_a_second_pause(self):
        app = self.paused_app()
        with patch("desktop.main.time.monotonic", return_value=20.0):
            app.choose_mode("running")
        self.resume(app)
        self.assertEqual(app.player.started, 30.0)
        self.assertEqual(app.player.frame(30.0), (7, 0))
        self.assertEqual(app.player.frame(30.121), (7, 1))

    def test_leaving_automatic_mode_while_paused_uses_frozen_clock(self):
        app = self.paused_app()
        app.settings.mode = "review"
        app.settings.automatic = True
        app.player.set_mode("running", 3)
        app.flags["automatic"].get.return_value = False
        with patch("desktop.main.time.monotonic", return_value=20.0):
            app.toggle("automatic")
        self.resume(app)
        self.assertEqual(app.player.started, 30.0)
        self.assertEqual(app.player.frame(30.151), (8, 1))

    def test_resizing_paused_character_preserves_the_displayed_pose(self):
        app = self.paused_app()
        app.last_cell = (8, 3)
        app.photos = {app.last_cell: object()}
        app.render_cell = Mock()
        app.refresh_size()
        app.render_cell.assert_called_once_with((8, 3))
        self.assertEqual(app.photos, {})

    def test_drag_reversal_changes_pose_before_crossing_original_position(self):
        app = self.paused_app()
        app.press = (100, 100, 500, 500)
        app.last_drag_x = 200
        app.dragging = True
        app.drag_direction = "running-right"
        app.move_to = Mock()
        app.on_drag(SimpleNamespace(x_root=150, y_root=100))
        self.assertEqual(app.drag_direction, "running-left")
        app.move_to.assert_called_once_with(550, 500)

    def test_nonactivating_style_is_set_before_showing_own_window(self):
        app = self.paused_app()
        events = []
        app.root = SimpleNamespace(
            update_idletasks=lambda: events.append("layout"),
            winfo_id=lambda: 123,
            state=lambda value: events.append(("state", value)))
        with patch("desktop.main.no_activate", side_effect=lambda hwnd: events.append(("no_activate", hwnd))):
            app.show()
        self.assertEqual(events, ["layout", ("no_activate", 123), ("state", "normal"), "layout"])


class SceneAndResourceTests(unittest.TestCase):
    def test_only_exact_known_process_basenames_match(self):
        self.assertEqual(scene_for_process(r"D:\Apps\Code.exe"), "running")
        self.assertEqual(scene_for_process("PYCHARM64.EXE"), "running")
        self.assertEqual(scene_for_process("Codex.exe"), "review")
        self.assertEqual(scene_for_process("DeepSeek Harness.exe"), "waiting")
        for name in ("", "mycode.exe", "deepseek-document.txt", "not-codex.exe", "chrome.exe"):
            self.assertEqual(scene_for_process(name), "idle")

    def test_distributed_sprite_is_exact_approved_asset(self):
        self.assertEqual(asset_path(), ROOT / "assets/xinglan-v2.png")
        report = validate_atlas(asset_path())
        self.assertEqual(report["frames"], 73)
        self.assertEqual((report["width"], report["height"]), (1536, 2288))


if __name__ == "__main__":
    unittest.main(verbosity=2)
