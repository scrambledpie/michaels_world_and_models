# Michael's World and Models

An MkDocs blogging site powered by Material for MkDocs and managed with `uv`.

## Run locally

```sh
uv sync
uv run mkdocs serve
```

Open the local URL that MkDocs prints, usually `http://127.0.0.1:8000`.

## Build

```sh
uv run mkdocs build
```

The static site is written to `site/`.

## Writing posts

Add Markdown files under `docs/blog/posts/`. Each post should include front matter:

```md
---
date: 2026-06-30
categories:
  - Notes
---

# Post title

Your post goes here.
```
