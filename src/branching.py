from .errors import PigError
from pathlib import Path
import json
from .repo_utils import (
    get_head_info,
    update_head,
)
from .commit_helpers import current_commit_hash
from .models import HeadInfo, BranchInfo
from .recreatedirectory import recreate_directory

def get_branch_heads_path(pig_root: Path) -> Path:
    return pig_root / ".pig" / "BRANCH_HEADS.json"

def get_branch_heads(pig_root: Path) -> BranchInfo:
    branch_heads_path = get_branch_heads_path(pig_root)
    if not branch_heads_path.exists():
        return {}
    return json.loads(branch_heads_path.read_text())

def update_branch_head(pig_root: Path, branch_name: str, new_commit_hash: str) -> None:
    branch_heads = get_branch_heads(pig_root)
    branch_heads[branch_name] = new_commit_hash
    branch_heads_path = get_branch_heads_path(pig_root)
    branch_heads_path.write_text(json.dumps(branch_heads, indent=4))

def get_current_branch(pig_root: Path) -> str | None:
    head_info = get_head_info(pig_root)
    if head_info.type == "branch":
        return head_info.value
    return None

def switch_branch(pig_root: Path, branch_name: str) -> None:
    branch_heads = get_branch_heads(pig_root)
    if branch_name not in branch_heads:
        raise PigError(f"branch '{branch_name}' does not exist")
    new_commit_hash = branch_heads[branch_name]
    recreate_directory(pig_root, new_commit_hash)
    update_head(pig_root, HeadInfo(type="branch", value=branch_name))

def create_branch(pig_root: Path, branch_name: str, start_commit: str | None = None) -> None:
    if start_commit is None:
        start_commit = current_commit_hash(pig_root)
    branch_heads = get_branch_heads(pig_root)
    if branch_name in branch_heads:
        raise PigError(f"branch '{branch_name}' already exists")
    update_branch_head(pig_root, branch_name, start_commit)

def delete_branch(pig_root: Path, branch_name: str) -> None:
    branch_heads = get_branch_heads(pig_root)
    if branch_name not in branch_heads:
        raise PigError(f"branch '{branch_name}' does not exist")
    current_branch = get_current_branch(pig_root)
    if current_branch == branch_name:
        raise PigError("Cannot delete the current checked out branch")
    branch_heads.pop(branch_name)
    branch_heads_path = get_branch_heads_path(pig_root)
    branch_heads_path.write_text(json.dumps(branch_heads, indent=4))