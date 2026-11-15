#!/usr/bin/env python3
"""Pokes the test VM through QEMU's QMP socket.

  qmp.py shot out.png      screenshot
  qmp.py click X Y         left click at screen pixel X,Y
  qmp.py type 'text'       type text (US layout)
  qmp.py key ret|tab|...   press one key (QEMU qcode names, e.g. ctrl-alt-f2)
"""
import json
import socket
import struct
import sys
import time
from pathlib import Path

SOCK = Path(__file__).resolve().parent.parent / "build/vm/qmp.sock"
SHIFTED = {'!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
           '_': 'minus', '+': 'equal', '{': 'bracket_left', '}': 'bracket_right', ':': 'semicolon',
           '"': 'apostrophe', '<': 'comma', '>': 'dot', '?': 'slash', '|': 'backslash', '~': 'grave_accent'}
PLAIN = {' ': 'spc', '-': 'minus', '=': 'equal', '[': 'bracket_left', ']': 'bracket_right', ';': 'semicolon',
         "'": 'apostrophe', ',': 'comma', '.': 'dot', '/': 'slash', '\\': 'backslash', '`': 'grave_accent',
         '\n': 'ret'}


class QMP:
    def __init__(self):
        self.s = socket.socket(socket.AF_UNIX)
        self.s.connect(str(SOCK))
        self.f = self.s.makefile("rw")
        self.f.readline()
        self.cmd("qmp_capabilities")

    def cmd(self, name, **args):
        self.f.write(json.dumps({"execute": name, "arguments": args}) + "\n")
        self.f.flush()
        while True:
            msg = json.loads(self.f.readline())
            if "return" in msg:
                return msg["return"]
            if "error" in msg:
                sys.exit(msg["error"]["desc"])


def png_size(path):
    with open(path, "rb") as f:
        f.read(16)
        return struct.unpack(">II", f.read(8))


def keys_for(ch):
    if ch.isalpha():
        return ["shift", ch.lower()] if ch.isupper() else [ch]
    if ch.isdigit():
        return [ch]
    if ch in SHIFTED:
        return ["shift", SHIFTED[ch]]
    return [PLAIN[ch]]


def send(q, names):
    q.cmd("send-key", keys=[{"type": "qcode", "data": n} for n in names])
    time.sleep(0.05)


def main():
    q = QMP()
    op = sys.argv[1]
    if op == "shot":
        # cage only repaints damaged areas, which QEMU's screendump can miss; a mouse nudge forces a frame.
        for x, y in ((0, 0), (32767, 0), (32767, 32767), (0, 32767), (16383, 16383)):
            q.cmd("input-send-event", events=[{"type": "abs", "data": {"axis": "x", "value": x}},
                                              {"type": "abs", "data": {"axis": "y", "value": y}}])
            time.sleep(0.3)
        q.cmd("screendump", filename=str(Path(sys.argv[2]).resolve()), format="png")
    elif op == "click":
        x, y = int(sys.argv[2]), int(sys.argv[3])
        tmp = SOCK.parent / "size.png"
        q.cmd("screendump", filename=str(tmp), format="png")
        w, h = png_size(tmp)
        move = [{"type": "abs", "data": {"axis": "x", "value": x * 32767 // (w - 1)}},
                {"type": "abs", "data": {"axis": "y", "value": y * 32767 // (h - 1)}}]
        q.cmd("input-send-event", events=move)
        time.sleep(0.1)
        for down in (True, False):
            q.cmd("input-send-event", events=[{"type": "btn", "data": {"down": down, "button": "left"}}])
            time.sleep(0.05)
    elif op == "type":
        for ch in sys.argv[2]:
            send(q, keys_for(ch))
    elif op == "key":
        send(q, sys.argv[2].split("-"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
