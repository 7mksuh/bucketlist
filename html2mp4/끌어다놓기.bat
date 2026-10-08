@echo off
chcp 65001 > nul
REM HTML 파일을 이 파일 위로 끌어다 놓으면 MP4로 변환됩니다
cd /d "%~dp0"
for %%F in (%*) do node html2mp4.js "%%~F"
pause
