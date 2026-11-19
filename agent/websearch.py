# -*- coding: utf-8 -*-
"""联网检索工具（纯标准库 urllib + re）。

供编排层 LLM 在「本地案例/知识都覆盖不到」时自主查询外部资料：
- search(query)：DuckDuckGo Lite 网页搜索（无 key、尽力而为，失败明确告知）
- fetch(url)：抓取网页正文（去标签提取文本）

设计约束：工具层零第三方依赖；网络不可用/解析失败时**明确返回失败**，
由上层 fallback 兜底（告知用户 + 建议权威 URL），绝不假装查到了。
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from typing import List, Tuple

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Abaqus-Agent/0.1"


# --------------------------------------------------------------------------- 纯函数（可测）
def _strip_html(html: str) -> str:
    """去 HTML 标签提取正文文本。"""
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"&#?\w+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _real_url(u: str) -> str:
    """DuckDuckGo 重定向链接 uddg 解码回真实 URL。"""
    if "uddg=" in u:
        m = re.search(r"uddg=([^&]+)", u)
        if m:
            return urllib.parse.unquote(m.group(1))
    return u


_LINK_BLOCK_RE = re.compile(r'<a\b[^>]*class="[^"]*result-link[^"]*"[^>]*>.*?</a>', re.S)
_SNIP_RE = re.compile(r'<td[^>]+class="[^"]*result-snippet[^"]*"[^>]*>(.*?)</td>', re.S)


def _extract_ddg(html: str) -> List[Tuple[str, str, str]]:
    """从 DuckDuckGo Lite 结果页提取 [(标题, url, 摘要)]。"""
    blocks = _LINK_BLOCK_RE.findall(html)
    snips = _SNIP_RE.findall(html)
    out: List[Tuple[str, str, str]] = []
    for i, block in enumerate(blocks):
        m = re.search(r'href="([^"]+)"', block)
        href = m.group(1) if m else ""
        title = _strip_html(block)
        snip = _strip_html(snips[i]) if i < len(snips) else ""
        out.append((title, _real_url(href), snip))
    return out


def _extract_bing(html: str) -> List[Tuple[str, str, str]]:
    """从必应（cn.bing.com）结果页提取 [(标题, url, 摘要)]。"""
    out: List[Tuple[str, str, str]] = []
    for block in re.findall(r'<li class="b_algo".*?</li>', html, re.S):
        m = re.search(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        url = m.group(1)
        title = _strip_html(m.group(2))
        sm = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
        snip = _strip_html(sm.group(1)) if sm else ""
        out.append((title, url, snip))
    return out


# --------------------------------------------------------------------------- 联网动作
def _search_config() -> dict:
    """读 config.yaml 的 search 配置；读不到则用默认（bing）。"""
    try:
        from . import config as _cfg_mod
        return _cfg_mod.load_config().get("search", {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def search(query: str, max_hits: int = 5) -> str:
    """联网搜索，返回人类可读结果。后端可配置（默认必应，国内可用、无需 key）。"""
    cfg = _search_config()
    provider = (cfg.get("provider") or "bing").lower()
    if provider == "api":
        out = _search_api(query, max_hits, cfg)
    elif provider == "ddg":
        out = _search_ddg(query, max_hits)
    else:
        out = _search_bing(query, max_hits)
    return out or "[INFO] 未检索到可解析结果，可改用 web_fetch(已知URL)，或建议查 Abaqus 官方文档（help.3ds.com）。"


def _search_bing(query: str, max_hits: int) -> str:
    url = "https://cn.bing.com/search?q=" + urllib.parse.quote(query)
    try:
        html = _http_get(url)
    except Exception as e:  # noqa: BLE001
        return f"[FAIL] 搜索请求失败：{e}。可改用 web_fetch(已知URL)，或建议查 Abaqus 官方文档（help.3ds.com）。"
    results = _extract_bing(html)
    if not results:
        return ""
    lines = [f"「{query}」搜索结果（{len(results)} 条）："]
    for title, link, snip in results[:max_hits]:
        lines.append(f"- {title}\n  {link}\n  {snip[:200]}")
    return "\n".join(lines)


def _search_ddg(query: str, max_hits: int) -> str:
    url = "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(query)
    try:
        html = _http_get(url)
    except Exception as e:  # noqa: BLE001
        return f"[FAIL] 搜索请求失败：{e}。"
    results = _extract_ddg(html)
    if not results:
        return ""
    lines = [f"「{query}」搜索结果（{len(results)} 条）："]
    for title, link, snip in results[:max_hits]:
        lines.append(f"- {title}\n  {link}\n  {snip[:200]}")
    return "\n".join(lines)


def _search_api(query: str, max_hits: int, cfg: dict) -> str:
    base = cfg.get("api_base") or ""
    if not base:
        return "[FAIL] search.provider=api 但未配置 api_base。"
    key_env = cfg.get("api_key_env") or ""
    key = os.environ.get(key_env, "") if key_env else ""
    sep = "&" if "?" in base else "?"
    url = f"{base}{sep}q={urllib.parse.quote(query)}"
    if key:
        url += f"&key={urllib.parse.quote(key)}"
    try:
        raw = _http_get_bytes(url)
        data = json.loads(_decode(raw))
    except Exception as e:  # noqa: BLE001
        return f"[FAIL] 搜索 API 请求/解析失败：{e}。"
    items = _pick_results(data)
    if not items:
        return ""
    lines = [f"「{query}」搜索结果（{len(items)} 条）："]
    for it in items[:max_hits]:
        t = it.get("title") or it.get("name") or ""
        u = it.get("url") or it.get("link") or it.get("href") or ""
        s = it.get("snippet") or it.get("summary") or it.get("description") or ""
        lines.append(f"- {t}\n  {u}\n  {str(s)[:200]}")
    return "\n".join(lines)


def _pick_results(data) -> List[dict]:
    """从搜索 API 返回的 JSON 里尽力提取结果列表（兼容多种常见结构）。"""
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("results", "items", "data", "webPages"):
        v = data.get(key)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
        if isinstance(v, dict):
            inner = v.get("value") or v.get("results") or v.get("items")
            if isinstance(inner, list):
                return [x for x in inner if isinstance(x, dict)]
    return []


def fetch(url: str, max_chars: int = 4000) -> str:
    """抓取网页正文（去标签提取文本，截断到 max_chars）。"""
    try:
        raw = _http_get_bytes(url)
    except Exception as e:  # noqa: BLE001
        return f"[FAIL] 抓取失败：{e}"
    text = _decode(raw)
    text = _strip_html(text)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n...（共 {len(text)} 字符，已截断，可换更具体的 URL 再抓）"
    return text or "[INFO] 页面无正文文本（可能是纯 JS 渲染页，建议换静态文档源）。"


def _http_get(url: str) -> str:
    return _decode(_http_get_bytes(url))


def _http_get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return resp.read(1_000_000)


def _decode(b: bytes) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")
