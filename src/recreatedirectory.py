import gzip
from pathlib import Path
import shutil
from .commit_helpers import get_commit_info


def clear_directory(path: Path, ignoreFiles: set | None = None) -> None:
    for item in path.iterdir():
        if ignoreFiles and item.name in ignoreFiles:
            continue
        if item.is_dir():
            clear_directory(item)
            item.rmdir()
        else:
            item.unlink()

def recreate_directory(pig_root: Path, commit_hash: str) -> None:
    commit_info = get_commit_info(pig_root, commit_hash)
    tmp_dir = pig_root / ".pig" / "tmp-recreate"
    if tmp_dir.exists():
        clear_directory(tmp_dir)
    for filepath, fileinfo in commit_info.files.items():
        dest_path: Path  = tmp_dir / filepath
        if not dest_path.parent.exists():
            dest_path.parent.mkdir(parents=True)
        compressed_file_path: Path  = pig_root / ".pig" / "compressed-files" / fileinfo.hash
        # print(f"Recreating file {filepath}...")
        try:
            with gzip.open(compressed_file_path, "rb") as f_in:
                with open(dest_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        except Exception as e:
            print(f"Error recreating file {filepath}: {e}")
    clear_directory(pig_root, ignoreFiles={".pig"})
    if not tmp_dir.exists():
        return
    for item in tmp_dir.iterdir():
        shutil.move(str(item), str(pig_root))
    clear_directory(tmp_dir)
    tmp_dir.rmdir()
    
        
        
