
from pathlib import Path
import gzip
import shutil
import hashlib
from .errors import PigError

def write_file_info(pig_root: Path, file_hash: str, filepath: Path):
    compressed_dir = pig_root / ".pig" / "compressed-files"
    dest_path = compressed_dir / file_hash
    if dest_path.exists():
        return
    with open(filepath, "rb") as f_in:
        with gzip.open(dest_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

def read_compressed_file(pig_root: Path, file_hash: str) -> list[str]:
    compressed_file_path = pig_root / ".pig" / "compressed-files" / file_hash
    if not compressed_file_path.exists():
        raise PigError(f"compressed file {file_hash} does not exist")
    with gzip.open(compressed_file_path, "rt") as f:
        return f.readlines()
    
def get_file_hash(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()