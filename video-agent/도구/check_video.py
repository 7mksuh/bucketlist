#!/usr/bin/env python3
"""검수담당용 자동 점검 도구

사용법:
    python3 video-agent/도구/check_video.py video-agent/작업중/<영상이름>

하는 일:
  1. 숫자로 확인할 수 있는 문제를 찾는다 (글씨 넘침, 자막 겹침, 음성 누락, 표시 위치 범위 등)
  2. 모든 장면을 한 장에 모은 <영상이름>/검수시트.png 를 만든다 (눈으로 점검용)
결과: 🔴(꼭 고칠 것) 🟡(확인 필요) ✅ 목록. 🔴가 있으면 종료 코드 1.
"""
import json
import re
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_video as mv  # noqa: E402  (같은 글꼴·배치 계산을 그대로 사용)

PX = 250  # make_video.draw_scene 의 휴대폰 왼쪽 위치
problems = []


def add(level, scene, msg):
    problems.append((level, scene, msg))


def width(s, size, role):
    f = mv._font(mv.T["제목글꼴"] if role == "head" else mv.T["본문글꼴"], size)
    return f.getlength(s)


def check_scene(n, sc, work):
    # ── 자막 ──
    lines = textwrap.wrap(sc["narration"], 30)
    for line in lines:
        if width(line, 50, "body") > mv.W - 160:
            add("🔴", n, f"자막 한 줄이 화면 밖으로 넘침: '{line}'")
    sub_top = mv.H - 24 - (44 + 62 * len(lines))
    if len(lines) >= 3:
        add("🟡", n, f"자막이 {len(lines)}줄 — 2줄 이하로 줄이기 권장")

    if not sc.get("screen"):
        for line in textwrap.wrap(sc["big"], 14):
            if width(line, 120, "head") > mv.W - 120:
                add("🔴", n, f"큰 글씨가 넘침: '{line}'")
        return

    # ── 휴대폰 화면 ──
    shot_path = work / "screens" / sc["screen"]
    if not shot_path.exists():
        add("🔴", n, f"캡처 파일 없음: screens/{sc['screen']}")
        return
    shot = Image.open(shot_path)
    k = mv.PH_H / shot.height
    pw = int(shot.width * k)
    rx = PX + pw + 130
    phone_bottom = mv.PH_Y + mv.PH_H + 14
    if sub_top < phone_bottom:
        add("🟡", n, f"자막이 휴대폰 화면 아래쪽을 {phone_bottom - sub_top:.0f}px 가림")

    for line in textwrap.wrap(sc["big"], 11):
        if rx + 140 + width(line, 96, "head") > mv.W - 40:
            add("🔴", n, f"큰 글씨가 오른쪽으로 넘침: '{line}'")
    if sc.get("sub") and rx + 140 + width(sc["sub"], 54, "body") > mv.W - 40:
        add("🔴", n, f"작은 설명이 넘침: '{sc['sub']}'")

    # ── 빨간 표시 ──
    box = sc.get("box")
    if box:
        x1, y1, x2, y2 = box
        if not (0 <= x1 < x2 <= shot.width and 0 <= y1 < y2 <= shot.height):
            add("🔴", n, f"빨간 표시 {box} 가 캡처 범위({shot.width}×{shot.height}) 밖")
        elif (x2 - x1) * k < 20 or (y2 - y1) * k < 20:
            add("🟡", n, "빨간 표시가 너무 작음 — 버튼 주변을 넉넉히 감싸기")
    elif sc.get("screen"):
        add("🟡", n, "화면은 있는데 누를 곳(box)이 없음 — 의도한 것인지 확인")

    # ── 말과 화면 글자 ──
    for name in re.findall(r'"([^"]+)"', sc["big"]):
        if name.replace(" ", "") not in sc["narration"].replace(" ", ""):
            add("🟡", n, f"큰 글씨의 메뉴 이름 '{name}' 이 내레이션에 없음 — 말과 화면이 같은지 확인")


def check_audio(n, sc, work):
    a = work / "audio" / f"{n:02d}.mp3"
    if not a.exists():
        add("🔴", n, "음성 파일 없음 (무음 4초로 만들어짐)")
        return 4.0
    t = mv.duration(a)
    chars = len(re.sub(r"\s", "", sc["narration"]))
    if t < chars / 10:      # 한국어 낭독은 보통 초당 5~8자
        add("🔴", n, f"음성 {t:.1f}초가 문장({chars}자)에 비해 너무 짧음 — 잘렸을 수 있음")
    elif t > chars / 3:
        add("🟡", n, f"음성 {t:.1f}초가 문장({chars}자)에 비해 김 — 다른 문장이 녹음됐는지 확인")
    return t + mv.PAUSE


def contact_sheet(scenes, work):
    cols, tw, th = 3, 640, 360
    rows = (len(scenes) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 50)), "white")
    d = ImageDraw.Draw(sheet)
    f = mv._font(mv.T["제목글꼴"], 30)
    for n, sc in enumerate(scenes, 1):
        fr = work / "frames" / f"{n:02d}_mark.png"
        if not fr.exists():
            fr = work / "frames" / f"{n:02d}.png"
        x, y = ((n - 1) % cols) * tw, ((n - 1) // cols) * (th + 50)
        d.text((x + 12, y + 8), f"{n}. {sc['big']}", font=f, fill="black")
        if fr.exists():
            sheet.paste(Image.open(fr).resize((tw - 8, th - 8)), (x + 4, y + 50))
        else:
            d.text((x + 20, y + 200), "장면 이미지 없음", font=f, fill="red")
    out = work / "검수시트.png"
    sheet.save(out)
    return out


def main(work):
    work = Path(work)
    data = json.loads((work / "scenes.json").read_text(encoding="utf-8"))
    scenes = data["scenes"]
    mv.load_theme(data.get("theme", "블루"))

    total = 0.0
    for n, sc in enumerate(scenes, 1):
        check_scene(n, sc, work)
        total += check_audio(n, sc, work)

    mp4 = mv.TOOLS.parent / "완성영상" / f"{work.name}.mp4"
    if not mp4.exists():
        add("🔴", "-", "완성 영상 파일이 없음")
    else:
        real = mv.duration(mp4)
        if abs(real - total) > 0.5:
            add("🔴", "-", f"영상 길이 {real:.1f}초 ≠ 예상 {total:.1f}초 — 장면이 빠졌거나 다시 만들어야 함")
        if mp4.stat().st_mtime < (work / "scenes.json").stat().st_mtime:
            add("🟡", "-", "대본(scenes.json)이 영상보다 나중에 바뀜 — 영상을 다시 만들었는지 확인")

    sheet = contact_sheet(scenes, work)

    print(f"# 자동 점검 — {work.name}  (장면 {len(scenes)}개, 예상 {total:.1f}초)")
    if not problems:
        print("✅ 자동 점검 문제 없음")
    for level, n, msg in sorted(problems, key=lambda p: (p[0] != "🔴", str(p[1]))):
        print(f"{level} 장면 {n}: {msg}")
    print(f"\n👀 눈으로 점검: {sheet}")
    print("   (빨간 표시 위치, 말과 화면 일치, 단계 순서는 반드시 직접 확인)")
    sys.exit(1 if any(p[0] == "🔴" for p in problems) else 0)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
