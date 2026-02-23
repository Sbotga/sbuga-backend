import hashlib
from typing import Union, IO
from io import BytesIO
from pathlib import Path
import os


def _calculate_hash(data: Union[os.PathLike, IO[bytes], bytes], algorithm: str) -> str:
    if algorithm not in ("sha1", "sha256"):
        raise ValueError("Unsupported hash algorithm.")

    hash_obj = hashlib.new(algorithm)

    if isinstance(data, (str, Path, os.PathLike)):
        with open(data, "rb") as file:
            while chunk := file.read(8192):
                hash_obj.update(chunk)

    elif isinstance(data, BytesIO):
        data.seek(0)
        while chunk := data.read(8192):
            hash_obj.update(chunk)
        data.seek(0)

    elif isinstance(data, IO):
        while chunk := data.read(8192):
            hash_obj.update(chunk)

    elif isinstance(data, bytes):
        hash_obj.update(data)

    else:
        raise ValueError(
            "Input must be a file path (str/Path), a file-like object (IO[bytes]), or raw bytes."
        )

    return hash_obj.hexdigest()


def calculate_sha1(data: Union[os.PathLike, IO[bytes], bytes]) -> str:
    return _calculate_hash(data, "sha1")


def calculate_sha256(data: Union[os.PathLike, IO[bytes], bytes]) -> str:
    return _calculate_hash(data, "sha256")
