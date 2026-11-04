#!/usr/bin/env python3
"""scenes.json + screens/ + audio/  →  16:9 실습 영상 mp4

사용법:
    python3 video-agent/도구/make_video.py video-agent/작업중/<영상이름>

폴더 구성:
    <영상이름>/scenes.json        대본 (대본담당이 작성)
    <영상이름>/screens/01.jpg     실제 휴대폰 캡처 (캡틴이 촬영)
    <영상이름>/audio/01.mp3 ...   장면별 음성 (없으면 4초 무음)
결과:
    <영상이름>/frames/            장면 이미지
    video-agent/완성영상/<영상이름>.mp4

scenes.json 장면 항목:
    narration  성우 문장 (자막으로도 표시)
    big        큰 글씨
    sub        작은 설명 (선택)
    icon       동그라미 안 기호 (선택, 기본은 장면 번호)
    screen     screens/ 안의 캡처 파일 이름 (선택)
    box        누를 곳 [x1, y1, x2, y2] — 캡처 원본 픽셀 기준 (선택)
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (255, 248, 231)
INK = (33, 33, 33)
ACCENT = (230, 81, 0)
RED = (229, 20, 20)
SUB_BG = (33, 33, 33)
WHITE = (255, 255, 255)
PAUSE = 0.5          # 장면 끝 쉬는 시간(초)
BLINK_START = 0.6    # 빨간 표시가 나타나는 시각(초)

# 휴대폰 화면 자리
PH_Y, PH_H = 125, 735

FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgunbd.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def font(size):
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    sys.exit("한글 글꼴을 찾지 못했습니다. FONT_CANDIDATES에 글꼴 경로를 추가하세요.")


def text(d, xy, s, size, fill, bold=2, anchor="la"):
    d.text(xy, s, font=font(size), fill=fill, anchor=anchor,
           stroke_width=bold, stroke_fill=fill)


def step_mark(d, cx, cy, r, mark):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT)
    if mark in ("✓", "v", "ok"):
        d.line([(cx - r * .45, cy), (cx - r * .1, cy + r * .4), (cx + r * .5, cy - r * .4)],
               fill=WHITE, width=int(r * .22), joint="curve")
    else:
        text(d, (cx, cy), mark, int(r * 1.2), WHITE, 3, "mm")


def base_frame(i, total, title, sc):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    # 위쪽 띠: 제목 + 진도
    d.rectangle([0, 0, W, 100], fill=ACCENT)
    text(d, (60, 50), title, 50, WHITE, 2, "lm")
    text(d, (W - 60, 50), f"{i} / {total}", 44, (255, 230, 200), 1, "rm")
    # 아래쪽 자막
    lines = textwrap.wrap(sc["narration"], 30)
    box_h = 40 + 62 * len(lines)
    top = H - 20 - box_h
    d.rounded_rectangle([60, top, W - 60, H - 20], 28, fill=SUB_BG)
    for k, line in enumerate(lines):
        text(d, (W / 2, top + 20 + 62 * k), line, 52, WHITE, 1, "ma")
    return im, d


def draw_scene(i, total, title, sc, shots, out_plain, out_mark):
    """out_plain: 표시 없는 장면, out_mark: 빨간 표시가 있는 장면(없으면 None)"""
    im, d = base_frame(i, total, title, sc)
    mark = sc.get("icon") or str(i)

    if not sc.get("screen"):                      # 화면 없는 장면: 가운데 정렬
        step_mark(d, W / 2, 300, 95, mark)
        y = 450
        for line in textwrap.wrap(sc["big"], 14):
            text(d, (W / 2, y), line, 110, INK, 2, "ma"); y += 135
        if sc.get("sub"):
            text(d, (W / 2, y + 20), sc["sub"], 64, ACCENT, 2, "ma")
        im.save(out_plain)
        return False

    # 왼쪽: 휴대폰
    shot = Image.open(shots / sc["screen"]).convert("RGB")
    k = PH_H / shot.height
    pw = int(shot.width * k)
    px = 260
    d.rounded_rectangle([px - 16, PH_Y - 16, px + pw + 16, PH_Y + PH_H + 16], 40, fill=(30, 30, 30))
    im.paste(shot.resize((pw, PH_H), Image.LANCZOS), (px, PH_Y))

    # 오른쪽: 단계 + 큰 글씨 + 설명
    rx = px + pw + 140
    step_mark(d, rx + 60, 210, 60, mark)
    y = 160
    for line in textwrap.wrap(sc["big"], 11):
        text(d, (rx + 150, y), line, 92, INK, 2); y += 112
    if sc.get("sub"):
        text(d, (rx + 150, y + 10), sc["sub"], 56, ACCENT, 2); y += 80
    im.save(out_plain)

    if not sc.get("box"):
        return False

    # 빨간 표시 + 돋보기
    x1, y1, x2, y2 = sc["box"]
    m = ImageDraw.Draw(im)
    m.rounded_rectangle([px + x1 * k - 8, PH_Y + y1 * k - 8, px + x2 * k + 8, PH_Y + y2 * k + 8],
                        18, outline=RED, width=9)
    pad = 60                                       # 돋보기 영역(원본 픽셀)
    cx1, cy1 = max(0, x1 - pad), max(0, y1 - pad)
    cx2, cy2 = min(shot.width, x2 + pad), min(shot.height, y2 + pad)
    crop = shot.crop((cx1, cy1, cx2, cy2))
    top, maxw, maxh = max(y + 40, 420), W - rx - 80, 880 - max(y + 40, 420)
    s = min(maxw / crop.width, maxh / crop.height)
    crop = crop.resize((int(crop.width * s), int(crop.height * s)), Image.LANCZOS)
    im.paste(crop, (rx, top))
    m.rectangle([rx, top, rx + crop.width, top + crop.height], outline=(120, 120, 120), width=3)
    m.rounded_rectangle([rx + (x1 - cx1) * s - 6, top + (y1 - cy1) * s - 6,
                         rx + (x2 - cx1) * s + 6, top + (y2 - cy1) * s + 6],
                        22, outline=RED, width=10)
    text(m, (rx, top - 8), "확대", 40, (120, 120, 120), 1, "ld")
    im.save(out_mark)
    return True


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-2000:])


def main(work):
    work = Path(work)
    data = json.loads((work / "scenes.json").read_text(encoding="utf-8"))
    scenes, title = data["scenes"], data["title"]
    for sub in ("frames", "clips"):
        (work / sub).mkdir(exist_ok=True)

    clips = []
    for n, sc in enumerate(scenes, 1):
        plain = work / "frames" / f"{n:02d}.png"
        marked = work / "frames" / f"{n:02d}_mark.png"
        has_mark = draw_scene(n, len(scenes), title, sc, work / "screens", plain, marked)

        audio = work / "audio" / f"{n:02d}.mp3"
        if audio.exists():
            t = duration(audio) + PAUSE
            a_in, a_f = ["-i", str(audio)], f"[1:a]apad=pad_dur={PAUSE}[a]"
        else:
            t = 4.0
            a_in, a_f = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"], "[1:a]anull[a]"

        if has_mark:   # 표시 없는 화면 위에 표시 화면을 깜빡이며 겹친다
            inputs = ["-loop", "1", "-framerate", "30", "-i", str(plain), *a_in,
                      "-loop", "1", "-framerate", "30", "-i", str(marked)]
            vf = (f"[0:v][2:v]overlay=enable='gte(t,{BLINK_START})*lt(mod(t-{BLINK_START},1.2),0.9)',"
                  f"fade=in:0:8[v]")
        else:
            inputs = ["-loop", "1", "-framerate", "30", "-i", str(plain), *a_in]
            vf = "[0:v]fade=in:0:8[v]"
        mp4 = work / "clips" / f"{n:02d}.mp4"
        run(["ffmpeg", "-y", *inputs, "-filter_complex", f"{vf};{a_f}",
             "-map", "[v]", "-map", "[a]", "-t", f"{t:.2f}",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
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
