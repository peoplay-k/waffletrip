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
    assert "<ol>" in render("1. 하나\n2. 둘")


def test_blockquote_and_rule():
    assert "<blockquote>" in render("> 인용")
    assert "<hr>" in render("---")


def test_empty_input_is_empty_output():
    assert render("") == ""
    assert render(None) == ""


def test_bold_works_after_escaping():
    out = render("이건 **굵게** 다")
    assert "<strong>굵게</strong>" in out
