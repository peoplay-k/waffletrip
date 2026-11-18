"""해설 본문 렌더러. 이스케이프가 구조보다 먼저인지를 집중적으로 본다."""
from __future__ import annotations

from src.render.md import render


def test_script_tag_is_escaped_not_executed():
    out = render("<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_img_onerror_is_escaped():
    out = render('<img src=x onerror="alert(1)">')
    assert "<img" not in out
    assert "onerror" not in out or "&lt;img" in out


def test_javascript_scheme_link_loses_its_href():
    out = render("[누르지마](javascript:alert(1))")
    assert "javascript:" not in out
    assert "누르지마" in out


def test_http_link_survives_with_nofollow():
    out = render("[원문](https://example.com/a)")
    assert 'href="https://example.com/a"' in out
    assert "nofollow" in out


def test_heading_levels():
    assert "<h2>제목</h2>" in render("## 제목")
    assert "<h3>소제목</h3>" in render("### 소제목")


def test_table_renders_with_scroll_wrapper():
    out = render("| 항목 | 값 |\n|---|---|\n| 가격 | 1,000 |")
    assert '<div class="tw">' in out          # 좁은 화면에서 가로 스크롤
    assert "<th>항목</th>" in out
    assert "<td>1,000</td>" in out


def test_table_cell_content_is_escaped():
    out = render("| 항목 |\n|---|\n| <b>굵게</b> |")
    assert "<b>" not in out
    assert "&lt;b&gt;" in out


def test_bullet_and_numbered_lists():
    assert render("- 하나\n- 둘").count("<li>") == 2
    assert "<ol class=\"nlist\">" in render("1. 하나\n2. 둘")


def test_blockquote_and_rule():
    assert "<blockquote>" in render("> 인용")
    assert "<hr>" in render("---")


def test_empty_input_is_empty_output():
    assert render("") == ""
    assert render(None) == ""


def test_bold_works_after_escaping():
    out = render("이건 **굵게** 다")
    assert "<strong>굵게</strong>" in out


def test_internal_links_are_not_nofollowed():
    """우리 쪽 링크에 nofollow 를 붙이면 우리 지면끼리 연결이 전달되지 않는다."""
    out = render("[제주 지면](/jeju/)에 쌓입니다.")
    assert '<a href="/jeju/">제주 지면</a>' in out
    assert "nofollow" not in out
    assert "target=" not in out


def test_external_links_keep_nofollow_and_new_tab():
    """남의 사이트로는 신뢰를 넘기지 않고 새 창으로 연다."""
    out = render("[원문](https://example.com/a)")
    assert 'rel="nofollow noopener"' in out
    assert 'target="_blank"' in out


def test_한_줄_사진은_캡션과_함께_그린다():
    """방송사 보도 스틸을 출처와 함께 싣는다(2026-10-16)."""
    from src.render.md import render
    got = render("![사진: KBS 1TV '인간극장'](https://img.kbs.co.kr/a.jpg)")
    assert '<img src="https://img.kbs.co.kr/a.jpg"' in got
    assert 'referrerpolicy="no-referrer"' in got
    assert "<figcaption>사진: KBS 1TV &#x27;인간극장&#x27;</figcaption>" in got


def test_사진은_https_만_받고_캡션은_이스케이프한다():
    from src.render.md import render
    assert "<img" not in render("![x](javascript:alert(1))")
    assert "<img" not in render("![x](http://a.com/b.jpg)")
    assert "<script>" not in render('![<script>](https://a.com/b.jpg)')


def test_여러_줄_인용은_줄을_살린다():
    from src.render.md import render
    got = render("> **방송 정보**\n> 채널 · KBS1 | 프로그램 · 인간극장")
    assert got == ("<blockquote><strong>방송 정보</strong><br>"
                   "채널 · KBS1 | 프로그램 · 인간극장</blockquote>")


def test_유튜브_예고편은_id_만_받아_nocookie_로_띄운다():
    from src.render.md import render
    got = render("@youtube NTk5p8RJJ6k")
    assert 'src="https://www.youtube-nocookie.com/embed/NTk5p8RJJ6k"' in got
    assert "<iframe" not in render('@youtube "><script>x')
    assert "<iframe" not in render("@youtube https://evil.example/aaaaaaaaaaa")


def test_readability_rules_2026_11_16():
    from src.render.md import highlight, maps_of, summary_lines
    out = render("첫 문장이다. 둘째 문장이다.\n\n자세한 건 https://example.com/x 에서.")
    assert "첫 문장이다.<br>둘째 문장이다." in out                # 한 문장 한 줄
    assert "바로가기" in out and ">https://" not in out               # 주소는 지면에 안 보인다
    assert 'class="slist"' in render("- 하나\n- 둘")
    assert "@map" not in render("본문.\n\n@map 제주 도두항") and maps_of("본문.\n\n@map 제주 도두항") == ["제주 도두항"]
    assert 'class="ai-note"' in render("본문이다.\n\n이 카툰은 AI 로 그렸다.")
    assert len(summary_lines("가가가가가가가가가가가가. 나나나나나나나나나나나, 다다다다다다다다다다다다.")) == 3
    assert "<mark>24%</mark>" in highlight("여객이 24% 줄었다") and "<mark>" not in highlight("11월 13일")


def test_카툰_컷은_우리_카툰_그림만_세로로_붙인다():
    """여행 카툰을 여러 컷 이야기로 싣는다(2026-11-18 사장님: "이미지 4장 이상, 스토리 있게")."""
    out = render("@panel /img/cartoon/ep006_1.webp 1컷 · 근고기집에 들어선 준\n\n"
                 "@panel /img/cartoon/ep006_2.webp")
    assert out.count('<figure class="panel">') == 2
    assert '<img src="/img/cartoon/ep006_1.webp" alt="1컷 · 근고기집에 들어선 준"' in out
    assert '<img src="/img/cartoon/ep006_2.webp" alt=""' in out
    assert "<figcaption>" not in out            # 컷 밑에 설명을 달지 않는다
    assert "@panel" not in out


def test_카툰_컷은_남의_주소와_상위_폴더를_받지_않는다():
    for line in ("@panel https://example.com/x.webp",
                 "@panel /img/cartoon/../photos/a.webp",
                 "@panel /img/guam/a.webp",
                 '@panel /img/cartoon/ep006_1.webp"onerror=alert(1)'):
        out = render(line)
        assert "<img" not in out and "<figure" not in out, line
        assert "@panel" not in out, line          # 못 쓰는 줄은 글자로도 남기지 않는다


def test_카툰_컷의_설명은_이스케이프한다():
    out = render('@panel /img/cartoon/ep006_1.webp <script>alert(1)</script>')
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
