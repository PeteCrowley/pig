from pathlib import Path
from collections import deque
import time

from .errors import PigError
from .repo_utils import find_pig_root_dir
from .commit_helpers import current_commit_hash, get_commit_info

def topological_log(pig_root: Path, num_to_print: int):
    if pig_root is None:
        raise PigError("not in a pig repository")
    if num_to_print <= 0:
        raise PigError("number of commits to show must be positive")
    
    head_commit = current_commit_hash(pig_root)
    commit_infos = {}
    parent_map = {}

    stack = [head_commit]
    count = 0
    while stack:
        commit_hash = stack.pop()
        commit_info = get_commit_info(pig_root, commit_hash)
        commit_infos[commit_hash] = commit_info
        parent_map[commit_hash] = list(commit_info.parentCommits)
        for parent_hash in commit_info.parentCommits:
            if parent_hash not in commit_infos:
                stack.append(parent_hash)
        count += 1
        print(count, end="\n")

    indegree = {commit_hash: 0 for commit_hash in commit_infos}
    for _, parents in parent_map.items():
        for parent_hash in parents:
            if parent_hash in indegree:
                indegree[parent_hash] += 1

    commits_printed = 0
    queue = deque([head_commit])
    seen = set()
    while queue:
        commit_hash = queue.popleft()
        seen.add(commit_hash)
        commit_info = commit_infos[commit_hash]

        for parent_hash in parent_map.get(commit_hash, []):
            if parent_hash in indegree:
                indegree[parent_hash] -= 1
                if indegree[parent_hash] == 0 and parent_hash not in seen:
                    queue.append(parent_hash)
    
        print(f"Commit: {commit_hash}")
        print(f"Author: {commit_info.author}")
        print(f"Date: {time.ctime(commit_info.timestamp)}")
        print(f"\n    {commit_info.commitMessage}\n")
        commits_printed += 1
        if commits_printed >= num_to_print:
            break
    
