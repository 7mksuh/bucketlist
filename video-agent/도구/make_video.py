#!/usr/bin/env python3
"""scenes.json + screens/ + audio/  →  16:9 실습 영상 mp4

사용법:
    python3 video-agent/도구/make_video.py <작업폴더>                  영상 만들기
    python3 video-agent/도구/make_video.py <작업폴더> --theme 다크     테마 바꿔서
    python3 video-agent/도구/make_video.py <작업폴더> --preview 5      5번 장면 그림만 (빠른 확인)

테마: 도구/themes.json (색·글꼴). scenes.json 의 "theme" 값이 기본, 없으면 "블루".

폴더 구성:
    <작업폴더>/scenes.json        대본 (대본담당이 작성)
    <작업폴더>/screens/01.jpg     실제 휴대폰 캡처 (캡틴이 촬영)
    <작업폴더>/audio/01.mp3 ...   장면별 음성 (없으면 4초 무음)
결과:
    <작업폴더>/frames/            장면 이미지
    video-agent/완성영상/<작업폴더 이름>.mp4

scenes.json 장면 항목:
    narration  성우 문장 (자막으로도 표시)
    big        큰 글씨
    sub        작은 설명 (선택)
    icon       동그라미 안 기호 (선택, 기본은 장면 번호, 완료는 ✓)
    screen     screens/ 안의 캡처 파일 이름 (선택)
    box        누를 곳 [x1, y1, x2, y2] — 캡처 원본 픽셀 기준 (선택)
"""
import argparse
import json
import subprocess
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TOOLS = Path(__file__).resolve().parent
W, H = 1920, 1080
PAUSE = 0.5          # 장면 끝 쉬는 시간(초)
BLINK_START = 0.6    # 빨간 표시가 나타나는 시각(초)
PH_Y, PH_H = 140, 720  # 휴대폰 화면 자리
T = {}               # 현재 테마


def load_theme(name):
    themes = json.loads((TOOLS / "themes.json").read_text(encoding="utf-8"))
    if name not in themes:
        sys.exit(f"테마 '{name}' 없음. 사용 가능: {', '.join(themes)}")
    T.clear()
    T.update(themes[name])


@lru_cache(None)
def _font(file, size):
    return ImageFont.truetype(str(TOOLS / "fonts" / file), size)


def text(d, xy, s, size, color, role="body", anchor="la"):
    f = _font(T["제목글꼴"] if role == "head" else T["본문글꼴"], size)
    d.text(xy, s, font=f, fill=T[color], anchor=anchor)


def baseline_for(size, role, cy):
    """한글 글자 높이의 가운데가 cy에 오도록 하는 기준선 y"""
    f = _font(T["제목글꼴"] if role == "head" else T["본문글꼴"], size)
    _, top, _, bottom = f.getbbox("가", anchor="ls")
    return cy - (top + bottom) / 2


def step_mark(d, cx, cy, r, mark):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=T["강조"])
    fg = T["배경"]
    if mark in ("✓", "v", "ok"):
        d.line([(cx - r * .45, cy), (cx - r * .1, cy + r * .4), (cx + r * .5, cy - r * .4)],
               fill=fg, width=int(r * .22), joint="curve")
    else:
        f = _font(T["제목글꼴"], int(r * 1.15))
        x0, y0, x1, y1 = d.textbbox((0, 0), mark, font=f, anchor="ls")   # 실제 글자 모양 기준
        d.text((cx - (x0 + x1) / 2, cy - (y0 + y1) / 2), mark, font=f, fill=fg, anchor="ls")


def base_frame(i, total, title, sc):
    im = Image.new("RGB", (W, H), T["배경"])
    d = ImageDraw.Draw(im)
    # 위쪽 띠: 제목 + 진도 막대
    d.rectangle([0, 0, W, 96], fill=T["상단띠"])
    text(d, (60, 50), title, 46, "상단글자", "head", "lm")
    bx = W - 60 - total * 46
    for k in range(total):
        on = T["상단글자"] if T["상단띠"] == T["상단선"] else T["상단선"]
        c = on if k < i else T["보조"]
        d.rounded_rectangle([bx + k * 46, 42, bx + k * 46 + 36, 54], 6, fill=c)
    d.rectangle([0, 96, W * i / total, 104], fill=T["상단선"])
    # 아래쪽 자막
    lines = textwrap.wrap(sc["narration"], 30)
    box_h = 44 + 62 * len(lines)
    top = H - 24 - box_h
    d.rounded_rectangle([60, top, W - 60, H - 24], 24, fill=T["자막배경"])
    for k, line in enumerate(lines):
        text(d, (W / 2, top + 22 + 62 * k), line, 50, "자막글자", "body", "ma")
    return im, d


def draw_scene(i, total, title, sc, shots, out_plain, out_mark):
    """out_plain: 표시 없는 장면, out_mark: 빨간 표시가 있는 장면. 표시가 있으면 True"""
    im, d = base_frame(i, total, title, sc)
    mark = sc.get("icon") or str(i)

    if not sc.get("screen"):                      # 화면 없는 장면: 가운데 정렬
        step_mark(d, W / 2, 300, 90, mark)
        y = 440
        for line in textwrap.wrap(sc["big"], 14):
            text(d, (W / 2, y), line, 120, "글자", "head", "ma"); y += 145
        if sc.get("sub"):
            text(d, (W / 2, y + 10), sc["sub"], 64, "강조", "body", "ma")
        im.save(out_plain)
        return False

    # 왼쪽: 휴대폰
    shot = Image.open(shots / sc["screen"]).convert("RGB")
    k = PH_H / shot.height
    pw = int(shot.width * k)
    px = 250
    d.rounded_rectangle([px - 14, PH_Y - 14, px + pw + 14, PH_Y + PH_H + 14], 38, fill=T.get("폰테두리", "#111111"))
    im.paste(shot.resize((pw, PH_H), Image.LANCZOS), (px, PH_Y))

    # 오른쪽: 단계 + 큰 글씨 + 설명
    rx = px + pw + 130
    cy = 222                                        # 번호 동그라미와 큰 글씨 첫 줄의 가운데
    step_mark(d, rx + 55, cy, 55, mark)
    base = baseline_for(96, "head", cy)
    for line in textwrap.wrap(sc["big"], 11):
        text(d, (rx + 140, base), line, 96, "글자", "head", "ls"); base += 118
    y = base - 118 + 30                             # 마지막 줄 아래
    if sc.get("sub"):
        text(d, (rx + 140, y + 54), sc["sub"], 54, "강조", "body", "ls"); y += 80
    im.save(out_plain)

    if not sc.get("box"):
        return False

    # 빨간 표시 + 확대 화면
    x1, y1, x2, y2 = sc["box"]
    m = ImageDraw.Draw(im)
    m.rounded_rectangle([px + x1 * k - 8, PH_Y + y1 * k - 8, px + x2 * k + 8, PH_Y + y2 * k + 8],
                        16, outline=T["표시"], width=8)
    pad = 60
    cx1, cy1 = max(0, x1 - pad), max(0, y1 - pad)
    cx2, cy2 = min(shot.width, x2 + pad), min(shot.height, y2 + pad)
    crop = shot.crop((cx1, cy1, cx2, cy2))
    top = int(max(y + 56, 430))
    maxw, maxh = W - rx - 80, 860 - top
    s = min(maxw / crop.width, maxh / crop.height)
    crop = crop.resize((int(crop.width * s), int(crop.height * s)), Image.LANCZOS)
    # 그림자 + 둥근 모서리 카드
    bg = Image.new("RGB", (1, 1), T["배경"]).getpixel((0, 0))
    shade = tuple(int(c * .82) for c in bg)
    m.rounded_rectangle([rx + 8, top + 10, rx + crop.width + 8, top + crop.height + 10], 22, fill=shade)
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *crop.size], 22, fill=255)
    im.paste(crop, (rx, top), mask)
    m.rounded_rectangle([rx + (x1 - cx1) * s - 6, top + (y1 - cy1) * s - 6,
                         rx + (x2 - cx1) * s + 6, top + (y2 - cy1) * s + 6],
                        22, outline=T["표시"], width=10)
    text(m, (rx + 4, top - 12), "확대해서 보기", 36, "보조", "body", "ld")
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


def main():
    ap = argparse.ArgumentParser(description="실습 영상 만들기")
    ap.add_argument("work")
    ap.add_argument("--theme")
    ap.add_argument("--preview", type=int, help="이 번호 장면의 그림만 만든다")
    ap.add_argument("--out", help="미리보기 저장 경로")
    a = ap.parse_args()

    work = Path(a.work)
    data = json.loads((work / "scenes.json").read_text(encoding="utf-8"))
    scenes, title = data["scenes"], data["title"]
    load_theme(a.theme or data.get("theme", "블루"))
    for sub in ("frames", "clips"):
        (work / sub).mkdir(exist_ok=True)

    if a.preview:
        n = a.preview
        plain, marked = work / "frames" / f"{n:02d}.png", work / "frames" / f"{n:02d}_mark.png"
        has = draw_scene(n, len(scenes), title, scenes[n - 1], work / "screens", plain, marked)
        out = Path(a.out) if a.out else (marked if has else plain)
        if a.out:
            Image.open(marked if has else plain).save(out)
        print(f"미리보기: {out}")
        return

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
    out_dir = TOOLS.parent / "완성영상"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{work.name}.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    print(f"완성: {out}  (총 {duration(out):.1f}초, 테마 {a.theme or data.get('theme', '블루')})")


if __name__ == "__main__":
    main()
