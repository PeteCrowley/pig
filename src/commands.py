from .errors import PigError
from pathlib import Path
from typing import Callable
import hashlib
import time
from .repo_utils import (
    find_pig_root_dir,
    update_head,
)
from .file_helpers import (
    get_file_hash,
    write_file_info,
)
from .staging_helpers import (
    get_staging_info,
    update_staging_info,
)
from .commit_helpers import (
    current_commit_hash,
    get_commit_info,
    get_new_commit_hash,
    update_commit_info,
    commit_from_commit_or_branch,
)
from .branching import (
    switch_branch,
    create_branch,
    get_current_branch,
    update_branch_head,
    get_branch_heads,
    delete_branch,
)
from .merging import (
    merge_commits,
)
from .models import CommitInfo, FileInfo, HeadInfo

def map_command(command: str) -> Callable:
    commandsMap = {
        "init": init,
        "add": add,
        "status": status,
        "commit": commit,
        "checkout": checkout,
        "switch": switch,
        "merge": merge,
        "log": log,
        "branch": branch,
    }
    if command not in commandsMap:
        raise PigError(f"Unknown command: {command}")
    return commandsMap[command]

def init(args):
    if find_pig_root_dir() is not None:
        raise PigError("already in a pig repository")
    pig_dir = Path.cwd() / ".pig"
    empty_commit_info = CommitInfo(
        commitMessage = "Initial empty commit",
        author = "Pete Crowley",
        timestamp = int(time.time()),
        parentCommit = None,
        files = {}
    )
    try:
        pig_dir.mkdir()
        (pig_dir / "commits").mkdir()
        update_commit_info(Path.cwd(), "EMPTY-COMMIT", empty_commit_info)
        (pig_dir / "compressed-files").mkdir()
        update_staging_info(Path.cwd(), {})
        update_head(Path.cwd(), HeadInfo(type="branch", value="main"))
        update_branch_head(Path.cwd(), "main", "EMPTY-COMMIT")
    except Exception as e:
        raise PigError(f"failed to create .pig directory: {e}")
    print("Initialized empty pig repository in " + str(pig_dir))


def calculate_sha256(filepath: Path) -> str:
    sha256 = hashlib.sha256()
    with filepath.open("rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def add(args):
    filepattern = args.filepattern
    pig_root = find_pig_root_dir()
    if pig_root is None:
        raise PigError("not in a pig repository")
    
    any_matches = False
    staging_info = get_staging_info(pig_root)
    for path in Path.cwd().rglob(filepattern):
        if not path.is_file():
            continue
        any_matches = True

        relative_path = str(path.relative_to(pig_root))
        new_hash = get_file_hash(path)
        staging_info[str(relative_path)] = FileInfo(
            hash=new_hash,
            lastEdited=int(time.time())
        )
        print(f"Added {relative_path} to staging.")

    if not any_matches:
        print("No files matched the given pattern.")
        return
    
    update_staging_info(pig_root, staging_info)


def status(args):
    pig_root = find_pig_root_dir()
    if pig_root is None:
        raise PigError("not in a pig repository")
    staging_info = get_staging_info(pig_root)
    current_branch = get_current_branch(pig_root)
    most_recent_commit = current_commit_hash(pig_root)
    location_info = f"on branch '{current_branch}'" if current_branch else f"at commit {most_recent_commit}"
    print(f"Repository status: {location_info}")
    if not staging_info:
        print("No files staged.")
        return
    print("Staged files:")
    for filepath in staging_info.keys():
        print(f" - {filepath}")

def commit_file(pig_root: Path, prev_commit_info: CommitInfo, filepath: Path):
    if not filepath.is_file():
        raise PigError(f"tried to commit file {filepath} does not exist")
    file_hash = get_file_hash(filepath)
    str_path = filepath.as_posix()
    if str_path in prev_commit_info.files and prev_commit_info.files[str_path].hash == file_hash:
        return False    # no changes actually made to this file
    prev_commit_info.files[str_path] = FileInfo(
        hash = file_hash,
        lastEdited = int(time.time())
    )
        
    write_file_info(pig_root, file_hash, filepath)
    return True
    

def commit(args):
    message = args.message
    pig_root = find_pig_root_dir()
    if pig_root is None:
        raise PigError("not in a pig repository")
    
    staging_info = get_staging_info(pig_root)

    if not staging_info:
        raise PigError("no files staged for commit")

    current_commit_info = get_commit_info(pig_root, current_commit_hash(pig_root))
    any_changes = False
    for filepath, _ in staging_info.items():
        if commit_file(pig_root, current_commit_info, Path(filepath)):
            any_changes = True
    if not any_changes:
        raise PigError("no changes to commit")
    
    new_commit_hash = get_new_commit_hash()
    current_commit_info.commitMessage = message
    current_commit_info.timestamp = int(time.time())
    current_commit_info.author = "Pete Crowley"  # placeholder for now
    current_commit_info.parentCommit = current_commit_hash(pig_root)
    update_commit_info(pig_root, new_commit_hash, current_commit_info)
    current_branch = get_current_branch(pig_root)
    if current_branch:
        update_branch_head(pig_root, current_branch, new_commit_hash)
    else:
        update_head(pig_root, HeadInfo(type="commit", value=new_commit_hash))
    update_staging_info(pig_root, {})   # clear staging area
    print(f"Committed changes as commit {new_commit_hash}")
    

def checkout(args):
    pig_root = find_pig_root_dir()
    if pig_root is None:
        raise PigError("not in a pig repository")
    staging_info = get_staging_info(pig_root)
    if staging_info:
        raise PigError("cannot switch branches with staged changes; please commit or unstage them first")
    # TODO: let name be either branch name or commit hash
    branch_name = args.name
    if args.create:
        start_point = commit_from_commit_or_branch(pig_root, args.start_point) if args.start_point else current_commit_hash(pig_root)
        create_branch(pig_root, branch_name, start_point)
    switch_branch(pig_root, branch_name)

    
def switch(args):
    pig_root = find_pig_root_dir()
    if pig_root is None:
        raise PigError("not in a pig repository")
    staging_info = get_staging_info(pig_root)
    if staging_info:
        raise PigError("cannot switch branches with staged changes; please commit or unstage them first")
    branch_name = args.name
    switch_branch(pig_root, branch_name)

def merge(args):
    pig_root = find_pig_root_dir()
    if pig_root is None:
        raise PigError("not in a pig repository")
    branch_name = args.name
    target_commit_hash = get_branch_heads(pig_root).get(branch_name)
    if target_commit_hash is None:
        raise PigError(f"branch '{branch_name}' does not exist")
    merge_commits(pig_root, target_commit_hash)
    print(f"Succesfully merged branch '{branch_name}' into current branch.")

def log(args):
    pig_root = find_pig_root_dir()
    if pig_root is None:
        raise PigError("not in a pig repository")
    # recursively print commit history
    commit_hash = current_commit_hash(pig_root)
    while commit_hash:
        commit_info = get_commit_info(pig_root, commit_hash)
        print(f"Commit: {commit_hash}")
        print(f"Author: {commit_info.author}")
        print(f"Date: {time.ctime(commit_info.timestamp)}")
        print(f"\n    {commit_info.commitMessage}\n")
        commit_hash = commit_info.parentCommit

def branch(args):
    pig_root = find_pig_root_dir()
    if pig_root is None:
        raise PigError("not in a pig repository")
    if args.delete:
        branch_to_delete = args.delete
        branch_heads = get_branch_heads(pig_root)
        if branch_to_delete not in branch_heads:
            raise PigError(f"branch '{branch_to_delete}' does not exist")
        delete_branch(pig_root, branch_to_delete)
    elif args.create:
        branch_to_create = args.create
        create_branch(pig_root, branch_to_create)
    else:
        branch_heads = get_branch_heads(pig_root)
        current_branch = get_current_branch(pig_root)
        for branch_name in branch_heads.keys():
            prefix = "*" if branch_name == current_branch else " "
            print(f"{prefix} {branch_name}")

        
    