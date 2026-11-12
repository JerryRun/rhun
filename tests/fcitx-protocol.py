#!/usr/bin/python3
"""Exercise the actual private engine and client, without system IME changes."""
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
    request(1, 32, 32, 4)
    for ch in 'zhongwen':
        request(1, ord(ch), ord(ch))
    panels = [s.decode() for k,g,s,a in packets if k == 4 and s]
    assert any('中文' in s for s in panels), panels
    assert not any(k == 3 for k,g,s,a in packets), packets
    first_page = panels[-1]
    request(1, 0xff56)
    next_page = [s.decode() for k,g,s,a in packets if k == 4 and s][-1]
    assert next_page != first_page, (first_page, next_page)
    request(1, 0xff55)
    assert [s.decode() for k,g,s,a in packets if k == 4 and s][-1] == first_page
    request(1, 32, 32)
    commits = [s.decode() for k,g,s,a in packets if k == 3]
    assert commits == ['中文'], commits
    for ch in 'ceshi':
        request(1, ord(ch), ord(ch))
    request(1, 0xff1b)
    request(1, 32, 32, 4)
    start = len(packets)
    request(1, ord('x'), ord('x'))
    assert any(k == 1 and struct.unpack('<5I', s)[1] == ord('x')
               for k,g,s,a in packets[start:]), packets[start:]
    print('PASS: private engine, preedit/candidates, paging, Chinese commit, cancel and English toggle')
finally:
    p.stdin.close()
    p.wait(timeout=5)
