from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CURRENT_FILE = Path(__file__).resolve()
for _parent in [_CURRENT_FILE, *_CURRENT_FILE.parents]:
    if (_parent / "butler_main").exists():
        import sys

        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from butler_main.sources.skills.shared.workspace_layout import find_workspace_root, resolve_output_dir, skill_runtime_dir


USER_AGENT = "Butler-UpstreamSkill/0.1"
TIMEOUT = 20
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
SOURCE_OUTPUT_NAMES = {
    "trafilatura-web-extract": "web-article-extract",
    "feedparser-rss-ingest": "rss-feed-watch",
    "praw-reddit-ingest": "reddit-thread-read",
    "hackernews-api-ingest": "hackernews-thread-watch",
    "stackexchange-api-ingest": "stackexchange-search",
    "discourse-api-monitor": "discourse-topic-read",
    "github-discussions-graphql": "github-discussions-read",
    "arxiv-py-paper-retrieval": "arxiv-search",
    "semantic-scholar-api": "semantic-scholar-search",
    "openalex-pyalex": "openalex-search",
    "crossref-rest-metadata": "crossref-doi-enrich",
    "europepmc-rest-biomed": "europepmc-search",
}


def _request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> bytes:
    req_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    request = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def _get_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any] | list[Any]:
    return json.loads(_request(url, headers={"Accept": "application/json", **(headers or {})}).decode("utf-8"))


def _get_text(url: str, *, headers: dict[str, str] | None = None) -> str:
    return _request(url, headers=headers).decode("utf-8", errors="ignore")


def _ensure_output_dir(output_dir: str | Path) -> Path:
    path = Path(output_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").strip().lower()).strip("-") or "result"


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def _title_from_html(html: str) -> str:
    matched = re.search(r"(?is)<title>(.*?)</title>", html)
    return re.sub(r"\s+", " ", matched.group(1)).strip() if matched else ""


def _markdown_lines(title: str, meta: dict[str, Any], items: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", ""]
    for key, value in meta.items():
        lines.append(f"- {key}: {value}")
    if meta:
        lines.append("")
    lines.append("## Items")
    lines.append("")
    if not items:
        lines.append("- No items.")
        lines.append("")
        return "\n".join(lines)
    for item in items:
        heading = str(item.get("title") or item.get("name") or item.get("id") or "item")
        lines.append(f"### {heading}")
        lines.append("")
        for key, value in item.items():
            if key in {"title", "name"}:
                continue
            if value in ("", None, [], {}):
                continue
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
            lines.append(f"- {key}: {value}")
        lines.append("")
    return "\n".join(lines)


def _write_outputs(source_id: str, output_dir: str | Path, payload: dict[str, Any]) -> dict[str, str]:
    out = _ensure_output_dir(output_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{_slugify(source_id)}_{stamp}"
    json_path = out / f"{base}.json"
    md_path = out / f"{base}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = _markdown_lines(
        title=str(payload.get("title") or source_id),
        meta=dict(payload.get("meta") or {}),
        items=list(payload.get("items") or []),
    )
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _safe_get_env(name: str) -> str:
    return str(os.getenv(name) or "").strip()


def _parse_feed_entries(xml_text: str, *, limit: int) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    entries: list[dict[str, Any]] = []
    if root.tag.endswith("rss"):
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item")[:limit]:
            entries.append(
                {
                    "title": (item.findtext("title") or "").strip(),
                    "link": (item.findtext("link") or "").strip(),
                    "published": (item.findtext("pubDate") or "").strip(),
                    "summary": textwrap.shorten(_strip_html(item.findtext("description") or ""), width=500, placeholder="..."),
                }
            )
        return entries
    for entry in root.findall("atom:entry", ATOM_NS)[:limit]:
        href = ""
        for link in entry.findall("atom:link", ATOM_NS):
            href = link.attrib.get("href", "")
            if href:
                break
        entries.append(
            {
                "title": (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip(),
                "link": href,
                "published": (entry.findtext("atom:published", default="", namespaces=ATOM_NS) or entry.findtext("atom:updated", default="", namespaces=ATOM_NS)).strip(),
                "summary": textwrap.shorten(
                    _strip_html(entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or entry.findtext("atom:content", default="", namespaces=ATOM_NS)),
                    width=500,
                    placeholder="...",
                ),
            }
        )
    return entries


def _parse_atom_entries(xml_text: str, *, limit: int) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("atom:entry", ATOM_NS)[:limit]:
        authors = [author.findtext("atom:name", default="", namespaces=ATOM_NS) for author in entry.findall("atom:author", ATOM_NS)]
        primary_link = ""
        for link in entry.findall("atom:link", ATOM_NS):
            href = link.attrib.get("href", "")
            if href:
                primary_link = href
                break
        entries.append(
            {
                "title": (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip(),
                "id": (entry.findtext("atom:id", default="", namespaces=ATOM_NS) or "").strip(),
                "published": (entry.findtext("atom:published", default="", namespaces=ATOM_NS) or "").strip(),
                "updated": (entry.findtext("atom:updated", default="", namespaces=ATOM_NS) or "").strip(),
                "authors": [author for author in authors if author],
                "summary": textwrap.shorten(_strip_html(entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or ""), width=700, placeholder="..."),
                "link": primary_link,
            }
        )
    return entries


def _summarize_reddit_comments(children: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for child in children[:limit]:
        data = child.get("data") or {}
        items.append(
            {
                "id": data.get("id"),
                "author": data.get("author"),
                "score": data.get("score"),
                "body": textwrap.shorten(str(data.get("body") or ""), width=400, placeholder="..."),
                "permalink": f"https://www.reddit.com{data.get('permalink')}" if data.get("permalink") else "",
            }
        )
    return items


def handle_web_article_extract(args: argparse.Namespace) -> dict[str, Any]:
    if not args.url:
        raise SystemExit("--url is required for web article extraction")
    html = _get_text(args.url)
    title = _title_from_html(html) or args.url
    content_text = ""
    try:
        import trafilatura  # type: ignore

        content_text = str(trafilatura.extract(html, include_comments=False, include_tables=False) or "").strip()
    except Exception:
        content_text = _strip_html(html)
    item = {
        "title": title,
        "url": args.url,
        "text_excerpt": textwrap.shorten(content_text, width=1200, placeholder="..."),
        "content_length": len(content_text),
    }
    return {"title": "Web Article Extract", "meta": {"source": args.url}, "items": [item]}


def handle_rss_feed_watch(args: argparse.Namespace) -> dict[str, Any]:
    if not args.feed:
        raise SystemExit("--feed is required")
    xml_text = _get_text(args.feed, headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    entries: list[dict[str, Any]] = []
    try:
        import feedparser  # type: ignore

        parsed = feedparser.parse(xml_text)
        for entry in list(parsed.entries)[: args.limit]:
            entries.append(
                {
                    "title": str(getattr(entry, "title", "") or "").strip(),
                    "link": str(getattr(entry, "link", "") or "").strip(),
                    "published": str(getattr(entry, "published", "") or getattr(entry, "updated", "") or "").strip(),
                    "summary": textwrap.shorten(_strip_html(str(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")), width=500, placeholder="..."),
                }
            )
    except Exception:
        entries = _parse_feed_entries(xml_text, limit=args.limit)
    return {"title": "RSS Feed Watch", "meta": {"feed": args.feed, "limit": args.limit}, "items": entries}


def handle_reddit_thread_read(args: argparse.Namespace) -> dict[str, Any]:
    if args.url:
        url = args.url.rstrip("/")
        if not url.endswith(".json"):
            url += ".json"
        if "?" not in url:
            url += f"?limit={args.limit}"
        data = _get_json(url, headers={"Accept": "application/json"})
        if not isinstance(data, list) or len(data) < 2:
            raise SystemExit("unexpected reddit thread response")
        post = ((data[0] or {}).get("data") or {}).get("children") or []
        comments = ((data[1] or {}).get("data") or {}).get("children") or []
        post_data = (post[0] or {}).get("data") if post else {}
        items = [
            {
                "title": post_data.get("title"),
                "author": post_data.get("author"),
                "score": post_data.get("score"),
                "url": f"https://www.reddit.com{post_data.get('permalink')}" if post_data.get("permalink") else args.url,
                "selftext": textwrap.shorten(str(post_data.get("selftext") or ""), width=600, placeholder="..."),
                "comments": _summarize_reddit_comments(comments, limit=args.limit),
            }
        ]
        return {"title": "Reddit Thread Read", "meta": {"mode": "thread", "url": args.url}, "items": items}
    if not args.subreddit:
        raise SystemExit("--subreddit or --url is required")
    api_url = f"https://www.reddit.com/r/{urllib.parse.quote(args.subreddit)}/{urllib.parse.quote(args.sort)}.json?limit={args.limit}"
    data = _get_json(api_url, headers={"Accept": "application/json"})
    children = (((data or {}).get("data") or {}).get("children") or []) if isinstance(data, dict) else []
    items = []
    for child in children[: args.limit]:
        payload = child.get("data") or {}
        items.append(
            {
                "title": payload.get("title"),
                "author": payload.get("author"),
                "score": payload.get("score"),
                "comments": payload.get("num_comments"),
                "url": f"https://www.reddit.com{payload.get('permalink')}" if payload.get("permalink") else "",
                "created_utc": payload.get("created_utc"),
            }
        )
    return {"title": "Reddit Thread Read", "meta": {"mode": "subreddit", "subreddit": args.subreddit, "sort": args.sort}, "items": items}


def handle_hackernews_thread_watch(args: argparse.Namespace) -> dict[str, Any]:
    base = "https://hacker-news.firebaseio.com/v0"

    def fetch_item(item_id: int | str) -> dict[str, Any]:
        item = _get_json(f"{base}/item/{item_id}.json")
        return item if isinstance(item, dict) else {}

    if args.story_id:
        story = fetch_item(args.story_id)
        kids = list(story.get("kids") or [])[: args.limit]
        comments = []
        for kid in kids:
            child = fetch_item(kid)
            comments.append(
                {
                    "id": child.get("id"),
                    "author": child.get("by"),
                    "time": child.get("time"),
                    "text": textwrap.shorten(_strip_html(str(child.get("text") or "")), width=400, placeholder="..."),
                }
            )
        return {
            "title": "Hacker News Thread Watch",
            "meta": {"mode": "story", "story_id": args.story_id},
            "items": [
                {
                    "title": story.get("title"),
                    "author": story.get("by"),
                    "score": story.get("score"),
                    "url": story.get("url") or f"https://news.ycombinator.com/item?id={story.get('id')}",
                    "comments": comments,
                }
            ],
        }
    ids = _get_json(f"{base}/{args.mode}.json")
    if not isinstance(ids, list):
        raise SystemExit("unexpected hackernews ids response")
    items = []
    for story_id in ids[: args.limit]:
        story = fetch_item(story_id)
        items.append(
            {
                "title": story.get("title"),
                "author": story.get("by"),
                "score": story.get("score"),
                "comments": len(story.get("kids") or []),
                "url": story.get("url") or f"https://news.ycombinator.com/item?id={story.get('id')}",
                "id": story.get("id"),
            }
        )
    return {"title": "Hacker News Thread Watch", "meta": {"mode": args.mode, "limit": args.limit}, "items": items}


def handle_stackexchange_search(args: argparse.Namespace) -> dict[str, Any]:
    if not args.query:
        raise SystemExit("--query is required")
    params = {"order": "desc", "sort": "relevance", "site": args.site, "pagesize": args.limit, "q": args.query}
    if args.tagged:
        params["tagged"] = args.tagged
    url = "https://api.stackexchange.com/2.3/search/advanced?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    items = []
    for entry in list((data or {}).get("items") or [])[: args.limit]:
        items.append(
            {
                "title": entry.get("title"),
                "score": entry.get("score"),
                "answer_count": entry.get("answer_count"),
                "is_answered": entry.get("is_answered"),
                "link": entry.get("link"),
                "tags": entry.get("tags"),
            }
        )
    return {"title": "Stack Exchange Search", "meta": {"query": args.query, "site": args.site}, "items": items}


def handle_discourse_topic_read(args: argparse.Namespace) -> dict[str, Any]:
    if not args.base_url:
        raise SystemExit("--base-url is required")
    base = args.base_url.rstrip("/")
    headers = {}
    if args.api_key_env:
        api_key = _safe_get_env(args.api_key_env)
        api_username = _safe_get_env(args.api_username_env) if args.api_username_env else ""
        if api_key:
            headers["Api-Key"] = api_key
            if api_username:
                headers["Api-Username"] = api_username
    if args.topic_id:
        data = _get_json(f"{base}/t/{args.topic_id}.json", headers=headers)
        posts = list((data or {}).get("post_stream", {}).get("posts") or [])[: args.limit] if isinstance(data, dict) else []
        items = []
        for post in posts:
            items.append(
                {
                    "title": data.get("title"),
                    "author": post.get("username"),
                    "created_at": post.get("created_at"),
                    "cooked_excerpt": textwrap.shorten(_strip_html(str(post.get("cooked") or "")), width=500, placeholder="..."),
                }
            )
        return {"title": "Discourse Topic Read", "meta": {"base_url": base, "topic_id": args.topic_id}, "items": items}
    data = _get_json(f"{base}/latest.json", headers=headers)
    topics = list((data or {}).get("topic_list", {}).get("topics") or [])[: args.limit] if isinstance(data, dict) else []
    items = []
    for topic in topics:
        items.append(
            {
                "title": topic.get("title"),
                "posts_count": topic.get("posts_count"),
                "views": topic.get("views"),
                "slug": topic.get("slug"),
                "id": topic.get("id"),
                "url": f"{base}/t/{topic.get('slug')}/{topic.get('id')}",
            }
        )
    return {"title": "Discourse Topic Read", "meta": {"base_url": base, "mode": "latest"}, "items": items}


def handle_github_discussions_read(args: argparse.Namespace) -> dict[str, Any]:
    token = _safe_get_env(args.github_token_env or "GITHUB_TOKEN")
    if not token:
        raise SystemExit(f"missing GitHub token env: {args.github_token_env or 'GITHUB_TOKEN'}")
    if not args.owner or not args.repo:
        raise SystemExit("--owner and --repo are required")
    if args.number:
        query = """
        query($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            discussion(number: $number) {
              title
              url
              category { name }
              comments(first: 10) {
                nodes { author { login } bodyText createdAt }
              }
            }
          }
        }
        """
        variables = {"owner": args.owner, "repo": args.repo, "number": int(args.number)}
    else:
        query = """
        query($owner: String!, $repo: String!, $limit: Int!) {
          repository(owner: $owner, name: $repo) {
            discussions(first: $limit, orderBy: {field: UPDATED_AT, direction: DESC}) {
              nodes {
                number
                title
                url
                author { login }
                category { name }
                updatedAt
              }
            }
          }
        }
        """
        variables = {"owner": args.owner, "repo": args.repo, "limit": int(args.limit)}
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    data = json.loads(
        _request(
            "https://api.github.com/graphql",
            method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
            body=payload,
        ).decode("utf-8")
    )
    repository = ((data or {}).get("data") or {}).get("repository") or {}
    items: list[dict[str, Any]] = []
    if args.number:
        discussion = repository.get("discussion") or {}
        for comment in list((discussion.get("comments") or {}).get("nodes") or [])[: args.limit]:
            items.append(
                {
                    "title": discussion.get("title"),
                    "url": discussion.get("url"),
                    "category": ((discussion.get("category") or {}).get("name") or ""),
                    "author": ((comment.get("author") or {}).get("login") or ""),
                    "comment": textwrap.shorten(str(comment.get("bodyText") or ""), width=500, placeholder="..."),
                    "created_at": comment.get("createdAt"),
                }
            )
    else:
        for discussion in list((repository.get("discussions") or {}).get("nodes") or [])[: args.limit]:
            items.append(
                {
                    "number": discussion.get("number"),
                    "title": discussion.get("title"),
                    "url": discussion.get("url"),
                    "category": ((discussion.get("category") or {}).get("name") or ""),
                    "author": ((discussion.get("author") or {}).get("login") or ""),
                    "updated_at": discussion.get("updatedAt"),
                }
            )
    return {"title": "GitHub Discussions Read", "meta": {"owner": args.owner, "repo": args.repo}, "items": items}


def handle_arxiv_search(args: argparse.Namespace) -> dict[str, Any]:
    if not args.query:
        raise SystemExit("--query is required")
    params = {"search_query": f"all:{args.query}", "start": 0, "max_results": args.limit, "sortBy": args.sort_by, "sortOrder": args.sort_order}
    xml_text = _get_text("http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params))
    return {"title": "arXiv Search", "meta": {"query": args.query, "sort_by": args.sort_by}, "items": _parse_atom_entries(xml_text, limit=args.limit)}


def handle_semantic_scholar_search(args: argparse.Namespace) -> dict[str, Any]:
    headers = {}
    api_key = _safe_get_env(args.semantic_scholar_key_env or "SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    if args.paper_id:
        fields = "title,authors,year,abstract,url,venue,citationCount"
        data = _get_json(f"https://api.semanticscholar.org/graph/v1/paper/{urllib.parse.quote(args.paper_id)}?fields={urllib.parse.quote(fields)}", headers=headers)
        paper = data if isinstance(data, dict) else {}
        items = [
            {
                "title": paper.get("title"),
                "authors": [author.get("name") for author in list(paper.get("authors") or []) if author.get("name")],
                "year": paper.get("year"),
                "venue": paper.get("venue"),
                "citation_count": paper.get("citationCount"),
                "url": paper.get("url"),
                "abstract": textwrap.shorten(str(paper.get("abstract") or ""), width=700, placeholder="..."),
            }
        ]
        return {"title": "Semantic Scholar Search", "meta": {"paper_id": args.paper_id}, "items": items}
    if not args.query:
        raise SystemExit("--query or --paper-id is required")
    fields = "title,authors,year,url,venue,citationCount,abstract"
    data = _get_json("https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode({"query": args.query, "limit": args.limit, "fields": fields}), headers=headers)
    items = []
    for paper in list((data or {}).get("data") or [])[: args.limit]:
        items.append(
            {
                "title": paper.get("title"),
                "authors": [author.get("name") for author in list(paper.get("authors") or []) if author.get("name")],
                "year": paper.get("year"),
                "venue": paper.get("venue"),
                "citation_count": paper.get("citationCount"),
                "url": paper.get("url"),
                "abstract": textwrap.shorten(str(paper.get("abstract") or ""), width=700, placeholder="..."),
            }
        )
    return {"title": "Semantic Scholar Search", "meta": {"query": args.query}, "items": items}


def handle_openalex_search(args: argparse.Namespace) -> dict[str, Any]:
    if not args.query:
        raise SystemExit("--query is required")
    params = {"search": args.query, "per-page": args.limit}
    if args.openalex_mailto:
        params["mailto"] = args.openalex_mailto
    data = _get_json(f"https://api.openalex.org/{args.entity_type}?" + urllib.parse.urlencode(params))
    items = []
    for item in list((data or {}).get("results") or [])[: args.limit]:
        items.append(
            {
                "id": item.get("id"),
                "title": item.get("display_name") or item.get("title"),
                "publication_year": item.get("publication_year"),
                "cited_by_count": item.get("cited_by_count"),
                "type": item.get("type"),
                "host_venue": ((item.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
                "url": item.get("id"),
            }
        )
    return {"title": "OpenAlex Search", "meta": {"query": args.query, "entity_type": args.entity_type}, "items": items}


def handle_crossref_doi_enrich(args: argparse.Namespace) -> dict[str, Any]:
    headers = {"mailto": args.mailto} if args.mailto else {}
    if args.doi:
        data = _get_json(f"https://api.crossref.org/works/{urllib.parse.quote(args.doi)}", headers=headers)
        message = (data or {}).get("message") or {}
        items = [{"title": " ".join(message.get("title") or []), "doi": message.get("DOI"), "type": message.get("type"), "published": message.get("created", {}).get("date-time"), "publisher": message.get("publisher"), "url": message.get("URL")}]
        return {"title": "Crossref DOI Enrich", "meta": {"doi": args.doi}, "items": items}
    if not args.query:
        raise SystemExit("--query or --doi is required")
    data = _get_json("https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": args.query, "rows": args.limit}), headers=headers)
    entries = list(((data or {}).get("message") or {}).get("items") or [])[: args.limit]
    items = []
    for entry in entries:
        items.append({"title": " ".join(entry.get("title") or []), "doi": entry.get("DOI"), "type": entry.get("type"), "publisher": entry.get("publisher"), "published": ((entry.get("created") or {}).get("date-time") or ""), "url": entry.get("URL")})
    return {"title": "Crossref DOI Enrich", "meta": {"query": args.query}, "items": items}


def handle_europepmc_search(args: argparse.Namespace) -> dict[str, Any]:
    if not args.query:
        raise SystemExit("--query is required")
    data = _get_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode({"query": args.query, "format": "json", "pageSize": args.limit}))
    entries = list(((data or {}).get("resultList") or {}).get("result") or [])[: args.limit]
    items = []
    for entry in entries:
        items.append({"title": entry.get("title"), "author_string": entry.get("authorString"), "journal": entry.get("journalTitle"), "pub_year": entry.get("pubYear"), "doi": entry.get("doi"), "pmid": entry.get("pmid")})
    return {"title": "Europe PMC Search", "meta": {"query": args.query}, "items": items}


SOURCE_HANDLERS = {
    "trafilatura-web-extract": handle_web_article_extract,
    "feedparser-rss-ingest": handle_rss_feed_watch,
    "praw-reddit-ingest": handle_reddit_thread_read,
    "hackernews-api-ingest": handle_hackernews_thread_watch,
    "stackexchange-api-ingest": handle_stackexchange_search,
    "discourse-api-monitor": handle_discourse_topic_read,
    "github-discussions-graphql": handle_github_discussions_read,
    "arxiv-py-paper-retrieval": handle_arxiv_search,
    "semantic-scholar-api": handle_semantic_scholar_search,
    "openalex-pyalex": handle_openalex_search,
    "crossref-rest-metadata": handle_crossref_doi_enrich,
    "europepmc-rest-biomed": handle_europepmc_search,
}


def build_parser(source_id: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Run Butler upstream skill runtime for {source_id}")
    parser.add_argument("--output-dir", default="", help="Output directory; defaults to 工作区/Butler/runtime/skills/<skill-name>")
    parser.add_argument("--limit", type=int, default=5, help="Max items")
    parser.add_argument("--url", default="", help="Target URL")
    parser.add_argument("--feed", default="", help="Feed URL")
    parser.add_argument("--subreddit", default="", help="Reddit subreddit")
    parser.add_argument("--sort", default="hot", help="Sort order")
    parser.add_argument("--mode", default="topstories", help="List mode")
    parser.add_argument("--story-id", default="", help="Specific story id")
    parser.add_argument("--query", default="", help="Search query")
    parser.add_argument("--site", default="stackoverflow", help="Stack Exchange site")
    parser.add_argument("--tagged", default="", help="Tagged filter")
    parser.add_argument("--base-url", default="", help="Base URL")
    parser.add_argument("--topic-id", default="", help="Topic id")
    parser.add_argument("--api-key-env", default="", help="Env var name for API key")
    parser.add_argument("--api-username-env", default="", help="Env var name for API username")
    parser.add_argument("--owner", default="", help="Repository owner")
    parser.add_argument("--repo", default="", help="Repository name")
    parser.add_argument("--number", default="", help="Discussion number")
    parser.add_argument("--github-token-env", default="GITHUB_TOKEN", help="GitHub token env var")
    parser.add_argument("--sort-by", default="relevance", help="Source-specific sort field")
    parser.add_argument("--sort-order", default="descending", help="Source-specific sort order")
    parser.add_argument("--paper-id", default="", help="Paper id")
    parser.add_argument("--semantic-scholar-key-env", default="SEMANTIC_SCHOLAR_API_KEY", help="Semantic Scholar API key env var")
    parser.add_argument("--entity-type", default="works", help="OpenAlex entity type")
    parser.add_argument("--openalex-mailto", default="", help="Mailto for OpenAlex polite pool")
    parser.add_argument("--doi", default="", help="DOI")
    parser.add_argument("--mailto", default="", help="Contact mailto")
    return parser


def main(*, source_id: str) -> int:
    handler = SOURCE_HANDLERS.get(source_id)
    if handler is None:
        raise SystemExit(f"unsupported source_id: {source_id}")
    parser = build_parser(source_id)
    args = parser.parse_args()
    workspace_root = find_workspace_root(Path.cwd())
    runtime_name = SOURCE_OUTPUT_NAMES.get(source_id, _slugify(source_id))
    args.output_dir = str(
        resolve_output_dir(
            workspace_root,
            args.output_dir,
            default_path=skill_runtime_dir(workspace_root, runtime_name),
        )
    )
    try:
        payload = handler(args)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"HTTP error: {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"network error: {exc.reason}") from exc
    payload.setdefault("meta", {})
    payload["meta"]["source_id"] = source_id
    payload["meta"]["generated_at"] = datetime.now(timezone.utc).isoformat()
    outputs = _write_outputs(source_id, args.output_dir, payload)
    print(json.dumps({"ok": True, "source_id": source_id, "output_files": outputs, "items": len(payload.get("items") or [])}, ensure_ascii=False))
    return 0


__all__ = ["main"]
