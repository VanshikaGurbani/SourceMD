"""Download, chunk, embed, and push guideline PDFs into ChromaDB.

Run as a one-shot:
    python -m backend.ingestion.ingest

Idempotent: existing chunks with the same hash id are overwritten, so
re-running the script after editing sources.py does not create duplicates.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
from pypdf import PdfReader

from backend.agents.chroma_client import get_guidelines_collection
from backend.agents.embeddings import embed_texts
from backend.ingestion.sources import SOURCES, GuidelineSource

CACHE_DIR = Path(__file__).parent / "cache"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}


def _download_pdf(source: GuidelineSource) -> Path:
    """Download the given PDF into the cache directory if not already present.

    Uses browser-like headers to avoid servers that block plain programmatic
    requests (e.g. WHO iris). Validates that the response is actually a PDF
    by checking for the %%PDF magic bytes. Raises RuntimeError when the server
    returns HTML instead of a PDF (usually a redirect or paywall page).
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = CACHE_DIR / f"{source['name']}.pdf"
    if target.exists() and target.stat().st_size > 1024:
        # Quick sanity check — existing file must start with %PDF
        with target.open("rb") as fh:
            if fh.read(4) == b"%PDF":
                return target
        # File is corrupt/HTML — delete and re-download.
        target.unlink()

    if source["url"] == "local":
        raise RuntimeError(
            f"No cached file found for '{source['name']}' at {target}. "
            "Place the PDF there manually and re-run ingestion."
        )

    print(f"  downloading {source['url']}")
    with httpx.Client(follow_redirects=True, timeout=90.0, headers=_BROWSER_HEADERS) as client:
        response = client.get(source["url"])
        response.raise_for_status()
        content = response.content
        if not content[:4].startswith(b"%PDF"):
            raise RuntimeError(
                f"Server returned non-PDF content (got {content[:20]!r}). "
                "Download this PDF manually and place it at {target}."
            )
        target.write_bytes(content)
    return target


def _extract_pages(path: Path) -> list[tuple[int, str]]:
    """Return a list of ``(page_number, page_text)`` tuples for a PDF.

    Page numbers are 1-indexed to match how clinicians cite documents.
    Blank pages are skipped.
    """
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            text = ""
        text = text.strip()
        if text:
            pages.append((i, text))
    return pages


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split ``text`` into overlapping character windows.

    Character-level chunking is deliberate: it is deterministic, language
    agnostic, and keeps the ingestion pipeline free of a tokenizer
    dependency. Guideline PDFs have consistent formatting, so this works
    well for retrieval at top-3.
    """
    if size <= 0:
        raise ValueError("chunk size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must satisfy 0 <= overlap < size")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap
    return chunks


def _chunk_id(doc: str, page: int, chunk_index: int, text: str) -> str:
    """Return a deterministic SHA-1 based id for a chunk."""
    payload = f"{doc}|{page}|{chunk_index}|{text[:64]}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def ingest_source(source: GuidelineSource) -> int:
    """Ingest a single guideline PDF into ChromaDB.

    Returns the number of chunks uploaded.
    """
    print(f"[{source['name']}]")
    path = _download_pdf(source)
    pages = _extract_pages(path)
    print(f"  parsed {len(pages)} non-empty pages")

    collection = get_guidelines_collection()

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for page_number, page_text in pages:
        for chunk_index, chunk in enumerate(_chunk_text(page_text)):
            ids.append(_chunk_id(source["name"], page_number, chunk_index, chunk))
            documents.append(chunk)
            metadatas.append(
                {
                    "doc": source["name"],
                    "page": page_number,
                    "chunk": chunk_index,
                    "tag": source["tag"],
                    "source_url": source["url"],       # PDF download link
                    "web_url": source["web_url"],      # canonical guideline webpage
                }
            )

    if not documents:
        print("  no chunks produced, skipping")
        return 0

    # Embed and upload in batches to avoid huge requests.
    batch_size = 64
    total = 0
    for i in range(0, len(documents), batch_size):
        batch_ids = ids[i : i + batch_size]
        batch_docs = documents[i : i + batch_size]
        batch_meta = metadatas[i : i + batch_size]
        batch_vecs = embed_texts(batch_docs)
        collection.upsert(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_meta,
            embeddings=batch_vecs,
        )
        total += len(batch_ids)
    print(f"  upserted {total} chunks")
    return total


def main() -> None:
    """Ingest every guideline in ``SOURCES`` and print a summary."""
    grand_total = 0
    for src in SOURCES:
        try:
            grand_total += ingest_source(src)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}")
    print(f"\nDone. Total chunks upserted: {grand_total}")


if __name__ == "__main__":
    main()
