from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

import yaml
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page
from mkdocs.utils import get_relative_url
from mkdocs.utils.meta import YAML_RE
from pymdownx.slugs import slugify


GRAPH_PAGE = "graph.md"
POST_DIR = "blog/posts"
NODE_WIDTH = 132
NODE_HEIGHT = 44
X_GAP = 58
Y_GAP = 108
MARGIN_X = 36
MARGIN_Y = 42


def on_page_markdown(
    markdown: str,
    *,
    page: Page,
    config: MkDocsConfig,
    files: Files,
) -> str | None:
    if page.file.src_uri != GRAPH_PAGE:
        return None

    posts = _load_posts(config, files, page)
    if not posts:
        return "# Graph\n\nNo posts found.\n"

    ranks = _compute_ranks(posts)
    levels = _group_by_rank(posts, ranks)
    positions, width, height = _layout(levels)
    svg = _render_svg(posts, positions, width, height)

    return "\n".join(
        [
            "# Graph",
            "",
            "Arrows point from each post upward to the posts listed in its `refs` metadata.",
            "",
            '<div class="post-graph">',
            svg,
            "</div>",
            "",
        ]
    )


def _load_posts(config: MkDocsConfig, files: Files, page: Page) -> dict[str, dict]:
    docs_dir = Path(config.docs_dir)
    posts: dict[str, dict] = {}

    for path in sorted((docs_dir / POST_DIR).glob("*.md")):
        text = path.read_text(encoding="utf-8-sig")
        match = YAML_RE.match(text)
        if not match:
            continue

        meta = yaml.safe_load(match.group(1)) or {}
        title = _title_from_markdown(text[match.end() :]) or path.stem
        name = str(meta.get("name") or title)
        refs = [str(ref) for ref in meta.get("refs", [])]
        url = _post_url(meta, path, page, files)

        posts[name] = {
            "name": name,
            "refs": refs,
            "url": url,
        }

    return posts


def _title_from_markdown(markdown: str) -> str | None:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()

    return None


def _post_url(meta: dict, path: Path, page: Page, files: Files) -> str:
    source = f"{POST_DIR}/{path.name}"
    file = files.get_file_from_path(source)
    if file and file.url:
        return get_relative_url(file.url, page.url)

    created = meta.get("date", date.today())
    if isinstance(created, datetime):
        created = created.date()
    if not isinstance(created, date):
        created = datetime.fromisoformat(str(created)).date()

    title = str(meta.get("name") or path.stem)
    slug = str(meta.get("slug") or slugify(case="lower")(title, "-"))
    absolute = f"blog/{created:%Y/%m/%d}/{slug}/"
    return get_relative_url(absolute, page.url)


def _compute_ranks(posts: dict[str, dict]) -> dict[str, int]:
    ranks: dict[str, int] = {}
    visiting: set[str] = set()

    def rank(name: str) -> int:
        if name in ranks:
            return ranks[name]
        if name in visiting:
            return 0

        visiting.add(name)
        refs = [ref for ref in posts[name]["refs"] if ref in posts]
        ranks[name] = 0 if not refs else 1 + max(rank(ref) for ref in refs)
        visiting.remove(name)
        return ranks[name]

    for name in posts:
        rank(name)

    return ranks


def _group_by_rank(posts: dict[str, dict], ranks: dict[str, int]) -> dict[int, list[str]]:
    levels: dict[int, list[str]] = defaultdict(list)
    for name in posts:
        levels[ranks[name]].append(name)

    for names in levels.values():
        names.sort()

    return dict(sorted(levels.items()))


def _layout(levels: dict[int, list[str]]) -> tuple[dict[str, tuple[int, int]], int, int]:
    max_nodes = max(len(names) for names in levels.values())
    width = max_nodes * NODE_WIDTH + (max_nodes - 1) * X_GAP + MARGIN_X * 2
    height = len(levels) * NODE_HEIGHT + (len(levels) - 1) * Y_GAP + MARGIN_Y * 2
    positions: dict[str, tuple[int, int]] = {}

    for row, rank in enumerate(levels):
        names = levels[rank]
        row_width = len(names) * NODE_WIDTH + (len(names) - 1) * X_GAP
        start_x = (width - row_width) // 2
        y = MARGIN_Y + row * (NODE_HEIGHT + Y_GAP) + NODE_HEIGHT // 2

        for index, name in enumerate(names):
            x = start_x + index * (NODE_WIDTH + X_GAP) + NODE_WIDTH // 2
            positions[name] = (x, y)

    return positions, width, height


def _render_svg(
    posts: dict[str, dict],
    positions: dict[str, tuple[int, int]],
    width: int,
    height: int,
) -> str:
    parts = [
        (
            f'<svg class="post-graph__svg" viewBox="0 0 {width} {height}" '
            'role="img" aria-labelledby="post-graph-title">'
        ),
        '<title id="post-graph-title">Post reference graph</title>',
        "<defs>",
        (
            '<marker id="post-graph-arrow" markerWidth="10" markerHeight="10" '
            'refX="5" refY="5" orient="auto">'
            '<path d="M 0 0 L 10 5 L 0 10 z" class="post-graph__arrowhead" />'
            "</marker>"
        ),
        "</defs>",
    ]

    for child, post in posts.items():
        child_x, child_y = positions[child]
        for parent in post["refs"]:
            if parent not in positions:
                continue

            parent_x, parent_y = positions[parent]
            parts.append(
                (
                    '<path class="post-graph__edge" '
                    f'd="M {child_x} {child_y - NODE_HEIGHT // 2} '
                    f'C {child_x} {child_y - Y_GAP // 2}, '
                    f'{parent_x} {parent_y + Y_GAP // 2}, '
                    f'{parent_x} {parent_y + NODE_HEIGHT // 2}" '
                    'marker-end="url(#post-graph-arrow)" />'
                )
            )

    for name, post in posts.items():
        x, y = positions[name]
        left = x - NODE_WIDTH // 2
        top = y - NODE_HEIGHT // 2
        label = escape(name)
        url = escape(post["url"])
        parts.extend(
            [
                f'<a href="{url}" class="post-graph__node-link">',
                (
                    f'<rect class="post-graph__node" x="{left}" y="{top}" '
                    f'width="{NODE_WIDTH}" height="{NODE_HEIGHT}" rx="8" />'
                ),
                (
                    f'<text class="post-graph__label" x="{x}" y="{y}" '
                    'dominant-baseline="middle" text-anchor="middle">'
                    f"{label}</text>"
                ),
                "</a>",
            ]
        )

    parts.append("</svg>")
    return "\n".join(parts)
