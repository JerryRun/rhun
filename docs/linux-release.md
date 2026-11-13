# Linux and WSL release

Extract this archive and run bin/rhun with a project path for the normal Linux editor.
The Windows ZIP uses the Windows system input method.

## Optional private Chinese input in WSL

From the extracted directory, run:

    ./tools/setup-fcitx.sh
    ./tools/run-personal.sh /path/to/project

Setup downloads and extracts Ubuntu 24.04 amd64 Fcitx5 packages into build/fcitx5.
It does not install packages or change system/user input method settings. It requires
an existing dbus-run-session and /usr/bin/python3 with dbus and GLib bindings;
if they are missing, it stops. The runtime is not bundled in this archive.
The launcher stores its configuration and state inside build/personal in this directory.
Ctrl+Alt+Space toggles Chinese/English; customize it in Settings.
The built-in Iosevka is used by default, with system fallback for Chinese.
Windows fonts can be configured manually and are not redistributed.
Use bin/rhun directly if the private input engine is not needed.
