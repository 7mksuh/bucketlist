#!/usr/bin/env python3
"""scenes.json + audio/*.mp3  →  세로 쇼츠 mp4

사용법:
    python3 video-agent/도구/make_video.py video-agent/작업중/<영상이름>

폴더 구성:
    <영상이름>/scenes.json        대본 (대본담당이 작성)
    <영상이름>/audio/01.mp3 ...   장면별 음성 (없으면 4초 무음)
결과:
    <영상이름>/frames/01.png ...  장면 이미지
    video-agent/완성영상/<영상이름>.mp4
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG = (255, 248, 231)        # 따뜻한 미색
INK = (33, 33, 33)
ACCENT = (230, 81, 0)       # 주황
SUB_BG = (33, 33, 33)
SUB_INK = (255, 255, 255)
PAUSE = 0.5                 # 장면 끝 쉬는 시간(초)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",                       # 윈도우
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",          # 맥
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",  # 리눅스
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def font(size):
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    sys.exit("한글 글꼴을 찾지 못했습니다. FONT_CANDIDATES에 글꼴 경로를 추가하세요.")


def center_text(d, y, text, f, fill, bold=0):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill, stroke_width=bold, stroke_fill=fill)


def draw_scene(i, total, title, sc, out):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    # 위쪽: 영상 제목 + 진도
    d.rectangle([0, 0, W, 230], fill=ACCENT)
    center_text(d, 60, title, font(64), (255, 255, 255), bold=2)
    center_text(d, 150, f"{i} / {total}", font(44), (255, 230, 200))

    # 가운데: 단계 동그라미 + 큰 글씨 + 설명
    cy = 560
    d.ellipse([W / 2 - 110, cy - 110, W / 2 + 110, cy + 110], fill=ACCENT)
    mark = sc.get("icon") or str(i)
    if mark in ("✓", "v", "V", "ok"):   # 글꼴에 없는 기호는 직접 그린다
        d.line([(W / 2 - 55, cy), (W / 2 - 12, cy + 45), (W / 2 + 60, cy - 50)],
               fill=(255, 255, 255), width=26, joint="curve")
    else:
        center_text(d, cy - 75, mark, font(130), (255, 255, 255), bold=3)

    y = 760
    for line in textwrap.wrap(sc["big"], 8):
        center_text(d, y, line, font(130), INK, bold=4)
        y += 165
    if sc.get("sub"):
        y += 30
        for line in textwrap.wrap(sc["sub"], 14):
            center_text(d, y, line, font(72), ACCENT, bold=2)
            y += 95

    # 아래쪽: 자막 (내레이션)
    lines = textwrap.wrap(sc["narration"], 15)
    box_h = 70 + 88 * len(lines)
    top = H - 140 - box_h
    d.rounded_rectangle([50, top, W - 50, top + box_h], 36, fill=SUB_BG)
    y = top + 35
    for line in lines:
        center_text(d, y, line, font(64), SUB_INK, bold=1)
        y += 88

    im.save(out)


def duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def main(work):
    work = Path(work)
    data = json.loads((work / "scenes.json").read_text(encoding="utf-8"))
    scenes, title = data["scenes"], data["title"]
    (work / "frames").mkdir(exist_ok=True)
    (work / "clips").mkdir(exist_ok=True)

    clips = []
    for n, sc in enumerate(scenes, 1):
        png = work / "frames" / f"{n:02d}.png"
        mp4 = work / "clips" / f"{n:02d}.mp4"
        draw_scene(n, len(scenes), title, sc, png)

        audio = work / "audio" / f"{n:02d}.mp3"
        if audio.exists():
            t = duration(audio) + PAUSE
            a_in = ["-i", str(audio)]
            a_map = ["-af", f"apad=pad_dur={PAUSE}"]
        else:
            t = 4.0
            a_in = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            a_map = []
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", str(png), *a_in,
             *a_map, "-vf", "fade=in:0:8", "-t", f"{t:.2f}",
             "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "44100", "-ac", "2", str(mp4)])
        clips.append(mp4)
        print(f"장면 {n}/{len(scenes)} 완료 ({t:.1f}초)")

    lst = work / "clips" / "list.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    out_dir = Path(__file__).resolve().parent.parent / "완성영상"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{work.name}.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    print(f"완성: {out}  (총 {duration(out):.1f}초)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
