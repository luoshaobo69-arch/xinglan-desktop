# 一起完善星澜

欢迎提交问题、改进交互或补充翻译。建议先开一个 Issue，描述想改善的体验。

## 报告问题

请写明系统版本、星澜版本、复现步骤和预期结果。截图请只包含相关界面，日志可先移除个人路径。若是运行失败，可附上程序提示的错误日志。

## 本地开发

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python desktop/main.py
```

透明桌面窗口面向 Windows；浏览器互动演示直接打开 `docs/index.html` 即可。修改角色显示时，请保留透明图集的格子尺寸与动作顺序，避免移动或缩放造成动画跳帧。

## 提交修改

让一次 PR 解决一个清楚的问题。说明修改前后的行为、验证方式；涉及界面请提供预览。代码遵循 MIT，角色资产遵循 `ASSET-LICENSE.txt`。提交作品前请确认你有权分享它。

星澜不会读取聊天、记录键盘输入或上传使用数据。新增交互也应保持这一边界。
