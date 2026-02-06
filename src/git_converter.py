from pathlib import Path
import subprocess
from .file_helpers import get_file_hash, write_file_info
from .commit_helpers import update_commit_info, get_commit_info, get_new_commit_hash
from .models import CommitInfo, FileInfo
from .branching import update_branch_head

def recursive_read_all_files_in_directory(directory: Path, files: dict[str, str], prefix: str = "") -> None:
    for item in directory.iterdir():
        if item.is_dir():
            recursive_read_all_files_in_directory(item, files, prefix + item.name + "/")
        else:
            files[prefix + item.name] = item.read_text().strip()
    
# Works for smaller repos (i.e < 6,700) when it doesn't start using packed refs
def get_all_branch_heads(git_root: Path) -> dict[str, str]:
    branch_heads_path = git_root / ".git" / "refs" / "heads"
    if not branch_heads_path.exists():
        return {}
    branch_heads: dict[str, str] = {}
    recursive_read_all_files_in_directory(branch_heads_path, branch_heads)
    return branch_heads

def get_all_commits_for_branch(git_root: Path, branch_name: str) -> list[str]:
    result = subprocess.run(["git", "rev-list", branch_name], cwd=git_root, capture_output=True, text=True)
    print(branch_name)
    if result.returncode != 0:
        raise Exception(f"Git command failed: {result.stderr}")
    commit_hashes = result.stdout.strip().split('\n')
    return commit_hashes

def add_git_commit_to_pig_repo(git_root: Path, pig_root: Path, commit_hash: str, parent_pig_hash: str) -> str:
    result = subprocess.run(["git", "show", "--pretty=format:%an%n%at%n%s%n", "--name-status", "--no-renames", commit_hash], cwd=git_root, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Git command failed: {result.stderr}")
    output_lines = result.stdout.strip().split('\n')
    author_line = output_lines[0]
    timestamp = int(output_lines[1])
    commit_message = output_lines[2]
    file_lines = output_lines[4:]   # skip the empty line after commit message
    file_info_list = [f for f in (line.strip().split("\t") for line in file_lines)]

    commit_files: dict[str, FileInfo] = {}
    deleted_files = []

    tmp_file = pig_root / ".pig" / "tmp-file"
    for status, file_path in file_info_list:
        if status == "D":
            deleted_files.append(file_path)
            continue
        show_file_result = subprocess.run(["git", "show", f"{commit_hash}:{file_path}"], cwd=git_root, stdout=tmp_file.open('wb'))
        if show_file_result.returncode != 0:
            raise Exception(f"Git command failed: {show_file_result.stderr}")

        file_hash = get_file_hash(tmp_file)
        commit_files[file_path] = FileInfo(hash=file_hash, lastEdited=timestamp)
        write_file_info(pig_root, file_hash, tmp_file)

    if tmp_file.exists():
        tmp_file.unlink()

    parent_commit_files = get_commit_info(pig_root, parent_pig_hash).files
    for file_path, file_info in commit_files.items():
        parent_commit_files[file_path] = file_info
    for file_path in deleted_files:
        if file_path in parent_commit_files:
            del parent_commit_files[file_path]
    
    commit_info = CommitInfo(
        commitMessage=commit_message,
        author=author_line,
        timestamp=timestamp,
        parentCommit=parent_pig_hash,
        files=parent_commit_files
    )
    new_commit_hash = get_new_commit_hash()
    update_commit_info(pig_root, new_commit_hash, commit_info)
    return new_commit_hash
    

def create_pig_from_git_repo(git_root: Path, pig_root: Path) -> None:
    all_branches = get_all_branch_heads(git_root)
    commits_recreated: dict[str, str] = {}
    for branch_name in all_branches:
        parent_pig_commit_hash = "EMPTY-COMMIT"
        commit_hashes = get_all_commits_for_branch(git_root, branch_name)
        if not commit_hashes:
            continue
        for commit_hash in reversed(commit_hashes):
            if commit_hash in commits_recreated:
                parent_pig_commit_hash = commits_recreated[commit_hash]
                continue
            pig_commit_hash = add_git_commit_to_pig_repo(git_root, pig_root, commit_hash, parent_pig_commit_hash)
            commits_recreated[commit_hash] = pig_commit_hash
            parent_pig_commit_hash = pig_commit_hash
        # Update branch head
        update_branch_head(pig_root, branch_name, parent_pig_commit_hash)
        
        
        
    

