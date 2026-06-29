"""One-shot script to generate probe assets.

Generates:
- assets/probe/digit_1.png (64x64 white bg, black '1')
- assets/probe/digit_1.wav (short "one" speech on macOS, tone fallback elsewhere)

Usage: python scripts/generate_probe_assets.py
"""
from __future__ import annotations

import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
import zlib
from pathlib import Path

WIDTH = 64
HEIGHT = 64
SAMPLE_RATE = 16_000

# 8x16 bitmap font for digit "1"; 1=black pixel, 0=white pixel.
_GLYPH_1 = [
    "00011000",
    "00111000",
    "01111000",
    "11011000",
    "10011000",
    "00011000",
    "00011000",
    "00011000",
    "00011000",
    "00011000",
    "00011000",
    "00011000",
    "00011000",
    "00011000",
    "11111111",
    "11111111",
]


def _build_pixels() -> bytes:
    rows: list[bytes] = []
    scale = 3
    glyph_w = 8 * scale
    glyph_h = 16 * scale
    offset_x = (WIDTH - glyph_w) // 2
    offset_y = (HEIGHT - glyph_h) // 2
    for y in range(HEIGHT):
        row = bytearray([0])  # filter type
        for x in range(WIDTH):
            gx = (x - offset_x) // scale
            gy = (y - offset_y) // scale
            if 0 <= gx < 8 and 0 <= gy < 16 and _GLYPH_1[gy][gx] == "1":
                row.extend(b"\x00\x00\x00")
            else:
                row.extend(b"\xff\xff\xff")
        rows.append(bytes(row))
    return b"".join(rows)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _write_png(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    idat = zlib.compress(_build_pixels(), 9)
    png = sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
    out.write_bytes(png)
    print(f"wrote {out} ({len(png)} bytes, {WIDTH}x{HEIGHT})")


def _write_tone_wav(out: Path) -> None:
    """Fallback asset when platform TTS is unavailable."""
    frames = bytearray()
    duration_s = 0.55
    total_frames = int(SAMPLE_RATE * duration_s)
    for i in range(total_frames):
        t = i / SAMPLE_RATE
        envelope = min(1.0, i / 1200, (total_frames - i) / 1200)
        sample = int(0.35 * envelope * 32767 * math.sin(2 * math.pi * 440 * t))
        frames.extend(struct.pack("<h", sample))
    with wave.open(str(out), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(bytes(frames))


def _write_wav(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    say = shutil.which("say")
    afconvert = shutil.which("afconvert")
    if say and afconvert:
        with tempfile.TemporaryDirectory() as tmp:
            aiff = Path(tmp) / "digit_1.aiff"
            subprocess.run([say, "-o", str(aiff), "one"], check=True)
            subprocess.run(
                [
                    afconvert,
                    "-f",
                    "WAVE",
                    "-d",
                    "LEI16@16000",
                    str(aiff),
                    str(out),
                ],
                check=True,
            )
        print(f"wrote {out} ({out.stat().st_size} bytes, speech)")
        return
    _write_tone_wav(out)
    print(f"wrote {out} ({out.stat().st_size} bytes, tone fallback)")


def main() -> int:
    out_dir = Path(__file__).resolve().parent.parent / "assets" / "probe"
    _write_png(out_dir / "digit_1.png")
    _write_wav(out_dir / "digit_1.wav")
    return 0


if __name__ == "__main__":
    sys.exit(main())
