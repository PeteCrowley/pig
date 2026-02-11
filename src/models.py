from pydantic import BaseModel
from typing import Literal

class FileInfo(BaseModel):
    hash: str
    lastEdited: int

class StagingFileInfo(FileInfo):
    status: Literal["added", "modified", "deleted"]

class CommitInfo(BaseModel):
    commitMessage: str
    author: str
    timestamp: int
    parentCommits: list[str]
    files: dict[str,  FileInfo]

type BranchInfo = dict[str, str]
type StagingInfo = dict[str, StagingFileInfo]

class HeadInfo(BaseModel):
    type: Literal["branch", "commit"]
    value: str # branch name or commit hash




