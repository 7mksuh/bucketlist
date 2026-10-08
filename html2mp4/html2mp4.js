#!/usr/bin/env node
// HTML 모션 그래픽 → MP4 변환기
// 사용법: node html2mp4.js 애니메이션.html [옵션]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// ffmpeg: 함께 설치된 ffmpeg-static 우선, 없으면 시스템 ffmpeg
let FFMPEG = 'ffmpeg';
try { FFMPEG = require('ffmpeg-static') || FFMPEG; } catch {}

const HELP = `
사용법: node html2mp4.js <입력.html> [옵션]

옵션:
  -o, --out <파일>      출력 파일 (기본: 입력이름.mp4)
  -d, --duration <초>   영상 길이 (기본: CSS 애니메이션 길이 자동 감지, 없으면 5초)
  -f, --fps <숫자>      초당 프레임 (기본: 30)
  -w, --width <px>      가로 (기본: 1920)
  -h, --height <px>     세로 (기본: 1080)
      --vertical        쇼츠용 세로 1080x1920
      --transparent     투명 배경 .mov (프리미어/다빈치/파이널컷 오버레이용)
      --green           초록 배경 (캡컷/브루 크로마키용)
      --delay <초>      녹화 시작 전 대기 (폰트·이미지 로딩용, 기본: 0.5)
`;

function parseArgs(argv) {
  const o = { fps: 30, width: 1920, height: 1080, delay: 0.5 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i], next = () => argv[++i];
    if (a === '-o' || a === '--out') o.out = next();
    else if (a === '-d' || a === '--duration') o.duration = parseFloat(next());
    else if (a === '-f' || a === '--fps') o.fps = parseInt(next(), 10);
    else if (a === '-w' || a === '--width') o.width = parseInt(next(), 10);
    else if (a === '-h' || a === '--height') o.height = parseInt(next(), 10);
    else if (a === '--vertical') { o.width = 1080; o.height = 1920; }
    else if (a === '--transparent') o.transparent = true;
    else if (a === '--green') o.green = true;
    else if (a === '--delay') o.delay = parseFloat(next());
    else if (a === '--help') o.help = true;
    else if (!o.input) o.input = a;
  }
  return o;
}

// 프레임마다 CSS 애니메이션/트랜지션을 가상 시간에 맞춰 멈춰 세움
// (JS 애니메이션 - requestAnimationFrame, setTimeout, Date 등 - 은 page.clock 이 담당)
const SEEK_CSS = (now) => {
  const born = (window.__h2m_born ||= new WeakMap());
  for (const anim of document.getAnimations()) {
    if (!born.has(anim)) born.set(anim, now);
    anim.pause();
    anim.currentTime = now - born.get(anim);
  }
};

// CSS 애니메이션이 모두 끝나는 시간(ms) 계산. 무한 반복이면 null
const DETECT_DURATION = () => {
  let end = 0;
  for (const anim of document.getAnimations()) {
    const t = anim.effect.getComputedTiming();
    if (!isFinite(t.endTime)) return null;
    end = Math.max(end, t.endTime);
  }
  return end || null;
};

function startFfmpeg(o) {
  const args = ['-y', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(o.fps), '-i', '-'];
  if (o.transparent) {
    // ProRes 4444 + 알파 채널: 편집 프로그램에서 배경 없이 겹치기
    args.push('-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le');
  } else {
    // 유튜브 / 대부분 편집 프로그램 호환 설정
    args.push('-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
      '-pix_fmt', 'yuv420p', '-movflags', '+faststart');
  }
  args.push(o.out);
  const ff = spawn(FFMPEG, args, { stdio: ['pipe', 'inherit', 'inherit'] });
  ff.done = new Promise((res, rej) =>
    ff.on('close', (c) => (c === 0 ? res() : rej(new Error('ffmpeg 오류 코드 ' + c)))));
  return ff;
}

async function main() {
  const o = parseArgs(process.argv.slice(2));
  if (o.help || !o.input) return console.log(HELP);

  const input = path.resolve(o.input);
  if (!fs.existsSync(input)) throw new Error('파일이 없습니다: ' + input);
  const ext = o.transparent ? '.mov' : '.mp4';
  o.out ||= input.replace(/\.html?$/i, '') + ext;

  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: o.width, height: o.height },
  });

  // 가상 시계: 실제 시간과 무관하게 프레임 단위로 정확히 진행 (끊김 없음)
  await page.clock.install({ time: 0 });
  await page.clock.pauseAt(1000); // 시계를 멈춰 두고 프레임마다 직접 진행
  await page.goto('file://' + input, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  if (o.green) await page.addStyleTag({ content: 'html,body{background:#00ff00 !important}' });
  if (o.transparent) await page.addStyleTag({ content: 'html,body{background:transparent !important}' });
  await page.waitForTimeout(o.delay * 1000); // 이미지 등 실제 로딩 대기 (가상 시계는 멈춘 상태)

  if (!o.duration) {
    const ms = await page.evaluate(DETECT_DURATION);
    o.duration = ms ? ms / 1000 : 5;
    console.log(`영상 길이 ${ms ? '자동 감지' : '기본값'}: ${o.duration.toFixed(2)}초`);
  }

  const total = Math.round(o.duration * o.fps);
  console.log(`녹화 시작: ${o.width}x${o.height}, ${o.fps}fps, ${total}프레임 → ${o.out}`);
  const ff = startFfmpeg(o);

  let virtualMs = 0;
  for (let i = 0; i < total; i++) {
    const target = Math.round((i * 1000) / o.fps);
    if (target > virtualMs) await page.clock.runFor(target - virtualMs);
    virtualMs = target;
    await page.evaluate(SEEK_CSS, target);
    const png = await page.screenshot({ type: 'png', omitBackground: !!o.transparent });
    if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % o.fps === 0 || i === total - 1)
      process.stdout.write(`\r진행: ${Math.round(((i + 1) / total) * 100)}%   `);
  }

  ff.stdin.end();
  await ff.done;
  await browser.close();
  console.log(`\n완료! → ${o.out}`);
}

main().catch((e) => { console.error('\n실패:', e.message); process.exit(1); });
