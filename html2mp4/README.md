# html2mp4 — HTML 모션 그래픽 → MP4 변환기

HTML로 만든 애니메이션을 **유튜브 편집용 영상 파일**로 바꿔 줍니다.
프레임 단위로 시간을 멈춰 가며 촬영하므로 컴퓨터가 느려도 **끊김 없이 부드럽게** 나옵니다.

## 1. 설치 (처음 한 번만)

1. [Node.js](https://nodejs.org) LTS 버전 설치
2. 이 폴더에서 터미널(명령 프롬프트)을 열고:

```bash
npm install
```

크롬 브라우저와 ffmpeg가 자동으로 함께 설치됩니다.

## 2. 가장 쉬운 방법 (Windows)

HTML 파일을 **`끌어다놓기.bat` 위로 드래그** → 같은 폴더에 `.mp4` 생성

## 3. 명령어 예제

```bash
# 기본: 1920x1080, 30fps, 길이 자동 감지
node html2mp4.js 인트로.html

# 길이 10초로 지정
node html2mp4.js 인트로.html -d 10

# 유튜브 쇼츠용 세로 영상 (1080x1920)
node html2mp4.js 자막.html --vertical

# 60fps로 더 부드럽게
node html2mp4.js 로고.html -f 60

# 출력 파일 이름 지정
node html2mp4.js 인트로.html -o 1강_오프닝.mp4

# 투명 배경 → 영상 위에 겹치기 (프리미어·다빈치·파이널컷)
node html2mp4.js 하단자막.html --transparent      # → 하단자막.mov

# 초록 배경 → 크로마키로 겹치기 (캡컷·브루 등)
node html2mp4.js 하단자막.html --green

# 웹폰트·이미지가 늦게 뜰 때 대기 시간 늘리기
node html2mp4.js 인트로.html --delay 3
```

## 4. 어떤 상황에 어떤 옵션?

| 용도 | 옵션 | 결과 |
|---|---|---|
| 오프닝·엔딩·장면 전환 | (없음) | `.mp4` 전체 화면 |
| 쇼츠 | `--vertical` | `.mp4` 세로 |
| 하단 자막·이름표 (프리미어 등) | `--transparent` | `.mov` 투명 배경 |
| 하단 자막·이름표 (캡컷 등) | `--green` | `.mp4` 초록 배경 |

## 5. 지원하는 애니메이션

- CSS `animation`, `transition`
- JavaScript `requestAnimationFrame`, `setTimeout`, `setInterval`
- GSAP, anime.js, Lottie 등 위 방식을 쓰는 라이브러리

## 6. 알아두기

- **길이 자동 감지**는 CSS 애니메이션 기준입니다. JS 애니메이션이나 무한 반복(`infinite`)이 있으면 `-d 초`로 직접 지정하세요. (감지 실패 시 5초)
- HTML은 화면 크기(기본 1920x1080)에 맞춰 디자인하면 가장 깔끔합니다.
- 예제: `npm run example` → `examples/title.mp4` 생성
