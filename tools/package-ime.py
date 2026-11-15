#!/usr/bin/env python3
"""Build a self-contained, app-private Ubuntu 24.04 x86-64 Pinyin runtime.

Only download/extract packages and copy their shared library dependencies.
No apt install, services, shell profiles or system input method changes.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEST = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'build/ime-runtime').resolve()
PACKAGES = '''fcitx5 fcitx5-data fcitx5-modules libfcitx5utils2 libfcitx5config6
libfcitx5core7 fcitx5-pinyin fcitx5-chinese-addons-data fcitx5-module-punctuation
libime-data libime-data-language-model libimecore0 libimepinyin0
libboost-iostreams1.83.0 libxcb-ewmh2 libxcb-imdkit1 libenchant-2-2
libaspell15 libhunspell-1.7-0 dbus-daemon python3.12-minimal
libpython3.12-minimal libpython3.12-stdlib python3-dbus python3-gi
gir1.2-glib-2.0 gir1.2-girepository-2.0'''.split()


def download_packages(directory):
    # Desktop CI refreshes indexes with temporary sources. The runner's default
    # sources may name different mirrors, and its installed versions may no
    # longer exist there. Resolve and download against the same private indexes.
    with tempfile.TemporaryDirectory(prefix='rhun-ime-apt-', dir=directory.parent) as tmp:
        work = Path(tmp)
        (work / 'empty').mkdir()
        (work / 'lists/partial').mkdir(parents=True)
        (work / 'archives/partial').mkdir(parents=True)
        sources = work / 'ubuntu.list'
        sources.write_text(
            'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] '
            'https://archive.ubuntu.com/ubuntu noble main restricted universe multiverse\n'
            'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] '
            'https://archive.ubuntu.com/ubuntu noble-updates main restricted universe multiverse\n'
            'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] '
            'https://security.ubuntu.com/ubuntu noble-security main restricted universe multiverse\n')
        config = work / 'apt.conf'
        config.write_text(
            '#clear APT::Update::Pre-Invoke;\n'
            '#clear APT::Update::Post-Invoke;\n'
            '#clear APT::Update::Post-Invoke-Success;\n')
        apt = ['apt-get', '-c', str(config),
               '-o', 'Dir::Etc::SourceList=' + str(sources),
               '-o', 'Dir::Etc::SourceParts=' + str(work / 'empty'),
               '-o', 'Dir::State::lists=' + str(work / 'lists'),
               '-o', 'Dir::State::status=/dev/null',
               '-o', 'Dir::Cache::archives=' + str(work / 'archives'),
               '-o', 'Dir::Cache::pkgcache=', '-o', 'Dir::Cache::srcpkgcache=',
               '-o', 'Acquire::Retries=2', '-o', 'Acquire::http::Timeout=20',
               '-o', 'Acquire::https::Timeout=20']
        subprocess.run([*apt, '--error-on=any', 'update'], check=True)
        subprocess.run([*apt, 'download', *PACKAGES], cwd=directory, check=True)


def main():
    if subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip() != 'amd64':
        raise SystemExit('Chinese Pinyin packaging requires Ubuntu 24.04 amd64.')
    release = Path('/etc/os-release').read_text()
    if 'ID=ubuntu\n' not in release or 'VERSION_ID="24.04"' not in release:
        raise SystemExit('Chinese Pinyin packaging requires Ubuntu 24.04 amd64.')
    debs = ROOT / 'build/ime-debs'
    debs.mkdir(parents=True, exist_ok=True)
    download_packages(debs)
    DEST.mkdir(parents=True, exist_ok=True)
    for deb in sorted(debs.glob('*.deb')):
        subprocess.run(['dpkg-deb', '-x', str(deb), str(DEST)], check=True)
    lib = DEST / 'usr/lib/x86_64-linux-gnu'
    # ldd uses the archive libraries first; missing base OS libraries are copied with notices.
    targets = [DEST / 'usr/bin/fcitx5', DEST / 'usr/bin/dbus-daemon',
               DEST / 'usr/bin/python3.12']
    targets += [lib / 'fcitx5' / ('lib' + name + '.so')
                for name in ('dbus', 'dbusfrontend', 'pinyin', 'punctuation')]
    targets += list((DEST / 'usr/lib/python3').rglob('*.so'))
    targets += list((DEST / 'usr/lib/python3.12').rglob('*.so'))
    for soname in ('libglib-2.0.so.0', 'libgobject-2.0.so.0',
                   'libgirepository-1.0.so.1'):
        targets.append(Path('/usr/lib/x86_64-linux-gnu') / soname)
    notices = set()
    # Query ownership once; per-library dpkg scans are very slow on developer WSL disks.
    ownership = subprocess.check_output(['dpkg-query', '-S', '/lib/*', '/usr/lib/*'],
                                        text=True, stderr=subprocess.DEVNULL)
    owners = {}
    for line in ownership.splitlines():
        if ': ' in line:
            package, path = line.split(': ', 1)
            owners[path] = package.split(':')[0]
    copied = set()
    def copy_library(source):
        source = Path(source)
        if source.is_relative_to(DEST):
            return
        if source in copied:
            return
        copied.add(source)
        target = lib / source.name
        if not target.exists():
            shutil.copy2(source, target, follow_symlinks=True)
        package = owners.get(str(source)) or owners.get(str(source.resolve()))
        if package:
            notice = Path('/usr/share/doc') / package / 'copyright'
            if notice.is_file():
                destination = DEST / 'usr/share/doc' / package / 'copyright'
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(notice, destination)
                notices.add(package)
    env = dict(os.environ, LD_LIBRARY_PATH=str(lib))
    for binary in targets:
        if not binary.exists():
            raise RuntimeError('Missing runtime library: ' + str(binary))
        if binary.is_relative_to(Path('/usr/lib')):
            copy_library(binary)
        result = subprocess.run(['ldd', str(binary)], env=env, capture_output=True, text=True)
        if 'not found' in result.stdout:
            raise RuntimeError(str(binary) + ': ' + result.stdout)
        for match in re.finditer(r'(?:=>\s+)?(/[^\s]+)\s+\(', result.stdout):
            copy_library(match[1])
    (DEST / 'lib64').mkdir(exist_ok=True)
    shutil.copy2('/lib64/ld-linux-x86-64.so.2', DEST / 'lib64/ld-linux-x86-64.so.2',
                 follow_symlinks=True)
    # Keep all package copyright files and the license texts they reference.
    shutil.copytree('/usr/share/common-licenses', DEST / 'usr/share/common-licenses',
                    dirs_exist_ok=True)
    (DEST / 'PACKAGES').write_text('\n'.join(sorted(set(PACKAGES) | notices)) + '\n')
    (DEST / 'README').write_text('App-private Fcitx5 Pinyin, Python and D-Bus runtime.\n'
        'Ubuntu 24.04 amd64 packages; see usr/share/doc/*/copyright for licenses.\n'
        'Started only when Settings > Editor > Enable Chinese Pinyin input is on.\n')
    print('Chinese Pinyin runtime ready: ' + str(DEST))


if __name__ == '__main__':
    main()
