
import json
import os
from pathlib import Path

import faiss

from lexisync.config import INDEX_DIR
from lexisync.schemas.document import Chunk
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class IndexStore:
    """
    Persist and restore FAISS indexes and their corresponding chunks.

    FAISS stores vector representations.
    JSON stores the metadata required to map vectors back to chunks.
    """

    def __init__(
        self,
        index_dir: str | Path = INDEX_DIR,
        index_name: str = "legal_documents",
    ) -> None:

        if not index_name or Path(index_name).name != index_name:
            raise ValueError("Invalid index name.")

        self.index_dir = Path(index_dir)
        self.index_name = index_name

        self.index_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.index_path = (
            self.index_dir / f"{self.index_name}.faiss"
        )

        self.chunks_path = (
            self.index_dir / f"{self.index_name}_chunks.json"
        )

    def save(
        self,
        index: faiss.Index,
        chunks: list[Chunk],
    ) -> None:
        """
        Save a FAISS index and its corresponding chunks.

        Both files are written to temporary paths first and then
        replaced atomically to avoid leaving partially written files.
        """

        if index is None:
            raise ValueError("FAISS index cannot be None.")

        if not chunks:
            raise ValueError("Cannot save an empty chunk list.")

        if index.ntotal != len(chunks):
            raise ValueError(
                "FAISS vector count does not match chunk count."
            )

        chunk_ids = [
            chunk.chunk_id
            for chunk in chunks
        ]

        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("Chunk IDs must be unique.")

        index_temp_path = self.index_path.with_suffix(
            ".faiss.tmp"
        )

        chunks_temp_path = self.chunks_path.with_suffix(
            ".json.tmp"
        )

        try:
            # Save FAISS index.
            faiss.write_index(
                index,
                str(index_temp_path),
            )

            # Serialize chunk metadata.
            chunk_data = [
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "text": chunk.text,
                    "page_numbers": chunk.page_numbers,
                    "section": chunk.section,
                    "subsection": chunk.subsection,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "metadata": chunk.metadata,
                }
                for chunk in chunks
            ]

            with chunks_temp_path.open(
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    chunk_data,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            # Replace previous files only after successful writes.
            os.replace(
                index_temp_path,
                self.index_path,
            )

            os.replace(
                chunks_temp_path,
                self.chunks_path,
            )

            logger.info(
                "Saved FAISS index and %d chunks to %s.",
                len(chunks),
                self.index_dir,
            )

        finally:
            # Remove leftover temporary files if an error occurs.
            index_temp_path.unlink(missing_ok=True)
            chunks_temp_path.unlink(missing_ok=True)

    def load(self) -> tuple[faiss.Index, list[Chunk]]:
        """
        Load a FAISS index and its corresponding chunks.

        Returns:
            Tuple containing:
            - FAISS index
            - List of Chunk objects
        """

        if not self.index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found: {self.index_path}"
            )

        if not self.chunks_path.exists():
            raise FileNotFoundError(
                f"Chunk metadata not found: {self.chunks_path}"
            )

        index = faiss.read_index(
            str(self.index_path)
        )

        with self.chunks_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            chunk_data = json.load(file)

        if not isinstance(chunk_data, list):
            raise ValueError(
                "Chunk metadata must contain a JSON list."
            )

        chunks = [
            Chunk(**item)
            for item in chunk_data
        ]

        if index.ntotal != len(chunks):
            raise ValueError(
                "Loaded FAISS vector count does not match "
                "loaded chunk count."
            )

        chunk_ids = [
            chunk.chunk_id
            for chunk in chunks
        ]

        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError(
                "Loaded chunk metadata contains duplicate IDs."
            )

        logger.info(
            "Loaded FAISS index with %d vectors and %d chunks.",
            index.ntotal,
            len(chunks),
        )

        return index, chunks
