"""이미 실린 기사를 고치면 지면도 고친다.

지면은 원고(content/review/*.md)가 아니라 발행 기록(data/items/<날짜>.jsonl)을 읽는다.
그래서 편집실(/admin/)에서 발행된 기사를 고쳐도 라이브가 안 바뀌었다. 원고의
published_id 로 발행 기록을 찾아 제목·요약·본문·지면·부문·필자·사진을 원고에 맞춘다
(2026-10-28 사장님: "어드민 단 만들어줘 로그인해서 기사 고치거나 기사 올릴 수 있는 곳").

발행 때와 같은 문을 지난다 — 매체 인용 문장은 걷어내고, 남거나 개인정보가 걸리면
고친 내용을 싣지 않고 그대로 둔다. 제목이나 지면이 바뀌면 주소가 바뀌므로 옛 주소를
data/moved_urls.json 에 적어 새 주소로 넘긴다.

파이프라인 순서: … → publish_drafts → **sync_edits** → build
"""
from __future__ import annotations

import glob
import json
import os
import sys

from src.attribution import find_media_attribution, media_names, strip_media_attribution
from src.guards.privacy_guard import find_violations
from src.models import CHANNELS, REGIONS, item_from_dict, title_hash
from src.publish_drafts import _body_text, _split, _summary_of
from src.topics import ent_canonical

MOVED_URLS = os.path.join("data", "moved_urls.json")


def wanted_fields(front: dict, body: str) -> tuple[dict | None, str]:
    """원고 → 발행 기록에 들어갈 값. 실을 수 없으면 (None, 사유)."""
    title = str(front.get("title") or "").strip()
    if not title:
        return None, "제목이 없다"
    text = _body_text(body)
    if not text:
        return None, "본문이 비었다"
    names = media_names(body)
    text = strip_media_attribution(text, names)
    front = dict(front)
    if front.get("summary"):
        front["summary"] = strip_media_attribution(str(front["summary"]), names)
    if (find_media_attribution(text, names)
            + find_media_attribution(str(front.get("summary") or ""), names)):
        return None, "본문에 매체 인용 문장이 남았다"
    if find_violations(f"{title}\n{text}"):
        return None, "개인정보·거래단가가 걸렸다"
    channel = str(front.get("channel") or "travel").strip()
    if channel not in CHANNELS:
        return None, f"모르는 채널 {channel!r}"
    region = str(front.get("region") or "").strip()
    category = str(front.get("category") or "").strip()
    if channel == "ent":
        region, category = "", ent_canonical(category)
    else:
        category = ""
        if region not in REGIONS:
            return None, f"모르는 지역 {region!r}"
    out = {
        "title": title, "title_hash": title_hash(title),
        "summary": _summary_of(front, text), "body_md": text,
        "channel": channel, "region": region, "category": category,
        "section": str(front.get("section") or "news"),
        "source_name": str(front.get("source_name") or ""),
    }
    # 사진은 웹 경로가 된 것만 옮긴다. 편집실에서 막 올린 원본(content/uploads)은
    # 사진 반입이 검사해 웹 경로로 바꾼 다음에야 지면에 오른다.
    photo = str(front.get("photo") or "")
    if photo.startswith("/") and not photo.startswith("/content/"):
        out["photo"] = photo
    return out, ""


_DEFAULTS = {"channel": "travel", "category": "", "region": "", "section": "news",
             "source_name": "", "summary": "", "body_md": ""}


def _now(d: dict, key: str):
    """발행 기록의 지금 값. 옛 기록에는 channel·category 칸이 없고, 연예 부문은
    옛 id(drama·star)로 남아 있을 수 있다 — 그건 고친 것이 아니다."""
    v = d.get(key)
    if v is None:
        v = _DEFAULTS.get(key)
    if key == "category" and v:
        v = ent_canonical(str(v)) or v
    return v


def _load_reviews(review_dir: str) -> dict[str, tuple[str, dict, str]]:
    """published_id → (파일 이름, 앞머리, 본문). 발행된 원고만."""
    out: dict[str, tuple[str, dict, str]] = {}
    for path in sorted(glob.glob(os.path.join(review_dir, "*.md"))):
        try:
            with open(path, encoding="utf-8") as f:
                front, body = _split(f.read())
        except Exception:
            continue
        pid = str(front.get("published_id") or "")
        if front.get("status") == "published" and pid:
            out[pid] = (os.path.basename(path), front, body)
    return out


def sync(data_dir: str = "data", review_dir: str = "content/review",
         moved_path: str | None = None) -> int:
    """고친 원고를 발행 기록에 옮긴다. 고친 기사 수."""
    from src.render.site import article_url
    reviews = _load_reviews(review_dir)
    if not reviews:
        return 0
    moved_path = moved_path or os.path.join(data_dir, "moved_urls.json")
    try:
        with open(moved_path, encoding="utf-8") as f:
            moved = json.load(f)
    except (OSError, ValueError):
        moved = {}
    changed = 0
    held: set[str] = set()
    for jl in sorted(glob.glob(os.path.join(data_dir, "items", "*.jsonl"))):
        with open(jl, encoding="utf-8") as f:
            lines = f.read().splitlines()
        dirty = False
        for n, raw in enumerate(lines):
            if not raw.strip():
                continue
            d = json.loads(raw)
            hit = reviews.get(d.get("id", ""))
            if not hit:
                continue
            name, front, body = hit
            want, why = wanted_fields(front, body)
            if want is None:
                if name not in held:
                    print(f"  고친 내용 보류 {name}: {why} — 지면은 그대로 둔다", file=sys.stderr)
                    held.add(name)
                continue
            diff = {k: v for k, v in want.items() if _now(d, k) != v}
            if not diff:
                continue
            old_url = article_url(item_from_dict(d))
            d.update(diff)
            new_url = article_url(item_from_dict(d))
            if old_url != new_url:
                moved[old_url] = d["id"]
            lines[n] = json.dumps(d, ensure_ascii=False)
            dirty = True
            changed += 1
            print(f"  고침 반영: {name} — {', '.join(k for k in diff if k != 'title_hash')}")
        if dirty:
            with open(jl, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
    if changed:
        with open(moved_path, "w", encoding="utf-8") as f:
            json.dump(moved, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return changed


def main() -> int:
    n = sync()
    print(f"고친 기사 반영: {n}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
