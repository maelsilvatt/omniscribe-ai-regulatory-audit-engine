import argparse
import asyncio
import os
import sys

import fitz  # PyMuPDF

from src.rag.pipeline import RegulatoryIngestionPipeline


def _extract_text_from_pdf(file_path: str) -> str:
    """
    Synchronous text extraction using PyMuPDF.
    Design Decision: This must be executed in a background thread because PyMuPDF
    is a CPU-bound C-extension that will block the async event loop if run directly.
    """
    extracted_pages = []
    with fitz.open(file_path) as doc:
        for page in doc:
            extracted_pages.append(page.get_text())

    # Using join() is structurally faster and consumes less memory than string concatenation (+=)
    return "\n".join(extracted_pages)


def _parse_arguments() -> argparse.Namespace:
    """Encapsulates CLI argument parsing logic."""
    parser = argparse.ArgumentParser(
        description="OmniScribe RAG Ingestion CLI - Agnostically feeds the ChromaDB vector database."
    )
    parser.add_argument(
        "--file", "-f", required=True, help="Path to the regulatory PDF file."
    )
    parser.add_argument(
        "--framework",
        "-w",
        required=True,
        help="Framework name/tag (e.g., GDPR, HIPAA, CCPA).",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_arguments()
    framework_tag = args.framework.upper().strip()

    if not os.path.exists(args.file):
        print(f"❌ Error: The file '{args.file}' was not found.")
        sys.exit(1)

    print(f"📥 [RAG CLI] Opening and extracting document: '{args.file}'...")

    try:
        # Offload the heavy extraction process to a background thread to preserve event loop responsiveness
        extracted_text = await asyncio.to_thread(_extract_text_from_pdf, args.file)

        if not extracted_text.strip():
            print(
                "❌ Error: The provided PDF is empty or lacks a text layer (requires OCR)."
            )
            sys.exit(1)

    except Exception as e:
        print(f"❌ Critical failure while reading the PDF: {str(e)}")
        sys.exit(1)

    print(f"✂️  Slicing and generating embeddings for framework: '{framework_tag}'...")

    try:
        # Initialize and run the RAG pipeline
        pipeline = RegulatoryIngestionPipeline()
        result = await pipeline.run_ingestion_async(
            raw_text=extracted_text, framework_name=framework_tag
        )

        print("\n🏆 [INGESTION COMPLETED SUCCESSFULLY]")
        print(f"📂 Processed file: {args.file}")
        print(f"🏷️  ChromaDB Tag: {result.get('framework', framework_tag)}")
        print(f"🧩 Chunks generated and saved: {result.get('chunks_processed', 0)}")

    except Exception as e:
        print(f"❌ Critical failure during vector ingestion: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
