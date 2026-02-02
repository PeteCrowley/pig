import json
from pathlib import Path
import hashlib
import time
import random
from .errors import PigError
from .repo_utils import get_head_info
from .models import CommitInfo

def current_commit_hash(pig_root: Path) -> str:
    head_info = get_head_info(pig_root)
    if head_info.type == "commit":
        return head_info.value
    elif head_info.type == "branch":
        branch_heads_path = pig_root / ".pig" / "BRANCH_HEADS.json"
        if not branch_heads_path.exists():
            raise PigError("BRANCH_HEADS file does not exist")
        branch_heads = json.loads(branch_heads_path.read_text())
        if head_info.value not in branch_heads:
            raise PigError(f"branch '{head_info.value}' does not exist")
        return branch_heads[head_info.value]
    else:
        raise PigError("Invalid HEAD type")
    
def get_new_commit_hash() -> str:
    return hashlib.sha256(f"{time.time_ns()}-{random.random()}".encode()).hexdigest()

def get_commit_info(pig_root: Path, commit_hash: str) -> CommitInfo:
    commit_path = pig_root / ".pig" / "commits" / f"{commit_hash}.json"
    if not commit_path.exists():
        raise PigError(f"commit {commit_hash} does not exist")
    return CommitInfo(**json.loads(commit_path.read_text()))
    
def update_commit_info(pig_root: Path, commit_hash: str, info: CommitInfo):
    commit_path = pig_root / ".pig" / "commits" / f"{commit_hash}.json"
    commit_path.write_text(json.dumps(info.model_dump(), indent=4))

def commit_from_commit_or_branch(pig_root: Path, branch_name_or_commit_hash: str) -> str:
    branch_heads_path = pig_root / ".pig" / "BRANCH_HEADS.json"
    if branch_heads_path.exists():
        branch_heads = json.loads(branch_heads_path.read_text())
        if branch_name_or_commit_hash in branch_heads:
            return branch_heads[branch_name_or_commit_hash]
    if (pig_root / ".pig" / "commits" / f"{branch_name_or_commit_hash}.json").exists():
        return branch_name_or_commit_hash
    raise PigError(f"branch or commit '{branch_name_or_commit_hash}' does not exist")