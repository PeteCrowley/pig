from pathlib import Path
import subprocess
from typing import Optional
from .file_helpers import get_file_hash_from_content, write_file_info_from_content
from .commit_helpers import update_commit_info, get_commit_info, get_new_commit_hash
from .models import CommitInfo, FileInfo
from .branching import update_branch_head


class CatFileBatch:
    def __init__(self, git_root: Path) -> None:
        self._proc = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=git_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

    def __enter__(self) -> "CatFileBatch":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._proc.stdin:
            self._proc.stdin.close()
        if self._proc.stdout:
            self._proc.stdout.close()
        self._proc.wait()

    def get_blob(self, object_spec: str) -> tuple[Optional[bytes], Optional[str]]:
        if not self._proc.stdin or not self._proc.stdout:
            raise RuntimeError("cat-file batch process not initialized")
        self._proc.stdin.write(f"{object_spec}\n".encode())
        self._proc.stdin.flush()

        header = self._proc.stdout.readline()
        if not header:
            raise RuntimeError("cat-file batch process terminated unexpectedly")
        header = header.rstrip(b"\n")
        if header == b"missing":
            return None, None

        parts = header.split(b" ")
        if len(parts) < 3:
            return None, None

        obj_type = parts[1].decode("utf-8", "replace")
        size = int(parts[2])
        content = self._proc.stdout.read(size)
        self._proc.stdout.read(1)  # trailing newline

        if obj_type != "blob":
            return None, obj_type
        return content, obj_type

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
    result = subprocess.run(["git", "rev-list", "--topo-order", branch_name], cwd=git_root, capture_output=True, text=True)
    print(branch_name)
    if result.returncode != 0:
        raise Exception(f"Git command failed: {result.stderr}")
    commit_hashes = result.stdout.strip().split('\n')
    return commit_hashes

def is_valid_utf8(text: str) -> bool:
    try:
        text.encode('utf-8')
        return True
    except UnicodeEncodeError:
        return False

def decode_git_quoted_path(path: str) -> str:
    if not (path.startswith('"') and path.endswith('"')):
        return path
    inner = path[1:-1]
    result = bytearray()
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch != "\\":
            result.extend(ch.encode("utf-8", "surrogateescape"))
            i += 1
            continue
        i += 1
        if i >= len(inner):
            result.extend(b"\\")
            break
        nxt = inner[i]
        if nxt in "01234567":
            j = i
            while j < len(inner) and j - i < 3 and inner[j] in "01234567":
                j += 1
            result.append(int(inner[i:j], 8))
            i = j
            continue
        escapes = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r"}
        mapped = escapes.get(nxt, nxt)
        result.extend(mapped.encode("utf-8", "surrogateescape"))
        i += 1
    return result.decode("utf-8", "surrogateescape")

def convert_file_to_pig(
    git_root: Path,
    git_commit_hash: str,
    pig_root: Path,
    file_path: str,
    cat_file_batch: CatFileBatch,
) -> str | None:
    # returns file hash
    if not is_valid_utf8(file_path):
        print(f"Warning: Skipping file with non-UTF8 path: {file_path}")
        return None

    content, obj_type = cat_file_batch.get_blob(f"{git_commit_hash}:{file_path}")
    if content is None:
        if obj_type and obj_type != "blob":
            print(f"Warning: Skipping non-blob path at {git_commit_hash}:{file_path}")
        return None
    file_hash = get_file_hash_from_content(content)
    write_file_info_from_content(pig_root, file_hash, content)


    return file_hash


def add_git_commit_to_pig_repo(
    git_root: Path,
    pig_root: Path,
    commit_hash: str,
    parents_map: dict[str, str],
    cat_file_batch: CatFileBatch,
) -> str:
    result = subprocess.run(["git", "show", "--pretty=format:%an%n%at%n%P%n%s%n", "--name-status", "--no-renames", commit_hash], cwd=git_root, capture_output=True, text=True, errors="ignore")
    if result.returncode != 0:
        raise Exception(f"Git command failed: {result.stderr}")
    output_lines = result.stdout.strip().split('\n')
    author_line = output_lines[0]
    timestamp = int(output_lines[1])
    parent_git_hashes = output_lines[2].split() if output_lines[2] else []
    commit_message = output_lines[3]
    file_lines = output_lines[5:]   # skip the empty line after commit message
    raw_file_info_list = [f for f in (line.strip().split("\t") for line in file_lines)]
    file_info_list: list[tuple[str, str]] = []
    for status, file_path in raw_file_info_list:
        file_info_list.append((status, decode_git_quoted_path(file_path)))

    commit_files: dict[str, FileInfo] = {}

    if len(parent_git_hashes) < 2:
        deleted_files = []
        
        for status, file_path in file_info_list:
            if status == "D":
                deleted_files.append(file_path)
                continue
            converted_hash = convert_file_to_pig(git_root, commit_hash, pig_root, file_path, cat_file_batch)
            if converted_hash is not None:
                commit_files[file_path] = FileInfo(hash=converted_hash, lastEdited=timestamp)

        parent_pig_hash = "EMPTY-COMMIT" if len(parent_git_hashes) == 0 else parents_map[parent_git_hashes[0]]
        parent_commit_files = get_commit_info(pig_root, parent_pig_hash).files
        for file_path, file_info in commit_files.items():
            parent_commit_files[file_path] = file_info
        for file_path in deleted_files:
            if file_path in parent_commit_files:
                del parent_commit_files[file_path]
        commit_files = parent_commit_files
    else:
        if len(parent_git_hashes) > 2:
            merge_base_result = subprocess.run(["git", "merge-base", "--octopus", *(parent_git_hashes)], cwd=git_root, capture_output=True, text=True)
        else:
            merge_base_result = subprocess.run(["git", "merge-base", *(parent_git_hashes)], cwd=git_root, capture_output=True, text=True)
        if merge_base_result.returncode != 0:
            merge_base_hash = None
        else:
            merge_base_hash = merge_base_result.stdout.strip()
            merge_base_files = get_commit_info(pig_root, parents_map[merge_base_hash]).files
        changed_files = None
        if merge_base_hash is not None:
            diff_result = subprocess.run(
                ["git", "diff", "--name-only", merge_base_hash, commit_hash],
                cwd=git_root,
                capture_output=True,
                text=True,
                errors="ignore",
            )
            if diff_result.returncode != 0:
                raise Exception(f"Git command failed: {diff_result.stderr}")
            changed_files = set(decode_git_quoted_path(result) for result in diff_result.stdout.strip().split('\n'))
        # Merge commit so let's just get all of the files getting the diff is sort of complicated
        result = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit_hash], cwd=git_root, capture_output=True, text=True, errors="ignore")
        if result.returncode != 0:
            raise Exception(f"Git command failed: {result.stderr}")
        file_paths = [decode_git_quoted_path(result) for result in result.stdout.strip().split('\n')]
        for file_path in file_paths:
            if merge_base_hash is not None and changed_files is not None:
                if file_path not in changed_files:
                    # file is the same as merge base, so we can just use that version
                    try:
                        commit_files[file_path] = merge_base_files[file_path]
                    except KeyError:
                        # let's just fall back and convert it with the code below: I think this is only hit by submodules
                        assert cat_file_batch.get_blob(f"{commit_hash}:{file_path}")[0] is None, "Expected file to be non-blob type if it's missing from the merge base commit"
                    continue
                    
            # otherwise we have to convert the file from git to pig
            converted_hash = convert_file_to_pig(git_root, commit_hash, pig_root, file_path, cat_file_batch)
            if converted_hash is not None:
                commit_files[file_path] = FileInfo(hash=converted_hash, lastEdited=timestamp)

    parentCommits = [parents_map[parent_git_hash] for parent_git_hash in parent_git_hashes] if parent_git_hashes else ["EMPTY-COMMIT"]
    
    commit_info = CommitInfo(
        commitMessage=commit_message,
        author=author_line,
        timestamp=timestamp,
        parentCommits=parentCommits,
        files=commit_files
    )
    new_commit_hash = get_new_commit_hash()
    update_commit_info(pig_root, new_commit_hash, commit_info)
    return new_commit_hash
    

def create_pig_from_git_repo(git_root: Path, pig_root: Path) -> None:
    all_branches = get_all_branch_heads(git_root)
    commits_recreated: dict[str, str] = {}
    with CatFileBatch(git_root) as cat_file_batch:
        for branch_name in all_branches:
            commit_hashes = get_all_commits_for_branch(git_root, branch_name)
            if not commit_hashes:
                continue
            for commit_hash in reversed(commit_hashes):
                if commit_hash in commits_recreated:
                    continue
                pig_commit_hash = add_git_commit_to_pig_repo(
                    git_root,
                    pig_root,
                    commit_hash,
                    commits_recreated,
                    cat_file_batch,
                )
                commits_recreated[commit_hash] = pig_commit_hash
            # Update branch head
            update_branch_head(pig_root, branch_name, commits_recreated[commit_hashes[0]])
        
        
        
    

