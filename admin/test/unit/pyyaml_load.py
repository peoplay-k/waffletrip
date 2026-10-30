# 테스트 도우미: 표준 입력의 YAML 글 목록(JSON)을 PyYAML(파이프라인과 같은 파서)로 읽어 JSON 으로 돌려준다.
# 날짜는 문자열로 바꾼다. 읽지 못한 글은 {"__error__": 메시지}.
import json
import sys

import yaml

out = []
for text in json.load(sys.stdin):
    try:
        out.append(yaml.safe_load(text))
    except Exception as e:  # noqa: BLE001 — 오류 내용을 그대로 돌려준다
        out.append({"__error__": str(e)})
json.dump(out, sys.stdout, ensure_ascii=False, default=str)
