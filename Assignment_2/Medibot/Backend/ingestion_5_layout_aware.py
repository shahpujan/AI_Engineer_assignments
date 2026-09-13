"""
MediBot - Layout/Table-Aware Ingestion

- Parse PDFs/Markdown with Docling
- Use HybridChunker for normal text
- Preserve table structure where possible
- Add assignment metadata + RBAC roles
- Store dense + sparse vectors in Qdrant
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore, RetrievalMode, FastEmbedSparse


# ============================================================
# 1. CONFIG
# ============================================================

DATA_ROOT = Path("mediassist_data")
QDRANT_PATH = "./qdrant_data_hybrid"
QDRANT_COLLECTION_NAME = "mediassist_docs"
EMBED_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MAX_TOKENS = 800

COLLECTION_ACCESS = {
    "general": ["doctor", "nurse", "billing_executive", "technician", "admin"],
    "clinical": ["doctor", "admin"],
    "nursing": ["nurse", "doctor", "admin"],
    "billing": ["billing_executive", "admin"],
    "equipment": ["technician", "admin"],
}


# ============================================================
# 2. EMBEDDINGS + CHUNKER
# ============================================================

hf_tokenizer = HuggingFaceTokenizer(
    tokenizer=AutoTokenizer.from_pretrained(EMBED_MODEL_ID),
    max_tokens=MAX_TOKENS,
)

chunker = HybridChunker(
    tokenizer=hf_tokenizer,
    merge_peers=True,
)

embedder = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL_ID
)

sparse_embedder = FastEmbedSparse(
    model_name="Qdrant/bm25",
    batch_size=32,
)


# ============================================================
# 3. HELPERS
# ============================================================

def get_collection_from_path(file_path: Path) -> str:
    relative = file_path.relative_to(DATA_ROOT)
    if len(relative.parts) < 2:
        raise ValueError(f"Could not determine collection for {file_path}")

    collection = relative.parts[0].lower()
    if collection not in COLLECTION_ACCESS:
        raise ValueError(f"Unsupported collection '{collection}' for {file_path}")

    return collection


def normalise_label(label: Any) -> str:
    if label is None:
        return ""
    return str(getattr(label, "value", label)).lower()


def get_headings(doc_chunk: Any) -> list[str]:
    headings = getattr(doc_chunk.meta, "headings", None) or []
    return [str(h).strip() for h in headings if str(h).strip()]


def detect_chunk_type(doc_chunk: Any) -> str:
    labels: list[str] = []
    doc_items = getattr(doc_chunk.meta, "doc_items", None) or []

    for item in doc_items:
        labels.append(normalise_label(getattr(item, "label", None)))

    joined = " ".join(labels)

    if "table" in joined:
        return "table"
    if "code" in joined:
        return "code"
    if "heading" in joined or "title" in joined or "section_header" in joined:
        return "heading"
    return "text"


def safe_section_title(headings: list[str]) -> str:
    return " > ".join(headings) if headings else "Unknown section"


def clean_text(text: str) -> str:
    if not text:
        return ""

    cleaned: list[str] = []
    previous_blank = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        blank = not line.strip()

        if blank and previous_blank:
            continue

        cleaned.append(line)
        previous_blank = blank

    return "\n".join(cleaned).strip()


def contextualize_chunk(doc_chunk: Any) -> str:
    try:
        return clean_text(chunker.contextualize(chunk=doc_chunk))
    except Exception:
        return clean_text(getattr(doc_chunk, "text", "") or "")


def table_to_layout_aware_text(doc_chunk: Any, fallback_text: str) -> str:
    """
    Prefer a structured table export when Docling exposes one.
    Markdown keeps rows/columns explicit and reduces broken relationships.

    This function uses safe fallbacks because Docling's table-item API can vary
    slightly across versions.
    """
    doc_items = getattr(doc_chunk.meta, "doc_items", None) or []
    table_parts: list[str] = []

    for item in doc_items:
        label = normalise_label(getattr(item, "label", None))
        if "table" not in label:
            continue

        # Some Docling versions expose export_to_markdown on the item.
        if hasattr(item, "export_to_markdown"):
            try:
                value = item.export_to_markdown()
                if value and str(value).strip():
                    table_parts.append(str(value).strip())
                    continue
            except Exception:
                pass

        # Others expose it on item.data.
        data = getattr(item, "data", None)
        if data is not None and hasattr(data, "export_to_markdown"):
            try:
                value = data.export_to_markdown()
                if value and str(value).strip():
                    table_parts.append(str(value).strip())
                    continue
            except Exception:
                pass

        # Last table-specific fallback.
        item_text = getattr(item, "text", None)
        if item_text and str(item_text).strip():
            table_parts.append(str(item_text).strip())

    if not table_parts:
        return fallback_text

    headings = get_headings(doc_chunk)
    breadcrumb = " > ".join(headings)
    table_text = "\n\n".join(table_parts)

    if breadcrumb:
        return f"{breadcrumb}\n\n{table_text}".strip()

    return table_text.strip()


def make_document(file_path: Path, collection: str, doc_chunk: Any) -> Document | None:
    headings = get_headings(doc_chunk)
    chunk_type = detect_chunk_type(doc_chunk)

    contextualized = contextualize_chunk(doc_chunk)
    if not contextualized:
        return None

    if chunk_type == "table":
        page_content = table_to_layout_aware_text(doc_chunk, contextualized)
    else:
        page_content = contextualized

    if not page_content.strip():
        return None

    metadata = {
        "source_document": file_path.name,
        "collection": collection,
        "access_roles": COLLECTION_ACCESS[collection],
        "section_title": safe_section_title(headings),
        "chunk_type": chunk_type,
    }

    return Document(
        page_content=page_content.strip(),
        metadata=metadata,
    )


# ============================================================
# 4. PROCESS FILES
# ============================================================

def process_file(converter: DocumentConverter, file_path: Path) -> list[Document]:
    collection = get_collection_from_path(file_path)

    print("\n====================================================")
    print(f"Processing: {file_path}")
    print(f"Collection: {collection}")
    print("====================================================")

    result = converter.convert(str(file_path))
    dl_doc = result.document

    doc_chunks = list(chunker.chunk(dl_doc=dl_doc))
    print(f"Hybrid chunks before conversion: {len(doc_chunks)}")

    documents: list[Document] = []

    for doc_chunk in doc_chunks:
        document = make_document(file_path, collection, doc_chunk)
        if document is not None:
            documents.append(document)

    print(f"Final LangChain documents: {len(documents)}")
    return documents


def discover_files() -> list[Path]:
    supported = {".pdf", ".md", ".markdown"}
    files: list[Path] = []

    for collection in COLLECTION_ACCESS:
        folder = DATA_ROOT / collection

        if not folder.exists():
            print(f"Warning: folder does not exist: {folder}")
            continue

        for file_path in folder.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in supported:
                files.append(file_path)

    return sorted(files)


# ============================================================
# 5. SANITY CHECKS
# ============================================================

def print_matching_chunks(documents: list[Document], phrase: str) -> None:
    matches = [
        doc for doc in documents
        if phrase.lower() in doc.page_content.lower()
    ]

    print(f"\n========== MATCHES FOR '{phrase}' ({len(matches)}) ==========")

    for i, doc in enumerate(matches, start=1):
        print(f"\n----- MATCH {i} -----")
        print("Source:", doc.metadata.get("source_document"))
        print("Section:", doc.metadata.get("section_title"))
        print("Collection:", doc.metadata.get("collection"))
        print("Type:", doc.metadata.get("chunk_type"))
        print(doc.page_content[:2500])


# ============================================================
# 6. QDRANT INGESTION
# ============================================================

def ingest_documents(documents: list[Document]) -> None:
    if not documents:
        raise RuntimeError("No documents were produced. Nothing to ingest.")

    print(f"\nStoring {len(documents)} documents in Qdrant...")

    QdrantVectorStore.from_documents(
        documents=documents,
        embedding=embedder,
        sparse_embedding=sparse_embedder,
        path=QDRANT_PATH,
        collection_name=QDRANT_COLLECTION_NAME,
        retrieval_mode=RetrievalMode.HYBRID,
    )

    print("\nIngestion complete.")
    print("Collection:", QDRANT_COLLECTION_NAME)
    print("Qdrant path:", QDRANT_PATH)


# ============================================================
# 7. MAIN
# ============================================================

def main() -> None:
    converter = DocumentConverter()
    files = discover_files()

    print(f"Found {len(files)} source files.")

    if not files:
        raise RuntimeError(f"No PDF/Markdown files found under {DATA_ROOT}")

    all_documents: list[Document] = []

    for file_path in files:
        all_documents.extend(process_file(converter, file_path))

    print(f"\nTotal documents/chunks prepared: {len(all_documents)}")

    # Current billing-table diagnostic.
    print_matching_chunks(all_documents, "E11.9")
    print_matching_chunks(all_documents, "Type 2 diabetes w/o complications")

    ingest_documents(all_documents)


if __name__ == "__main__":
    main()
