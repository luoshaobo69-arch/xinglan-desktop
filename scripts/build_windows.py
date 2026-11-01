"""Build a portable folder with the interpreter running this script."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", type=Path)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Build the Windows release on Windows; cross compilation is not supported.")
    root = Path(__file__).resolve().parents[1]
    dist = (args.dist_dir or root / "dist").resolve()
    work = (args.work_dir or root / ".build").resolve()
    dist.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
               "--name", "Xinglan", "--distpath", str(dist), "--workpath", str(work / "pyinstaller"),
               "--specpath", str(work), "--add-data", f"{root / 'assets/xinglan-v2.png'};assets",
               "--paths", str(root / "desktop")]
    icon = root / "assets/xinglan.ico"
    if icon.exists():
        command += ["--icon", str(icon)]
    command.append(str(root / "desktop/main.py"))
    subprocess.run(command, cwd=root, check=True)
    bundle = dist / "Xinglan"
    for filename in ("LICENSE", "ASSET-LICENSE.txt", "THIRD_PARTY_NOTICES.md"):
        source = root / filename
        if source.exists():
            shutil.copy2(source, bundle / filename)
    notices = root / "licenses" / "third-party"
    if notices.exists():
        shutil.copytree(notices, bundle / "licenses" / "third-party", dirs_exist_ok=True)
    (bundle / "START-HERE.txt").write_text(
        "星澜 Xinglan — 离线桌面伙伴\n\n"
        "请先完整解压整个文件夹，再双击 Xinglan.exe。_internal 文件夹必须保留。\n"
        "单击招手，双击跳跃，拖动移动；右键设置姿态、暂停、缩放和退出。\n"
        "不需要 Python、账号或网络。无开机自启，无聊天或代码内容读取。\n"
        "前台应用场景提示默认关闭，开启后仅在本地读取进程名。\n"
        "本地设置与错误日志保存在 %LOCALAPPDATA%\\Xinglan。\n\n"
        "Extract the entire folder, then run Xinglan.exe. Keep _internal beside the EXE.\n"
        "Click to wave, double-click to jump, drag to move. Right-click for settings and Exit.\n"
        "No Python, account, or network required. Foreground-app hints are opt-in.\n",
        encoding="utf-8")
    print(bundle)


if __name__ == "__main__":
    main()
