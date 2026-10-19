"""본문에서 매체 인용 문구를 뺀다.

2026-10-19 사장님: "PDN 보도에 따르면 이런 부분은 아예 삭제해. 이런 거 아예 안 나오게."
해설은 여러 매체의 보도를 바탕으로 피플로드 문장으로 다시 쓴 글이다. 본문에서
"PDN은 17일 별도 보도에서 … 전했다", "같은 보도에 따르면 …", "…라고 PDN이 전했다"
식으로 매체를 앞세우면 남의 기사를 옮겨 놓은 것처럼 읽힌다. 사실은 그대로 쓰고,
참고한 매체와 원문 주소는 기사 맨 끝 `**출처**` 줄에만 밝힌다(그 줄은 건드리지 않는다).

기관·회사·통계의 발표("합동정보센터에 따르면", "괌전력청은 … 밝혔다")는 1차 출처라
남긴다. 빼는 것은 **매체**를 앞세운 문구다.

- strip_media_attribution(text) — 규칙으로 고칠 수 있는 문장은 고친다
- find_media_attribution(text)  — 고친 뒤에도 남은 매체 인용 문장을 돌려준다(검사용)
"""
from __future__ import annotations

import re

# 동사: 매체가 주어일 때 문장을 끝내는 말
_VERBS = ("전했다|보도했다|밝혔다|알렸다|명시했다|덧붙였다|설명했다|소개했다|짚었다|썼다|"
          "강조했다|보탰다|적었다|지적했다|내다봤다|분석했다|평가했다|예상했다|전망했다|"
          "다뤘다|정리했다|보고했다|언급했다|인용했다")

_LEAD_WORDS = ("또한|또|한편|이어|아울러|다만|특히|앞서|반면|이와 함께|같은 날|이날|이후|"
               "그러나|하지만|그리고|먼저|끝으로|여기에|이에|결국|실제로")

# 매체로 보이는 이름 끝말
_MEDIA_SUFFIX = re.compile(
    r"(뉴스|일보|신문|타임스|타임즈|포스트|매체|방송|TV|투데이|경제|이코노믹|이코노미|웍스|데일리|미디어|저널|"
    r"위클리|프레스|헤럴드|닷컴|통신|매거진|리뷰|스타|엔터|연예|코리아|비즈|Biz|"
    r"News|Times|Post|Daily|Press|Herald|Journal|Magazine|Media|Report|Travel|Tribune|"
    r"Star|Edge|Mole|Review|Hawaii|Now|\.vn|\.VN|\.com|\.kr|미리보기|보도자료|예고편|"
    r"KBS|MBC|SBS|EBS|YTN|JTBC|tvN|OBS|TJB|KBFD|KUAM|ize|1)\)?$")

# 출처 줄에 없어도 본문에 자주 나오는 우리말 표기·약칭
_KNOWN = (
    "PDN", "HNN", "PIT", "NST", "하와이뉴스나우", "하와이 뉴스 나우", "뉴스트레이츠타임스",
    "퍼시픽데일리뉴스", "퍼시픽 데일리 뉴스", "괌데일리포스트", "괌 데일리 포스트",
    "퍼시픽아일랜드타임스", "퍼시픽 아일랜드 타임스", "마리아나스프레스", "마리아나스 프레스",
    "VnExpress", "브이엔익스프레스", "라오시안타임스", "라오시안 타임스", "더스타", "디엣지",
    "베트남넷", "투오이째", "탄니엔", "아이즈", "bnt뉴스", "iMBC", "아이엠비씨",
    "KBS", "MBC", "SBS", "EBS", "YTN", "JTBC", "tvN", "OBS", "TJB", "KBFD", "KUAM",
    "KBS 미리보기", "EBS 보도자료", "SBS 보도자료", "MBC 보도자료",
)


def _initials(name: str) -> str:
    words = [w for w in re.split(r"\s+", name) if w and w[0].isalpha() and w[0].isascii()]
    return "".join(w[0].upper() for w in words) if len(words) >= 2 else ""


def media_names(text: str) -> list[str]:
    """출처 줄에서 매체 이름을 뽑고 약칭·별칭을 더한다. 긴 것부터."""
    names: set[str] = set(_KNOWN)
    for line in text.splitlines():
        if not line.lstrip().startswith("**출처**"):
            continue
        for m in re.finditer(r"\[([^\]「]+?)\s*「", line):
            raw = m.group(1).strip()
            names.add(raw)
            # "아이즈(ize)" → 아이즈, ize / "MTN 머니투데이방송" → MTN
            base = re.sub(r"\(.*?\)", "", raw).strip()
            names.add(base)
            for inner in re.findall(r"\((.*?)\)", raw):
                names.add(inner.strip())
            first = base.split()[0] if base.split() else ""
            if first and len(base.split()) >= 2 and re.fullmatch(r"[A-Z]{2,}", first):
                names.add(first)
            if base.lower().startswith("the "):
                names.add(base[4:])
            ini = _initials(base)
            if len(ini) >= 3:
                names.add(ini)
    names = {n for n in names if n and len(n) >= 2}
    return sorted(names, key=len, reverse=True)


def _looks_like_media(subject: str, names: list[str]) -> bool:
    s = subject.strip().strip("*").strip()
    if not s:
        return False
    if re.search(r"[가-힣](?:도|을|를|에|의|은|는|이|가)\s", s):
        return False
    parts = re.split(r"(?<=[가-힣A-Za-z0-9)])(?:와|과)\s+|\s*[·,]\s*|\s+및\s+", s)
    def one(p: str) -> bool:
        p = p.strip()
        if not p:
            return False
        if p in names:
            return True
        if re.fullmatch(r"(?:말레이시아|베트남|태국|대만|일본|괌|하와이|현지|해외|외신|국내|여행업계|여행|업계|미국|중국|라오스)?\s*(?:현지\s*)?(?:매체|언론|외신|여행업계 매체|업계 매체|전문지|일간지)\s*.{0,30}", p):
            return True
        if re.fullmatch(r"(?:같은|다른|또 다른|한|두|여러)\s*(?:매체|언론|외신)", p):
            return True
        return bool(_MEDIA_SUFFIX.search(p)) and len(p) <= 30
    return all(one(p) for p in parts)


def _convert_end(rest: str) -> str | None:
    """'…했다고 전했다.' → '…했다.' 고칠 수 없으면 None."""
    rest = rest.rstrip()
    trail = ""
    m = re.search(r"(\.(?:\*\*)?)$", rest)
    if not m:
        return None
    trail = m.group(1)
    core = rest[: m.start()]
    # 인용부호 바로 뒤 '고/라고' — 말한 사람이 사라지므로 규칙으로는 못 고친다
    if re.search(r"[\"”’'](?:\*\*)?\s*(?:이라고|라고|고)\s+(?:" + _VERBS + r")$", core):
        return None
    m = re.search(r"(다는|라는|이라는)\s+(?:소식|사실|내용|점)(?:을|를)\s+(?:" + _VERBS + r")$", core)
    if m:
        return core[: m.start()] + {"다는": "다", "라는": "다", "이라는": "이다"}[m.group(1)] + trail
    m = re.search(r"(다|이라|라)(\*\*)?고\s+(?:" + _VERBS + r")$", core)
    if not m:
        return None
    head = core[: m.start()]
    bold = m.group(2) or ""
    if re.search(r"(?:전했|보도했|밝혔|알렸|덧붙였|설명했|소개했|짚었|썼|강조했|명시했)(?:고|으며|며|는데|지만),?\s", head):
        return None                                   # '…전했고, …' 같은 겹문장
    end = {"다": "다", "이라": "이다", "라": "다"}[m.group(1)]
    return head + end + bold + trail


def _src_cite(rest: str) -> str:
    """'칸호아성을 인용해 …' → '칸호아성에 따르면 …'."""
    rest = re.sub(r"^(?:보도|기사)(?:에서는|에서)\s+", "", rest)
    m = re.match(r"^(.{1,60}?)(?:의 말|의 발표|의 자료|의 집계)?(?:을|를)\s+인용(?:해|하여|하며),?\s+", rest)
    if m:
        return f"{m.group(1)}에 따르면 " + rest[m.end():]
    return rest


_DATE = (r"(?:지난\s+)?(?:\d{1,2}월\s*)?(?:\d{1,2}일\s*)?(?:\([월화수목금토일]\)\s*)?"
         r"(?:\(현지\s*시간\)\s*)?,?\s*")
_KIND = (r"(?:(?:같은 날|이날|당일|하루 전|이튿날)\s+)?(?:[가-힣A-Za-z]{1,8}발\s+)?"
         r"(?:(?:별도|같은|후속|앞선|이날|당일|다른|또 다른|관련|최근|이어진|첫)\s+)?")
_REPORT = r"(?:보도|기사|리포트|방송|뉴스|칼럼|보도자료|예고|미리보기)"


def _fix_sentence(s: str, names: list[str]) -> str:
    original = s
    nm = "|".join(re.escape(n) for n in names) or "(?!x)x"

    # 괄호 속 출처 표시 "(PDN, 17일 보도)" "(9월 29일 보도)"
    s = re.sub(r"\s*\((?:[^()]{0,40}?,\s*)?(?:\d{1,2}월\s*)?(?:\d{1,2}일\s*)?보도\)", "", s)

    s = re.sub(r"([^\s]+?)(?:을|를)\s+인용한\s+(?:[^\s]+\s+)?(?:보도|기사)에\s+따르면,?\s*", r"\1에 따르면 ", s)
    # "…보도에 따르면" "PDN에 따르면" "EBS 보도자료에 따르면" "EBS가 15일 배포한 보도자료에 따르면"
    s = re.sub(r"(?:(?:" + nm + r")(?:의|가|이)?\s*(?:\(\s*[^()]*\)\s*)?)?" + _DATE
               + r"(?:배포한\s+|낸\s+|공개한\s+)?" + _KIND
               + r"(?:(?:이번|이|해당|같은|위|두|세|여러|이들|관련|복수의?)\s+)?"
               + r"(?:보도|기사|보도자료|미리보기|예고편|예고|외신|매체 보도|현지 보도|언론 보도)(?:들)?(?:에|에서)?\s+따르면,?\s*",
               "", s)
    s = re.sub(r"(?<![가-힣A-Za-z])(?:" + nm + r")(?:의\s+보도)?에\s+따르면,?\s*", "", s)
    s = re.sub(r"(?:[A-Za-z가-힣0-9]{2,12}(?:가|이|의)?\s+)?" + _DATE + r"(?:배포한\s+|낸\s+|공개한\s+)?"
               r"(?:보도자료|미리보기|예고편|예고 영상)(?:에|에서)?\s+따르면,?\s*", "", s)

    # 문장 첫머리의 군더더기(목록 번호, 굵은 소제목, 접속어)는 그대로 둔다
    m = re.match(r"^(?P<lead>(?:\d+\.\s+)?(?:\*\*[^*]{1,40}\*\*\s*[—:\-–]\s*)?(?:(?:" + _LEAD_WORDS + r")\s*,?\s+)*)(?P<body>.*)$", s, re.S)
    lead, body = m.group("lead"), m.group("body")

    # "PDN은 17일 별도 보도에서 (X를 인용해) …라고 전했다."
    m = re.match(r"^(?P<media>.{1,50}?)(?:은|는|이|가|도)\s+" + _DATE + _KIND + _REPORT
                 + r"(?:에서는|에서|를 통해|을 통해|로|에)\s*,?\s*(?P<rest>.+)$", body, re.S)
    if m and not re.search(r"보도|따르면", m.group("media")):
        conv = _convert_end(_src_cite(m.group("rest")))
        if conv:
            return lead + conv
        return original

    # "같은 보도는 …라고 전했다."
    m = re.match(r"^(?:(?:이번|같은|이|해당|다른|또 다른|앞선|이어진|후속|별도|두|여러)\s+)?(?:보도|기사|매체)(?:들)?(?:은|는|도|에서는|에서)\s+(?P<rest>.+)$", body, re.S)
    if m:
        conv = _convert_end(_src_cite(m.group("rest")))
        if conv:
            return lead + conv
        return original

    # "PDN은 (17일) …라고 전했다."  — 주어가 매체일 때만
    m = re.match(r"^(?P<media>.{1,50}?)(?:은|는|이|가|도)\s+" + _DATE + r"(?:(?:이어|또|같은 날|이날|별도로)\s+)?(?P<rest>.+)$", body, re.S)
    if m and _looks_like_media(m.group("media"), names):
        conv = _convert_end(_src_cite(m.group("rest")))
        if conv:
            return lead + conv

    # "…옮겼다고 PDN이 전했다."
    m = re.match(r"^(?P<pre>.+?)(?P<e>다|이라|라)고\s+" + _DATE + r"(?P<media>.{1,40}?)(?:은|는|이|가)\s+" + _DATE
                 + r"(?:" + _VERBS + r")(?P<t>\.(?:\*\*)?)$", s, re.S)
    if m and _looks_like_media(m.group("media"), names) and not re.search(r"[\"”’']\s*$", m.group("pre")):
        return m.group("pre") + {"다": "다", "이라": "이다", "라": "다"}[m.group("e")] + m.group("t")

    return s


# "이번 보도에 나오지 않았다" 같은 보도 언급
_NOT_IN_REPORT = re.compile(
    r"(?:(?:이번|이|해당|같은|관련|두|세|네|다섯|여러|다른|이들|모든)\s+)?(?:건의\s+)?"
    r"(?:보도|기사|보도자료)(?:들)?\s*(?:어디에도|모두에서?|에는|에도|에서는|에서도|에선|에)\s*"
    r"(?:아직\s+)?(?:자세히\s+|구체적으로\s+|따로\s+)?"
    r"(나오지 않았다|나오지 않는다|나와 있지 않다|나와 있지 않았다|없다|없었다|담기지 않았다|담겨 있지 않다|"
    r"언급되지 않았다|밝히지 않았다|드러나지 않았다|나오지 않았고|나오지 않지만|나오지 않아|없어)")
_NIR_MAP = {"나오지 않았고": "알려지지 않았고", "나오지 않지만": "알려지지 않았지만",
            "나오지 않아": "알려지지 않아", "없어": "알려지지 않아"}


def _fix_not_in_report(s: str) -> str:
    def rep(m: re.Match) -> str:
        return "아직 " + _NIR_MAP.get(m.group(1), "알려지지 않았다")
    s = _NOT_IN_REPORT.sub(rep, s)
    s = re.sub(r"(?:아직\s+)?보도되지 않았다", "아직 알려지지 않았다", s)
    s = re.sub(r"아직\s+아직", "아직", s)
    s = re.sub(r"(?:이번|이|두|이들)\s+보도(?:들)?(?:로|에서|를 통해)\s+확인되는", "확인된", s)
    return s


_SPLIT = re.compile(r"(?<=[다요]\.)\s+|(?<=다\.\*\*)\s+")


def _fix_line(line: str, names: list[str]) -> str:
    if line.lstrip().startswith("**출처**"):
        return line
    m = re.match(r"^(\s*(?:[-*>]\s+|\d+\.\s+(?=\S))?)(.*)$", line)
    prefix, text = m.group(1), m.group(2)
    if not text.strip():
        return line
    if text.lstrip().startswith("|"):          # 표 행은 칸 단위로
        cells = text.split("|")
        return prefix + "|".join(_fix_text(c, names) for c in cells)
    return prefix + _fix_text(text, names)


_FOLLOW = re.compile(r"^(?P<core>.+?)(?P<e>다|이라|라)(?P<b>\*\*)?고\s+(?:덧붙였다|전했다|보도했다|보탰다)(?P<t>\.(?:\*\*)?)$", re.S)


def _fix_text(text: str, names: list[str]) -> str:
    out = []
    prev_media = False
    for s in _SPLIT.split(text):
        fixed = _fix_sentence(s, names)
        converted = fixed != s
        # 앞 문장의 매체 주어를 이어받은 "…고 덧붙였다." — 말한 사람이 매체다
        if not converted and prev_media:
            m = _FOLLOW.match(s.strip())
            if m and not re.search(r"[\"”’']$", m.group("core")) and not re.match(r"^\S+(?:은|는)\s", s.strip()):
                fixed = m.group("core") + {"다": "다", "이라": "이다", "라": "다"}[m.group("e")] + (m.group("b") or "") + m.group("t")
                converted = True
        out.append(_fix_not_in_report(fixed))
        prev_media = converted and fixed != s
    return " ".join(out)


def strip_media_attribution(text: str, names: list[str] | None = None) -> str:
    """본문(마크다운) 전체를 고친다. 출처 줄과 제목줄(#)의 구조는 그대로."""
    if not text:
        return text
    names = names if names is not None else media_names(text)
    lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith("#"):
            lines.append(line)
            continue
        lines.append(_fix_line(line, names))
    return "\n".join(lines)


# 보도·매체를 가리키지 않는 낱말("주의보도", "횡단보도")은 검사에서 뺀다
_BROADCASTERS = {"KBS", "MBC", "SBS", "EBS", "YTN", "JTBC", "tvN", "OBS", "TJB", "KBFD", "KUAM", "KBS1", "KBS2", "EBS1"}
# 출처 줄이 없는 옛 원고용 — 이름 꼴로 매체를 알아본다
_GENERIC_OUTLET = re.compile(
    r"[A-Za-z가-힣0-9.]+(?:뉴스|일보|신문|타임스|포스트|투데이|데일리|저널|미디어|통신|매거진|소리|"
    r"News|Times|Post|Daily|Press|Herald|Journal|Media|Now)(?:와|과|은|는|이|가|도)\s")
_PRESS_VERB = re.compile(r"전했|전한|보도|짚었|썼다|실었|다뤘|소개했|전하며|전하면서")
_NOT_PRESS = re.compile(r"(?:주의보|경보|특보|예보|정보|회보|홍보)도|횡단보도|보도블록|인도와 보도")


def find_media_attribution(text: str, names: list[str] | None = None) -> list[str]:
    """남아 있는 매체 인용 문장. 출처 줄과 그 바로 뒤 맺음말은 보지 않는다.

    본문과 요약에는 '보도', '매체', '언론', '외신', 매체 이름 + 조사, 우리 매체가
    전에 '전한/보도한' 것 같은 말을 쓰지 않는다. 걸리면 사실만 남기고 다시 쓴다.
    """
    if not text:
        return []
    names = names if names is not None else media_names(text)
    # 방송사가 자기 프로그램을 내보내는 것은 매체 인용이 아니다("SBS가 15일 방송한다")
    names = [n for n in names if n not in _BROADCASTERS]
    nm = "|".join(re.escape(n) for n in names) or "(?!x)x"
    pat_media = re.compile(
        r"(?:^|[\s(“\"'*—·,])(?:" + nm + r")(?:은|는|이|가|도|에 따르면|의 보도|보도|기사|와|과|·)(?=[\s,·]|$)")
    pat_self = re.compile(r"(?:와플트립|피플로드)(?:가|는|이|도)\s.{0,40}?(?:전한|전했|보도|다룬|모은 기사|썼)")
    found = []
    for line in text.split("\n"):
        st_line = line.strip()
        if st_line.startswith("**출처**") or st_line.startswith("이 기사는 위 보도를"):
            continue
        for s in _SPLIT.split(line):
            st = s.strip()
            if not st:
                continue
            plain = _NOT_PRESS.sub("", st)
            if (re.search(r"보도|매체|언론|외신|기사(?:에서|를 보면|에는|에도|는|로는|만으로)", plain)
                    or pat_media.search(st) or pat_self.search(st)
                    or (_GENERIC_OUTLET.search(st) and _PRESS_VERB.search(st))):
                found.append(st)
    return found
