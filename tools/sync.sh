#!/bin/bash
# CI 봇과 같은 파일을 쓰면 충돌한다. data/ 는 CI 산출물이므로 항상 원격을 따른다.
# 내 변경은 코드와 content/review 뿐이다.
set -e
cd "$(dirname "$0")/.."
git fetch -q origin
git checkout -q origin/main -- data/ 2>/dev/null || true
echo "  data/ 를 원격 상태로 맞췄다. 이제 커밋해도 충돌하지 않는다."
