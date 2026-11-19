# -*- coding: utf-8 -*-
"""修掉语音接口返回的 WAV 头里的假长度，并把分段旁白拼成一条整轨。

语音服务返回的 WAV 把 data chunk 的 size 写成 0xFFFFFFFF（虚假长度），
播放器/剪辑软件会显示成几万秒。这里按真实文件大小重写 RIFF 与 data 两个 size 字段。

用法：
    .\\.venv\\Scripts\\python.exe scripts\\fix_voice_wav.py docs\\voice2
"""
from __future__ import annotations

import glob
import os
import struct
import sys
import wave


def fix_one(path: str) -> float:
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError(f"{path} 不是 WAV")
    pos = 12
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        if cid == b"data":
            real = len(raw) - (pos + 8)
            out = bytearray(raw)
            struct.pack_into("<I", out, pos + 4, real)   # data 真实长度
            struct.pack_into("<I", out, 4, len(out) - 8) # RIFF 总长度
            with open(path, "wb") as f:
                f.write(bytes(out))
            return real
        pos += 8 + size + (size & 1)
    raise ValueError(f"{path} 里没有 data chunk")


def main(folder: str) -> int:
    files = sorted(glob.glob(os.path.join(folder, "[0-9][0-9]-*.wav")))
    if not files:
        print(f"{folder} 下没有 01-*.wav")
        return 1
    total = 0.0
    marks = []
    for f in files:
        fix_one(f)
        w = wave.open(f)
        dur = w.getnframes() / w.getframerate()
        marks.append((os.path.basename(f)[:-4], total, total + dur))
        total += dur
        w.close()

    out_path = os.path.join(folder, "00-完整旁白.wav")
    first = wave.open(files[0])
    params = (first.getnchannels(), first.getsampwidth(), first.getframerate())
    first.close()
    out = wave.open(out_path, "wb")
    out.setnchannels(params[0])
    out.setsampwidth(params[1])
    out.setframerate(params[2])
    for f in files:
        w = wave.open(f)
        out.writeframes(w.readframes(w.getnframes()))
        w.close()
    out.close()

    print(f"合成 {out_path}：{total:.1f}s")
    for name, a, b in marks:
        print(f"  {name:<14} {a:6.1f} → {b:6.1f}   ({int(a)//60}:{int(a)%60:02d} 起)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "docs/voice2"))
