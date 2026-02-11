from pathlib import Path
import difflib
import time
from .errors import PigError
from .branching import get_current_branch, update_branch_head
from .models import CommitInfo, FileInfo, HeadInfo
from .commit_helpers import (
    current_commit_hash,
    get_commit_info,
    get_new_commit_hash,
    update_commit_info,
)
from .staging_helpers import get_staging_info
from .file_helpers import (
    read_compressed_file,
    write_file_info,
    get_file_hash,
)
from .repo_utils import update_head
from .recreatedirectory import clear_directory, recreate_directory

def find_common_ancestor(pig_root: Path, commit_hash1: str, commit_hash2: str) -> str:
    ancestors1 = set()
    batch_size = 50
    chash1 = commit_hash1
    chash2 = commit_hash2
    while commit_hash1 is not None and commit_hash2 is not None:
        for _ in range(batch_size):
            ancestors1.add(chash1)
            commit_info1 = get_commit_info(pig_root, chash1)
            chash1 = commit_info1.parentCommit
            if chash1 is None:
                break
        for _ in range(batch_size):
            if chash2 and chash2 in ancestors1:
                return chash2
            commit_info2 = get_commit_info(pig_root, chash2)
            chash2 = commit_info2.parentCommit
            if chash2 is None:
                break
    raise PigError("no common ancestor found")

def merge_files(pig_root: Path, file_path: str, file1_info: FileInfo, file2_info: FileInfo, base_file_info: FileInfo | None) -> FileInfo:
    # if manual merge file exists, use that
    manual_merge_path = pig_root / ".pig" / "merge" / file_path
    if manual_merge_path.exists():
        merged_hash = get_file_hash(manual_merge_path)
        write_file_info(pig_root, merged_hash, manual_merge_path)
        manual_merge_path.unlink()
        return FileInfo(
            hash=merged_hash,
            lastEdited=max(file1_info.lastEdited, file2_info.lastEdited)
        )
    base_file_lines = [] if not base_file_info else read_compressed_file(pig_root, base_file_info.hash)
    file1_lines = read_compressed_file(pig_root, file1_info.hash)
    file2_lines = read_compressed_file(pig_root, file2_info.hash)

    diff1 = difflib.SequenceMatcher(None, base_file_lines, file1_lines).get_opcodes()
    diff2 = difflib.SequenceMatcher(None, base_file_lines, file2_lines).get_opcodes()
    # returns opcodes of the form (tag, i1, i2, j1, j2)

    merge_lines = []
    has_conflicts = False
    
    # Convert diffs to a more usable format indexed by base position
    diff1_dict = {}
    diff2_dict = {}
    
    for tag, i1, i2, j1, j2 in diff1:
        for pos in range(i1, i2):
            diff1_dict[pos] = (tag, i1, i2, j1, j2)
    
    for tag, i1, i2, j1, j2 in diff2:
        for pos in range(i1, i2):
            diff2_dict[pos] = (tag, i1, i2, j1, j2)
    

    base_pos = 0
    processed_base_indices = set()
    # Merge by walking through base file and applying both changes
    while base_pos <= len(base_file_lines):
        change1 = diff1_dict.get(base_pos)
        change2 = diff2_dict.get(base_pos)
        
        if change1 is None and change2 is None:
            # No changes from either side
            if base_pos < len(base_file_lines):
                merge_lines.append(base_file_lines[base_pos])
            base_pos += 1
        elif change1 is not None and change2 is None:
            # Only file1 changed
            tag1, i1, i2, j1, j2 = change1
            if base_pos not in processed_base_indices:
                processed_base_indices.update(range(i1, i2))
                merge_lines.extend(file1_lines[j1:j2])
                base_pos = i2
            else:
                base_pos += 1
        elif change1 is None and change2 is not None:
            # Only file2 changed
            tag2, i1, i2, j1, j2 = change2
            if base_pos not in processed_base_indices:
                processed_base_indices.update(range(i1, i2))
                merge_lines.extend(file2_lines[j1:j2])
                base_pos = i2
            else:
                base_pos += 1
        else:
            assert change1 is not None and change2 is not None  # for type checker
            # Both files changed - need to check if they changed the same way
            tag1, i1_1, i2_1, j1_1, j2_1 = change1
            tag2, i1_2, i2_2, j1_2, j2_2 = change2
            
            if base_pos not in processed_base_indices:
                # Check if both sides made the same change
                if file1_lines[j1_1:j2_1] == file2_lines[j1_2:j2_2] and i1_1 == i1_2 and i2_1 == i2_2:
                    # Same change, take it once
                    merge_lines.extend(file1_lines[j1_1:j2_1])
                else:
                    # Conflicting changes
                    has_conflicts = True
                    merge_lines.append("<<<<<<< HEAD\n")
                    merge_lines.extend(file1_lines[j1_1:j2_1])
                    merge_lines.append("=======\n")
                    merge_lines.extend(file2_lines[j1_2:j2_2])
                    merge_lines.append(">>>>>>> merge\n")
                
                processed_base_indices.update(range(i1_1, i2_1))
                base_pos = max(i2_1, i2_2)
            else:
                base_pos += 1

    manual_merge_path.parent.mkdir(parents=True, exist_ok=True)

    with open(manual_merge_path, "w") as f:
        f.writelines(merge_lines)

    if has_conflicts:
        print(f"Warning: merge resulted in conflicts; please resolve them manually in {manual_merge_path.as_posix()}.")
        raise PigError("merge conflicts detected, please resolve them manually in the indicated file")
    
    # Write merged content to a file and get its hash
    merged_hash = get_file_hash(manual_merge_path)
    write_file_info(pig_root, merged_hash, manual_merge_path)

    # Remove file from temporary merge directory
    manual_merge_path.unlink()
    
    return FileInfo(
        hash=merged_hash,
        lastEdited=max(file1_info.lastEdited, file2_info.lastEdited)
    )

def merge_commits(pig_root: Path, target_commit_hash: str) -> None:
    if get_staging_info(pig_root) != {}:
        raise PigError("cannot merge commits with staged changes; please commit or unstage them first")
    
    current_commit = current_commit_hash(pig_root)
    base_commit = find_common_ancestor(pig_root, current_commit, target_commit_hash)

    current_commit_info = get_commit_info(pig_root, current_commit)
    target_commit_info = get_commit_info(pig_root, target_commit_hash)
    base_commit_info = get_commit_info(pig_root, base_commit)

    current_commit_files = set(current_commit_info.files.keys())
    target_commit_files = set(target_commit_info.files.keys())

    merge_commit_info = CommitInfo(
        commitMessage = f"Merge commit {target_commit_hash} into {current_commit}",
        author = "Pete Crowley",
        timestamp = int(time.time()),
        parentCommits=[current_commit, target_commit_hash],
        files = {}
    )

    for file in current_commit_files:
        if file not in target_commit_files:
            merge_commit_info.files[file] = current_commit_info.files[file]
        elif current_commit_info.files[file].hash == target_commit_info.files[file].hash:
            merge_commit_info.files[file] = FileInfo(
                hash=current_commit_info.files[file].hash,
                lastEdited=max(
                    current_commit_info.files[file].lastEdited,
                    target_commit_info.files[file].lastEdited
                )
            )
        elif file in base_commit_info.files and \
             current_commit_info.files[file].hash == base_commit_info.files[file].hash:
            merge_commit_info.files[file] = target_commit_info.files[file]
        elif file in base_commit_info.files and \
             target_commit_info.files[file].hash == base_commit_info.files[file].hash:
            merge_commit_info.files[file] = current_commit_info.files[file]
        else:
            base_file_info = base_commit_info.files.get(file)
            merged_file_info = merge_files(
                pig_root,
                file,
                current_commit_info.files[file],
                target_commit_info.files[file],
                base_file_info
            )
            merge_commit_info.files[file] = merged_file_info
    
    merge_commit_hash = get_new_commit_hash()
    update_commit_info(pig_root, merge_commit_hash, merge_commit_info)
    recreate_directory(pig_root, merge_commit_hash)
    current_branch = get_current_branch(pig_root)
    if current_branch:
        update_branch_head(pig_root, current_branch, merge_commit_hash)
    else:
        update_head(pig_root, HeadInfo(type="commit", value=merge_commit_hash))
    
    clear_directory(pig_root / ".pig" / "merge")
    (pig_root / ".pig" / "merge").rmdir()
    




    
    