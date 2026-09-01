#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""지면 구성을 보기 위한 샘플 기사를 만든다.

**이 도구가 만드는 것은 취재물이 아니다.** 사이트가 공개돼 있으므로 없는 사실을
지어내 기사로 실을 수 없다. 그래서 샘플은 세 겹으로 표시한다.

  ① 제목에 [샘플] 을 박는다 — 목록·카드·검색 어디에 나와도 보인다
  ② 본문 첫 줄에 안내 상자를 둔다
  ③ 숫자가 들어갈 자리는 [ ] 로 비워 둔다 — 채워 넣을 자리라는 뜻이다

지면이 얇은 지역(괌·사이판·코타키나발루·라오스)을 메운다.
그 네 곳이 주력 상품 지역인데 긁어올 뉴스가 없어 비어 있던 곳이다.

    python3 tools/make_samples.py            미리보기
    python3 tools/make_samples.py --write    검수 큐에 승인 상태로 생성
    python3 tools/make_samples.py --remove   샘플을 전부 걷어낸다
"""
from __future__ import annotations

import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW = os.path.join(ROOT, "content/review")
MARK = "[샘플]"

NOTICE = (
    "> **이 기사는 지면 구성을 보기 위한 샘플입니다.** 실제 취재 내용이 아니며, "
    "대괄호로 비워 둔 자리에는 답사·운영 기록에서 나온 실측값이 들어갑니다. "
    "정식 기사가 채워지면 이 글은 내려갑니다.\n"
)

SAMPLES = [
    ("guam", "news", "[샘플] 괌 PIC 리조트, 물놀이 시설과 객실 실측 기록", """
## 무엇을 확인했나

[YYYY년 M월] 답사 기준이다. 워터파크 운영 시간과 객실 동선을 직접 확인했다.
가격은 시즌마다 바뀌므로 확인일을 함께 적는다.

## 실측

| 항목 | 값 | 확인일 |
|---|---|---|
| 객실 유형 | [ ] | [YYYY-MM] |
| 실제 결제가 (1박) | [ ] | [YYYY-MM] |
| 공항 → 리조트 | [ ]분 | [YYYY-MM] |
| 워터파크 운영 | [ ] | [YYYY-MM] |
| 조식 운영 | [ ] | [YYYY-MM] |

공개하는 가격은 소비자가와 실제 결제가뿐이다. 거래처와의 계약 관련 숫자는 싣지 않는다.

## 이런 분께

- [직접 겪은 것만 적는다]
- [일반론은 쓰지 않는다]
"""),
    ("guam", "news", "[샘플] 괌 3박4일, 2인이 실제로 낸 돈", """
## 실제 지출

운영 기록에서만 나올 수 있는 표다. 광고가 아니라 영수증 기준이다.

| 항목 | 실제 결제가 | 비고 |
|---|---|---|
| 항공 | [ ] | [ ] |
| 숙소 | [ ] | 3박 |
| 액티비티 | [ ] | [ ] |
| 식비 | [ ] | [ ]끼 |
| 교통 | [ ] | [ ] |
| **합계** | **[ ]** | |

## 시즌별 변동

| 시기 | 항공 | 숙소 | 확인일 |
|---|---|---|---|
| 성수기 | [ ] | [ ] | [YYYY-MM] |
| 비수기 | [ ] | [ ] | [YYYY-MM] |

## 아낄 수 있는 곳

- [실제 운영에서 확인된 것만]
"""),
    ("guam", "news", "[샘플] 괌 돌고래 투어, 배 타는 시간과 실제 동선", """
## 코스

| 구간 | 소요 | 확인일 |
|---|---|---|
| 호텔 픽업 → 선착장 | [ ]분 | [YYYY-MM] |
| 출항 → 관측 지점 | [ ]분 | [YYYY-MM] |
| 관측 | [ ]분 | [YYYY-MM] |
| 귀항 → 호텔 | [ ]분 | [YYYY-MM] |

## 반복 운영에서 나온 것

같은 코스를 여러 번 운영하며 확인한 편차를 적는다.
한 번 다녀온 후기와 다른 지점이 여기다.

- 관측 성공률 [ ]
- 파도가 있는 날 [ ]
- 멀미가 잦은 구간 [ ]

## 주의

- [실제로 겪은 문제만 적는다]
"""),
    ("saipan", "news", "[샘플] 사이판 3박4일, 반복 운영으로 다듬은 일정표", """
## 하루별

| 일차 | 오전 | 오후 | 이동 |
|---|---|---|---|
| 1일 | [ ] | [ ] | [ ]분 |
| 2일 | [ ] | [ ] | [ ]분 |
| 3일 | [ ] | [ ] | [ ]분 |
| 4일 | [ ] | 출국 | [ ]분 |

## 왜 이 순서인가

- [실제 운영에서 순서를 바꾼 이유]
- [혼잡을 피하는 시간대]

## 무리한 조합

- [붙이면 안 되는 일정과 그 이유]
"""),
    ("saipan", "news", "[샘플] 사이판 날씨와 준비물, 문의가 가장 많았던 것", """
## 가장 많이 묻는 것

고객 문의 로그에서 빈도순으로 뽑았다. 검색해도 답이 안 나와 사람에게 물은 질문들이다.

1. [ ]
2. [ ]
3. [ ]

## 월별 기온과 강수

| 월 | 최고 | 최저 | 강수 | 확인일 |
|---|---|---|---|---|
| [ ] | [ ]°C | [ ]°C | [ ] | [YYYY-MM] |

오늘 날씨는 [사이판 지역면](/saipan/)의 데이터 패널에서 매일 갱신된다.

## 챙길 것

- [실제로 없어서 곤란했던 것만]
"""),
    ("kota", "news", "[샘플] 코타키나발루 숙소, 시내와 리조트 중 어디에 묵나", """
## 두 선택지

| | 시내 | 리조트 |
|---|---|---|
| 공항에서 | [ ]분 | [ ]분 |
| 1박 실제 결제가 | [ ] | [ ] |
| 식사 | [ ] | [ ] |
| 이동 부담 | [ ] | [ ] |

## 어떤 여행에 무엇이 맞나

- [운영하며 확인한 기준]

## 답사 기록

- [직접 본 것만]
"""),
    ("kota", "news", "[샘플] 코타키나발루 석양, 시간과 자리", """
## 시간

| 월 | 일몰 | 도착 권장 | 확인일 |
|---|---|---|---|
| [ ] | [ ] | [ ] | [YYYY-MM] |

## 자리

- [직접 서 본 자리와 그 이유]

## 우기에는

- [실제로 겪은 것]
"""),
    ("laos", "news", "[샘플] 라오스 이동, 구간별로 실제 걸린 시간", """
## 구간

| 구간 | 수단 | 실측 소요 | 확인일 |
|---|---|---|---|
| 비엔티안 → [ ] | [ ] | [ ]시간 | [YYYY-MM] |
| [ ] → [ ] | [ ] | [ ]시간 | [YYYY-MM] |

시간표는 어디에나 있다. **직접 타보고 잰 것**이 이 기사의 존재 이유다.

## 실제로 타본 기록

- [탑승 일시와 실제 소요]
- [정체·지연 구간]

## 주의

- [실제로 겪은 문제만]
"""),
]


def path_for(region: str, i: int) -> str:
    return os.path.join(REVIEW, f"sample_{region}_{i}.md")


def write_all() -> int:
    os.makedirs(REVIEW, exist_ok=True)
    made = 0
    for i, (region, section, title, body) in enumerate(SAMPLES, 1):
        front = {
            "id": f"sample-{region}-{i}",
            "region": region,
            "section": section,
            "title": title,
            "source_name": "와플트립",
            "source_url": "",
            "reason": "지면 구성 샘플",
            "summary": "지면 구성을 보기 위한 샘플입니다. 실제 취재 내용이 아닙니다.",
            "status": "approved",
        }
        with open(path_for(region, i), "w", encoding="utf-8") as f:
            f.write("---\n")
            yaml.safe_dump(front, f, allow_unicode=True, sort_keys=False)
            f.write("---\n\n" + NOTICE + body.strip() + "\n")
        made += 1
    return made


def remove_all(data_dir="data") -> tuple[int, int, int]:
    """샘플을 완전히 걷어낸다 — 초안·발행물·발행이력 셋 다."""
    files = 0
    if os.path.isdir(REVIEW):
        for name in list(os.listdir(REVIEW)):
            if name.startswith("sample_"):
                os.remove(os.path.join(REVIEW, name))
                files += 1

    items_dir = os.path.join(ROOT, data_dir, "items")
    removed_ids, lines_removed = set(), 0
    if os.path.isdir(items_dir):
        for name in sorted(os.listdir(items_dir)):
            if not name.endswith(".jsonl"):
                continue
            p = os.path.join(items_dir, name)
            keep = []
            with open(p, encoding="utf-8") as f:
                for raw in f:
                    if not raw.strip():
                        continue
                    d = json.loads(raw)
                    if MARK in d.get("title", ""):
                        removed_ids.add(d["id"])
                        lines_removed += 1
                    else:
                        keep.append(raw.rstrip("\n"))
            with open(p, "w", encoding="utf-8") as f:
                for k in keep:
                    f.write(k + "\n")

    idx_path = os.path.join(ROOT, data_dir, "published_index.json")
    purged = 0
    if removed_ids and os.path.exists(idx_path):
        with open(idx_path, encoding="utf-8") as f:
            idx = json.load(f)
        before = len(idx.get("ids", []))
        idx["ids"] = [i for i in idx.get("ids", []) if i not in removed_ids]
        idx["recent"] = [r for r in idx.get("recent", [])
                         if r.get("id") not in removed_ids]
        purged = before - len(idx["ids"])
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)
    return files, lines_removed, purged


def main(argv) -> int:
    if "--remove" in argv:
        files, items, purged = remove_all()
        print(f"샘플 제거: 초안 {files}개 · 발행물 {items}건 · 발행이력 {purged}건")
        print("다음에 빌드하면 지면에서 사라진다.")
        return 0

    if "--write" not in argv:
        print(f"샘플 {len(SAMPLES)}건 (미리보기)\n")
        for region, section, title, _ in SAMPLES:
            print(f"  {region:8} {section:7} {title}")
        print("\n실제로 만들려면:  python3 tools/make_samples.py --write")
        print("걷어내려면:      python3 tools/make_samples.py --remove")
        return 0

    made = write_all()
    print(f"샘플 초안 {made}건 생성 (status: approved)")
    print("다음:  python3 -m src.publish_drafts && python3 -m src.build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
