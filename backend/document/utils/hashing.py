"""Hash utilities for document processing.

Provides memory-efficient streaming SHA-256 calculation for file streams.
"""

import hashlib
from typing import BinaryIO


def calculate_sha256(stream: BinaryIO, chunk_size: int = 65536) -> str:
    """Calculate SHA-256 hexadecimal checksum of a binary stream without loading entirely into memory.

    Resets the stream seek position to 0 upon completion.
    """
    hasher = hashlib.sha256()
    current_pos = stream.tell()
    stream.seek(0)

    while chunk := stream.read(chunk_size):
        hasher.update(chunk)

    stream.seek(current_pos)
    return hasher.hexdigest()
