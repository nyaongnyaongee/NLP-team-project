"""임시 PWA 아이콘 생성 (표준 라이브러리만 사용).  실행: python frontend/scripts/make_icons.py

정식 아이콘이 나오면 frontend/public/icons/ 와 apple-touch-icon.png 를 그 파일로 바꾸면 된다 (이 스크립트는 지워도 된다).
모양: 앱 기본 색(#4F8BFF) 정사각 바탕 + 서로 이어진 두 개의 흰 고리 ("이음"). 도안은 가운데 70% 안에 둔다 (maskable 안전 영역).
"""
import struct
import zlib
from pathlib import Path

PUBLIC = Path(__file__).resolve().parents[1] / "public"
BG = (0x4F, 0x8B, 0xFF)
FG = (0xFF, 0xFF, 0xFF)
SS = 3  # 가장자리 부드럽게: 3x3 표본


def ring_coverage(px, py, cx, cy, r, w):
    d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
    return abs(d - r) <= w / 2


def render(size: int) -> bytes:
    # 좌표는 0~1 비율. 두 고리 중심 간격 < 지름 → 서로 겹쳐 이어진 모양
    r, w = 0.17, 0.065
    centers = [(0.5 - 0.115, 0.5), (0.5 + 0.115, 0.5)]
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            hit = 0
            for sy in range(SS):
                for sx in range(SS):
                    px, py = (x + (sx + 0.5) / SS) / size, (y + (sy + 0.5) / SS) / size
                    if any(ring_coverage(px, py, cx, cy, r, w) for cx, cy in centers):
                        hit += 1
            a = hit / (SS * SS)
            row += bytes(round(BG[i] * (1 - a) + FG[i] * a) for i in range(3))
        rows.append(bytes(row))
    return b"".join(rows)


def png(size: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8비트 RGB, 투명 없음
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(render(size), 9)) + chunk(b"IEND", b"")


def main():
    (PUBLIC / "icons").mkdir(parents=True, exist_ok=True)
    targets = {
        "icons/icon-192.png": 192,
        "icons/icon-512.png": 512,
        "icons/icon-maskable-512.png": 512,
        "apple-touch-icon.png": 180,
    }
    for name, size in targets.items():
        (PUBLIC / name).write_bytes(png(size))
        print("만듦:", PUBLIC / name)


if __name__ == "__main__":
    main()
