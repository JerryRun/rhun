# Linux and WSL release

Extract this archive and run bin/rhun with a project path for the normal Linux editor.
The Windows ZIP uses the Windows system input method.

## Chinese Pinyin input in Linux and WSL

Run bin/rhun directly. Enable Settings > Editor > Enable Chinese Pinyin input.
The engine starts immediately; the choice is saved for future launches.
The normal installer also accepts --chinese-input to enable it during installation:

    curl -fsSL https://github.com/JerryRun/rhun/releases/latest/download/install.sh | sh -s -- --chinese-input

The release bundles an app-private Fcitx5 Pinyin engine, dictionaries, Python and D-Bus.
No separate setup script, launcher, system package installation or system input method
configuration is needed. The engine is off by default. --no-chinese-input or the
Settings switch turns it off. User dictionaries and state are kept in rhun's own
configuration directory under ime/. Installed runtimes live in share/rhun/.
The bundled runtime targets Linux x86-64.
Installation and headless Chinese input/save have been verified on Ubuntu 22.04,
Debian 12 and Alpine 3.24 x86-64, including private loader operation on musl.
The installer needs curl or wget, tar/gzip and a SHA-256 utility. Both GNU wget
and BusyBox wget are supported. A graphical session (such as WSLg) and usable
Chinese font fallback are still required for normal desktop use.
Ctrl+Alt+Space toggles Chinese/English; customize it in Settings.
The built-in Iosevka is used by default, with system fallback for Chinese.
Windows fonts can be configured manually and are not redistributed.
Use rhun normally whether Chinese Pinyin input is enabled or disabled.
