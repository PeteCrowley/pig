from pathlib import Path
import json
from .models import StagingInfo, FileInfo

def get_staging_path(pig_root: Path) -> Path:
    return pig_root / ".pig" / "staging.json"

def get_staging_info(pig_root: Path) -> StagingInfo:
    staging_path = get_staging_path(pig_root)
    if not staging_path.exists():
        return {}
    data = json.loads(staging_path.read_text())
    return {k: FileInfo(**v) for k, v in data.items()}

def update_staging_info(pig_root: Path, info: StagingInfo):
    staging_path = get_staging_path(pig_root)
    info_dict = {k: v.model_dump() if hasattr(v, 'model_dump') else v for k, v in info.items()}
    staging_path.write_text(json.dumps(info_dict, indent=4))