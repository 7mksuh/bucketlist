#!/bin/bash
# audio/urls.txt 의 Fish Audio 음성 파일을 내려받는다.
# 사용법: bash video-agent/도구/get_audio.sh video-agent/작업중/<영상이름>
cd "$1/audio" || exit 1
while read -r name url; do
  [ -n "$url" ] && curl -sSfL -o "$name" "$url" && echo "받음: $name"
done < urls.txt
