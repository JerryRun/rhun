#!/usr/bin/python3
"""Absolute host-mode requests to the private engine, without host IME changes."""
import os
import pathlib
import select
import struct
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = subprocess.Popen(['/usr/bin/python3', str(ROOT/'runtime/ime/fcitx-client.py')],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE)
buf = bytearray()
packets = []

def drain(seconds=.15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not select.select([p.stdout], [], [], max(0, deadline-time.monotonic()))[0]:
            break
        data = os.read(p.stdout.fileno(), 8192)
        if not data:
            raise AssertionError('client exited: '+str(p.poll()))
        buf.extend(data)
        while len(buf) >= 16:
            kind, gen, length, aux = struct.unpack('<4I', buf[:16])
            if len(buf) < 16+length:
                break
            payload = bytes(buf[16:16+length])
            del buf[:16+length]
            packets.append((kind, gen, payload, aux))

def request(op, key=0, cp=0, mods=0, generation=1):
    p.stdin.write(struct.pack('<8I', op, generation, key, cp, mods, 0, 0, 0))
    p.stdin.flush()
    drain()

try:
    drain(3)
    assert any(k == 0 for k,g,s,a in packets), packets
    request(2, 1)
    request(5, 1)
    assert any(k == 6 and a == 1 for k,g,s,a in packets), packets
    start = len(packets)
    for ch in 'zhongwen':
        request(1, ord(ch), ord(ch))
    assert any(k == 4 and '中文' in s.decode() for k,g,s,a in packets[start:]), packets[start:]
    # Repeating the same host state must preserve pending Pinyin composition.
    request(5, 1)
    request(1, 32, 32)
    commits = [s.decode() for k,g,s,a in packets if k == 3]
    assert commits == ['中文'], commits
    request(5, 0)
    request(5, 0)
    start = len(packets)
    for ch in 'nihao':
        request(1, ord(ch), ord(ch))
    text = ''.join(chr(struct.unpack('<5I', s)[1]) for k,g,s,a in packets[start:] if k == 1)
    assert text == 'nihao', (text, packets[start:])
    assert not any(k == 3 for k,g,s,a in packets[start:]), packets[start:]
    request(5, 1)
    request(2, 0)
    request(2, 1)
    start = len(packets)
    for ch in 'ceshi':
        request(1, ord(ch), ord(ch))
    request(1, 32, 32)
    assert any(k == 3 and s.decode() == '测试' for k,g,s,a in packets[start:]), packets[start:]
    # Host ownership prevents private toggles; unavailable host releases ownership.
    request(5, 0)
    request(4)
    start = len(packets)
    request(1, ord('a'), ord('a'))
    assert any(k == 1 for k,g,s,a in packets[start:]), packets[start:]
    request(5, 0xFFFFFFFF)
    assert any(k == 6 and a == 0xFFFFFFFF for k,g,s,a in packets), packets
    print('PASS: absolute Chinese/English state, duplicate stability, composition, focus restoration')
finally:
    p.stdin.close()
    p.wait(timeout=5)
