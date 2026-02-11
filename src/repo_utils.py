from pathlib import Path
from .errors import PigError
from .models import HeadInfo

def find_pig_root_dir(start: Path = Path.cwd()) -> Path | None:
    for directory in [start] + list(start.parents):
        if (directory / ".pig").is_dir():
            return directory
        if directory == Path.home():    # won't look past home directory
            return None
    return None

def get_head_path(pig_root: Path) -> Path:
    return pig_root / ".pig" / "HEAD"

def get_head_info(pig_root: Path) -> HeadInfo:
    head_path = get_head_path(pig_root)
    if not head_path.exists():
        raise PigError("HEAD file does not exist")
    content = head_path.read_text().strip()
    if content.startswith("branch: "):
        return HeadInfo(type="branch", value=content[8:])
    elif content.startswith("commit: "):
        return HeadInfo(type="commit", value=content[8:])
    else:
        raise PigError("Invalid HEAD file format")

def update_head(pig_root: Path, new_head_info: HeadInfo) -> None:
    head_path = get_head_path(pig_root)
    head_path.write_text(new_head_info.type + ": " + new_head_info.value)
