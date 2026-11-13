#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i 'color=c=navy:s=320x180:r=10:d=120' \
  -f lavfi -i 'sine=frequency=440:duration=120' \
  -f lavfi -i 'sine=frequency=880:duration=120' \
  -i tests/media/english.srt -i tests/media/french.srt \
  -map 0:v -map 1:a -map 2:a -map 3:s -map 4:s \
  -c:v libx264 -preset ultrafast -crf 35 -pix_fmt yuv420p \
  -c:a aac -b:a 32k -c:s mov_text \
  -metadata:s:a:0 language=eng -metadata:s:a:1 language=fra \
  -metadata:s:s:0 language=eng -metadata:s:s:1 language=fra \
  app/src/androidTest/assets/player-fixture.mp4
