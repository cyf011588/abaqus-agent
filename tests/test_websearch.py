# -*- coding: utf-8 -*-
"""测试：联网检索工具的纯函数（不实际联网）。"""
from agent import websearch


def test_strip_html():
    assert websearch._strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert websearch._strip_html("<script>var x=1;</script>text") == "text"


def test_real_url_uddg():
    assert websearch._real_url("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa") == "https://example.com/a"


def test_extract_ddg():
    html = ('<a rel="nofollow" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com" class="result-link">标题</a>'
            '<td class="result-snippet">摘要内容</td>')
    res = websearch._extract_ddg(html)
    assert len(res) == 1
    assert res[0] == ("标题", "https://example.com", "摘要内容")


def test_extract_bing():
    html = ('<li class="b_algo"><h2><a href="https://example.com/page">标题</a></h2>'
            '<p>摘要内容</p></li>')
    res = websearch._extract_bing(html)
    assert len(res) == 1
    assert res[0] == ("标题", "https://example.com/page", "摘要内容")
