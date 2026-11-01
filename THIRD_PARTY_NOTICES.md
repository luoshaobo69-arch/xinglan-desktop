# Third-party notices

Xinglan's original code is licensed under [MIT](LICENSE). The character artwork
uses [CC BY 4.0](ASSET-LICENSE.txt). Neither license replaces the licenses of the
components listed below.

| Component | Use | License and official source |
| --- | --- | --- |
| CPython and its standard library | Desktop runtime | Python Software Foundation License Version 2 and the additional notices shipped with the selected Python distribution. [Python license](https://docs.python.org/3/license.html) |
| Tcl/Tk | Tkinter window and event runtime | Tcl/Tk license terms; retain its copyright and permission notices. [Tcl/Tk terms](https://www.tcl-lang.org/software/tcltk/license.html) |
| Pillow | PNG decoding, sprite extraction and resizing | MIT-CMU; bundled image codecs may have their own licenses. Use the complete license file included in the installed Pillow wheel. [Pillow license](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| PyInstaller | Windows executable packaging | GPL 2.0 with the PyInstaller exception; selected files use Apache 2.0. The exception permits distributing generated bundles under the application's license, subject to dependency licenses. [PyInstaller license](https://pyinstaller.org/en/stable/license.html) |

The offline web demo uses browser APIs and the project's own HTML, CSS,
JavaScript and artwork. It does not fetch CDN scripts, web fonts or tracking
libraries.

## Release packaging

The initial Windows build uses CPython 3.11.5, Pillow 12.3.0 and PyInstaller
6.22.3. Exact notices copied from those installed distributions are included
under [`licenses/third-party/`](licenses/third-party/): the Python license,
the Tcl/Tk license terms shipped with its runtime, the complete Pillow wheel
license, and PyInstaller's COPYING notice. The Pillow file includes notices
for native libraries bundled in that wheel.

Windows distributions must retain that directory alongside this file.
When rebuilding with other component versions, update the notices from the
actual build environment. Do not replace Pillow's complete wheel notice with
only its short project header. Preserve any additional license files supplied
with collected binary dependencies.

Component versions should be recorded in the release build information.
The official links above describe the projects; the notices shipped with the
actual installed versions are the appropriate distribution record.

No third-party endorsement is claimed. OpenAI, ChatGPT, Codex, DeepSeek,
Windows and other referenced product names belong to their respective owners.
