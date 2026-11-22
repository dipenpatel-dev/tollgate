"""
module_name: build_index.py
description: Build or update the search index. Three collections: vault, tickets, references, plus optional code and standards. Incremental by file time.
author: Dipen Patel (dipenpatel-dev)
date:
version: 1.0.0
change_log:
  1.0.0: Ported from the personal vector search. Folders come from the path loader. Embedder is injectable
         (hash, local, auto). Context generation is off unless --context is given. Reference chunks added
         by reference_add.py are kept on rebuild.
  1.1.0: Meeting files (under the meetings path) are split by size. The vault walk skips the archive, work and
         landing folders (config.VAULT_ONLY_SKIP_DIRS). Optional code (repos path) and standards (standards path) collections, off until set.
  1.2.0: The vault walk skips the top-level archive, work, history, landing and output folders (by path, from the
         layout). Files that are links pointing outside their source folder are skipped. Stale entries are
         removed per collection, so one unreadable file no longer leaves ghost entries.
usage: python3 build_index.py [--full] [--source vault|tickets|references|code|standards] [--embedder hash|local|auto] [--context]
  --full      Re-embed everything (drops build chunks, keeps chunks added with reference_add.py)
  --source    Limit to one collection (default: all)
  --embedder  Choose the embedder. Default: TOLLGATE_EMBEDDER, else a local model if present, else hash.
  --context   Add a short generated description to each chunk (needs a provider, off by default)

Chunking by file type:
  .md heading based (H1 to H3) with overlap; .py top level def and class; .sql statements;
  .ipynb one chunk per cell; .epub one section per chapter (needs ebooklib and bs4, optional); other: paragraphs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import pathlib
import re
import sys
import time
from dataclasses import dataclass, field

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402
import embedder as embedder_mod  # noqa: E402
from core.paths import NotSetUp, get_path  # noqa: E402

logger = logging.getLogger(__name__)

# Transcripts have one heading, so files under the meetings path are split by size instead.
# Meetings are walked inside the vault collection, so this is a per-file check (see _meetings_prefix).
SIZE_CHUNKED_SOURCES = {"meetings"}
EXTENSIONS = {
    "vault": {".md"},
    "tickets": {".md"},
    "references": {".md", ".txt", ".rst", ".epub"},
    "code": {".md", ".py", ".sql", ".ipynb", ".yaml", ".yml"},
    "standards": {".md"},
}


@dataclass
class FileRecord:
    fpath: pathlib.Path
    file_key: str
    collection: str
    mtime: str
    doc_text: str
    chunks: list = field(default_factory=list)


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk(heading: str, content: str, file_key: str) -> dict:
    raw = len(content)
    out = {"heading": heading, "content": content[: config.MAX_CHUNK_CHARS], "file": file_key}
    if raw > config.MAX_CHUNK_CHARS:
        out["truncated"] = True
    return out


def add_overlap(chunks: list[dict]) -> list[dict]:
    if config.OVERLAP_CHARS <= 0 or len(chunks) < 2:
        return chunks
    result = [chunks[0]]
    for i in range(1, len(chunks)):
        tail = chunks[i - 1]["content"][-config.OVERLAP_CHARS:]
        joined = f"[...]\n{tail}\n\n{chunks[i]['content']}"
        new = {**chunks[i], "content": joined[: config.MAX_CHUNK_CHARS]}
        if len(joined) > config.MAX_CHUNK_CHARS:
            new["truncated"] = True
        result.append(new)
    return result


def chunk_markdown(text: str, file_key: str) -> list[dict]:
    chunks, heading, lines = [], "(top)", []

    def flush():
        content = "\n".join(lines).strip()
        if len(content) >= config.MIN_CHUNK_CHARS:
            chunks.append(_chunk(heading, content, file_key))

    for line in text.splitlines():
        m = re.match(r"^(#{1,3})\s+(.+)", line)
        if m:
            flush()
            heading, lines = m.group(2).strip(), []
        else:
            lines.append(line)
    flush()
    return add_overlap(chunks)


def chunk_python(text: str, file_key: str) -> list[dict]:
    chunks, src = [], text.splitlines()
    starts = [i for i, ln in enumerate(src) if re.match(r"^(def |class |async def )", ln)]
    if not starts:
        content = text.strip()
        if len(content) >= config.MIN_CHUNK_CHARS:
            chunks.append(_chunk("(module)", content, file_key))
        return add_overlap(chunks)
    if starts[0] > 0:
        content = "\n".join(src[: starts[0]]).strip()
        if len(content) >= config.MIN_CHUNK_CHARS:
            chunks.append(_chunk("(module header)", content, file_key))
    for i, pos in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(src)
        block = src[pos:end]
        nm = re.match(r"(?:async )?(?:def|class)\s+(\w+)", block[0])
        content = "\n".join(block).strip()
        if len(content) >= config.MIN_CHUNK_CHARS:
            chunks.append(_chunk(nm.group(1) if nm else f"block_{i}", content, file_key))
    return add_overlap(chunks)


def chunk_sql(text: str, file_key: str) -> list[dict]:
    chunks = []
    for i, block in enumerate(re.split(r";\s*\n\s*\n|;\s*$", text, flags=re.MULTILINE)):
        content = block.strip()
        if len(content) < config.MIN_CHUNK_CHARS:
            continue
        first = next((ln.strip() for ln in content.splitlines()
                      if ln.strip() and not ln.strip().startswith(("/*", "*"))), "")
        if first.startswith("--"):
            heading = first.lstrip("-").strip()[:80]
        elif re.match(r"(?i)^(CREATE|ALTER|DROP|INSERT|SELECT|WITH|MERGE|UPDATE|DELETE)\b", first):
            heading = first[:80]
        else:
            heading = f"SQL block {i + 1}"
        chunks.append(_chunk(heading, content, file_key))
    return add_overlap(chunks)


def chunk_notebook(text: str, file_key: str) -> list[dict]:
    try:
        nb = json.loads(text)
    except json.JSONDecodeError:
        return []
    chunks = []
    for i, cell in enumerate(nb.get("cells", [])):
        src = cell.get("source", [])
        content = ("".join(src) if isinstance(src, list) else str(src)).strip()
        if len(content) < config.MIN_CHUNK_CHARS:
            continue
        first = content.splitlines()[0]
        heading = first.lstrip("#").strip()[:80] if first.startswith("#") else f"Cell {i + 1} ({cell.get('cell_type', 'code')})"
        chunks.append(_chunk(heading, content, file_key))
    return add_overlap(chunks)


def chunk_text(text: str, file_key: str) -> list[dict]:
    chunks, buf, buf_len, idx = [], [], 0, 0
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if buf_len + len(para) > config.MAX_CHUNK_CHARS and buf:
            content = "\n\n".join(buf)
            if len(content) >= config.MIN_CHUNK_CHARS:
                chunks.append(_chunk(f"section {idx + 1}", content, file_key))
            buf, buf_len, idx = [para], len(para), idx + 1
        else:
            buf.append(para)
            buf_len += len(para) + 2
    if buf:
        content = "\n\n".join(buf)
        if len(content) >= config.MIN_CHUNK_CHARS:
            chunks.append(_chunk(f"section {idx + 1}", content, file_key))
    return add_overlap(chunks)


def chunk_epub(fpath: pathlib.Path, file_key: str) -> list[dict]:
    """Optional. Needs ebooklib and bs4; raises ImportError otherwise (the caller skips the file)."""
    try:
        import ebooklib
        from bs4 import BeautifulSoup
        from ebooklib import epub
    except ImportError as exc:
        raise ImportError(f"{exc}. To index epub books: pip install -r scripts/requirements-epub.txt") from exc
    book = epub.read_epub(str(fpath), options={"ignore_ncx": True})
    chunks = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        tag = soup.find(["h1", "h2", "h3"])
        heading = tag.get_text(strip=True) if tag else item.get_name()
        text = soup.get_text(separator="\n\n", strip=True)
        if len(text) < config.MIN_CHUNK_CHARS:
            continue
        for chunk in chunk_text(text, file_key):
            chunk["heading"] = heading
            chunks.append(chunk)
    return chunks


def chunk_file(text: str, file_key: str, ext: str) -> list[dict]:
    dispatch = {".md": chunk_markdown, ".py": chunk_python, ".sql": chunk_sql, ".ipynb": chunk_notebook}
    return dispatch.get(ext, chunk_text)(text, file_key)


def chunk_id(file_key: str, heading: str, index: int) -> str:
    return hashlib.md5(f"{file_key}::{heading}::{index}".encode()).hexdigest()


# ── Discovery ─────────────────────────────────────────────────────────────────

def _prefix_for(folder: pathlib.Path, vault: pathlib.Path | None, label: str) -> str:
    """File keys are relative to the vault when the folder lives inside it."""
    try:
        if vault is not None:
            return str(folder.resolve().relative_to(vault.resolve()))
    except ValueError:
        pass
    return label


def _inside(folder: pathlib.Path, vault: pathlib.Path | None) -> bool:
    if vault is None:
        return False
    try:
        folder.resolve().relative_to(vault.resolve())
        return True
    except ValueError:
        return False


def _meetings_prefix() -> str | None:
    """Key prefix of the meetings folder, or None when the path is not set up."""
    try:
        meetings = get_path("meetings")
        vault = get_path("vault")
    except NotSetUp:
        return None
    return _prefix_for(meetings, vault, "meetings")


def source_roots() -> list[tuple[str, pathlib.Path, str]]:
    """Return (collection, root folder, key prefix). Missing path names are skipped.

    `code` (the repos path, when it is not inside the vault) and `standards` (the standards path)
    are listed only when their folder is set and not empty. Otherwise they are off and not mentioned.
    """
    vault = None
    roots = []
    try:
        vault = get_path("vault")
    except NotSetUp:
        pass
    if vault is not None:
        roots.append(("vault", vault, ""))
        # A meetings folder outside the vault is still indexed, in the vault collection.
        try:
            meetings = get_path("meetings")
            if not _inside(meetings, vault):
                roots.append(("vault", meetings, "meetings"))
        except NotSetUp:
            pass
    for name in ("tickets", "references"):
        try:
            folder = get_path(name)
        except NotSetUp:
            continue
        roots.append((name, folder, _prefix_for(folder, vault, name)))
    for name, path_name in (("code", "repos"), ("standards", "standards")):
        try:
            folder = get_path(path_name)
        except NotSetUp:
            continue
        if name == "code" and _inside(folder, vault):
            continue
        if not folder.is_dir() or not any(folder.iterdir()):
            continue  # missing or empty: stays off, no warning
        roots.append((name, folder, _prefix_for(folder, vault, path_name)))
    return roots


def active_collections() -> list[str]:
    """The three core collections, plus code and standards when their folders are set."""
    on = {c for c, _r, _p in source_roots()}
    return list(config.COLLECTION_NAMES) + [n for n in config.OPTIONAL_COLLECTIONS if n in on]


def real_inside(path: pathlib.Path, root: pathlib.Path) -> bool:
    """True when the real location of path (links followed) is inside root."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def find_source_files(only: str | None = None, errors: dict | None = None) -> list[tuple[pathlib.Path, str, str]]:
    """Every file to index as (path, key, collection).

    Files whose real location is outside their source folder (a link to somewhere else) are skipped.
    errors, when given, gets {collection: count} of folders the walk could not read.
    """
    roots = source_roots()
    nested = {r.resolve() for c, r, _ in roots if c != "vault"}
    base_skip = config.skip_dirs()
    extra_skip = {"code": config.CODE_SKIP_DIRS, "standards": config.STANDARDS_SKIP_DIRS}
    vault_skip = config.vault_skip_paths()
    results = []
    for collection, root, prefix in roots:
        if only and collection != only:
            continue
        if not root.is_dir():
            logger.warning("Skipping %s (folder not found)", collection)
            continue
        skip = base_skip | extra_skip.get(collection, frozenset())

        def on_error(exc, _c=collection):
            logger.error("Could not read a folder in %s: %s", _c, exc)
            if errors is not None:
                errors[_c] = errors.get(_c, 0) + 1

        for dirpath, dirs, files in os.walk(root, onerror=on_error):
            here = pathlib.Path(dirpath)
            dirs[:] = [d for d in dirs
                       if d not in skip and not d.startswith(".")
                       and not (collection == "vault" and (here / d).resolve() in nested)
                       and not (collection == "vault" and (here / d).relative_to(root).as_posix().lower() in vault_skip)]
            for name in sorted(files):
                path = here / name
                if name.startswith(".") or path.suffix.lower() not in EXTENSIONS[collection]:
                    continue
                if path.is_symlink() and not real_inside(path, root):
                    logger.warning("Skipping %s (link points outside the folder)", path)
                    continue
                rel = path.relative_to(root).as_posix()
                results.append((path, f"{prefix}/{rel}" if prefix else rel, collection))
    return results


# ── State and storage ─────────────────────────────────────────────────────────

def load_state(state_file: pathlib.Path) -> dict:
    try:
        return json.loads(state_file.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state: dict, state_file: pathlib.Path) -> None:
    state_file.write_text(json.dumps(state, indent=2))


def _delete_file(collection, file_key: str, origin: str = "build") -> int:
    existing = collection.get(where={"$and": [{"file": file_key}, {"origin": origin}]})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
    return len(existing["ids"])


def reconcile_orphans(collection, state: dict, current_keys: set[str]) -> int:
    """Remove chunks and state entries for files no longer on disk (only chunks this script built)."""
    deleted = 0
    for key in [k for k in state if k not in current_keys]:
        deleted += _delete_file(collection, key)
        state.pop(key, None)
    return deleted


def embed_records(records, collection, emb, state, state_file, origin="build", tags="") -> int:
    added = 0
    for rec in records:
        _delete_file(collection, rec.file_key, origin)
        ids, docs, metas = [], [], []
        for i, chunk in enumerate(rec.chunks):
            ids.append(chunk_id(rec.file_key, chunk["heading"], i))
            docs.append(chunk["content"])
            metas.append({
                "file": chunk["file"], "heading": chunk["heading"], "source": rec.collection,
                "embedding_model": emb.name, "truncated": bool(chunk.get("truncated", False)),
                "origin": origin, "tags": tags,
            })
        # The vector is made from the file name, the heading and the text. The stored text is the chunk only.
        label = re.sub(r"[^A-Za-z0-9]+", " ", pathlib.PurePosixPath(rec.file_key).stem)
        to_embed = [f"{label}. {c['heading']}. {d}" for c, d in zip(rec.chunks, docs)]
        vectors = emb.encode(to_embed, normalize_embeddings=config.NORMALIZE_EMBEDDINGS)
        collection.add(ids=ids, documents=docs, metadatas=metas, embeddings=vectors)
        state[rec.file_key] = rec.mtime
        added += len(rec.chunks)
    save_state(state, state_file)
    return added


def read_chunks(fpath: pathlib.Path, file_key: str, collection: str) -> tuple[list[dict], str]:
    ext = fpath.suffix.lower()
    if ext == ".epub":
        chunks = chunk_epub(fpath, file_key)
        return chunks, " ".join(c["content"] for c in chunks)[: config.CONTEXT_MAX_DOC_CHARS]
    text = fpath.read_text(encoding="utf-8", errors="ignore")
    meetings = _meetings_prefix()
    if collection in SIZE_CHUNKED_SOURCES or (meetings and file_key.startswith(meetings + "/")):
        return chunk_text(text, file_key), text
    return chunk_file(text, file_key, ext), text


def _run_context_pass(records: list[FileRecord]) -> int:
    """Optional pass: add a generated description to each chunk. Needs a provider; see context_generator.py."""
    from context_generator import batch_generate_context, load_cache, save_cache
    cache = load_cache()
    pairs = [(r.doc_text, c["content"]) for r in records for c in r.chunks]
    calls = sum(1 for d, c in pairs if hashlib.sha256((d + c).encode()).hexdigest() not in cache)
    results = batch_generate_context(pairs, cache=cache)
    idx = 0
    for r in records:
        for chunk in r.chunks:
            if results[idx]:
                chunk["content"] = f"{results[idx]}\n\n{chunk['content']}"[: config.MAX_CHUNK_CHARS]
            idx += 1
    save_cache(cache)
    return calls


# ── Orchestration ─────────────────────────────────────────────────────────────

def build(only: str | None = None, full: bool = False, embedder_name: str | None = None,
          context: bool = False, emb=None) -> dict:
    """Index the folders. Returns a summary dict. `emb` injects an embedder (tests)."""
    root = config.index_root()
    root.mkdir(parents=True, exist_ok=True)
    emb = emb or embedder_mod.get_embedder(embedder_name)
    if not full or only:
        embedder_mod.check_marker(root, emb)
    active = active_collections()
    if only and only not in active:
        raise ValueError(f"{only} is off: set its folder first (the {'repos' if only == 'code' else only} path)")
    names = [only] if only else active
    registry = {}
    for name in names:
        folder = root / name
        folder.mkdir(parents=True, exist_ok=True)
        client = config.chroma_client(folder)
        col = client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
        state_file = folder / "build_state.json"
        if full:
            existing = col.get(where={"origin": "build"})
            if existing["ids"]:
                col.delete(ids=existing["ids"])
        registry[name] = (col, {} if full else load_state(state_file), state_file)
    if not only or embedder_mod.read_marker(root) is None:
        embedder_mod.write_marker(root, emb)

    walk_errors: dict[str, int] = {}
    files = find_source_files(only, walk_errors)
    records, skipped, errors = [], 0, sum(walk_errors.values())
    epub_warned = False
    for fpath, key, collection in files:
        if collection not in registry:
            continue
        mtime = str(fpath.stat().st_mtime)
        if not full and registry[collection][1].get(key) == mtime:
            skipped += 1
            continue
        try:
            chunks, text = read_chunks(fpath, key, collection)
        except ImportError as exc:
            # Optional reader missing (epub). Skip without recording the file, so it is read once the library is installed.
            if not epub_warned:
                logger.warning("Skipping .epub files: %s", exc)
                epub_warned = True
            skipped += 1
            continue
        except Exception as exc:
            logger.error("Failed to read %s: %s", key, exc)
            errors += 1
            continue
        if chunks:
            records.append(FileRecord(fpath, key, collection, mtime, text[: config.CONTEXT_MAX_DOC_CHARS], chunks))
        else:
            # The file exists but now yields no chunks: drop its old ones and remember the file as seen.
            _delete_file(registry[collection][0], key)
            registry[collection][1][key] = mtime

    # Stale entries are removed per collection. A file that exists but could not be read still counts as
    # present (its old chunks stay until it reads again). A collection whose folders could not all be
    # listed is left alone, because a missing listing would look like deleted files.
    orphans = 0
    current: dict[str, set[str]] = {n: set() for n in names}
    for _p, key, collection in files:
        if collection in current:
            current[collection].add(key)
    for name, (col, state, state_file) in registry.items():
        if walk_errors.get(name):
            continue
        orphans += reconcile_orphans(col, state, current[name])
        save_state(state, state_file)

    context_calls = _run_context_pass(records) if context and records else 0
    started = time.time()
    total = 0
    for name in names:
        group = [r for r in records if r.collection == name]
        col, state, state_file = registry[name]
        if group:
            total += embed_records(group, col, emb, state, state_file)
    return {
        "files_indexed": len(records), "files_skipped": skipped, "chunks_added": total,
        "orphans_deleted": orphans, "context_calls": context_calls, "errors": errors,
        "seconds": round(time.time() - started, 1), "embedder": emb.name,
        "counts": {n: registry[n][0].count() for n in names},
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build or update the search index.")
    parser.add_argument("--full", action="store_true", help="Force full rebuild")
    parser.add_argument("--source", choices=list(config.BUILT_COLLECTION_NAMES), help="One collection only")
    parser.add_argument("--embedder", default=None, help="hash, local or auto")
    parser.add_argument("--context", action="store_true", help="Generate chunk context (needs a provider)")
    args = parser.parse_args(argv)
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    try:
        summary = build(args.source, args.full, args.embedder, args.context)
    except NotSetUp as exc:
        print(f"not set up: {exc}", file=sys.stderr)
        return 2
    except ImportError as exc:
        print(f"not set up: missing package ({exc})", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"stopped: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
