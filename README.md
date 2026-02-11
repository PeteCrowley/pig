# pig
`pig` stands for either "Pete's Implementation of Git" or "Python Implementation of Git". It's a project I created in order to better understand git internals so I can really know what's going on instead of brainlessly typing the same couple git commands over and over again. `pig` conceptually works the same as git with of course a few differences. I tried to mirror `git` commands the best I could and the ones I have implemented so far are in the table below. I also briefly describe how the project works below the table.
### Commands
| Command | Arguments | Description |
|---------|-----------|-------------|
| `init` | | Initialize a new pig repository |
| `add` | `<filepattern>` | Add files to staging area |
| `rm` | `<filepattern>` | Remove files from staging area |
| `status` | | Show the status of the repository |
| `commit` | `-m <message>` | Commit staged changes with a message |
| `checkout` | `[-b] <name> [-s <start_point>]` | Checkout a branch or commit; use `-b` to create a new branch |
| `switch` | `<name>` | Switch to an existing branch |
| `merge` | `<name>` | Merge a branch into the current branch |
| `log` | `[-n <number>]`| Show commit logs in chronological order (default 10)|
| `git-convert` | `<git_root>` | Convert a Git repository to a pig repository |
| `branch` | `[-c <name>] [-d <name>] [-l]` | Manage branches: create, delete, or list |

### Project Overview
#### How Commits Work

In `pig`, a commit is a snapshot of your project at a particular point in time. Each commit contains:
- A unique SHA-256 hash (generated from the timestamp and a random value)
- A commit message describing the changes
- Author information
- A timestamp
- A reference to its parent commit (the previous commit in the history)
- A dictionary of files and their current versions

When you run `pig commit`, all staged files are included in the commit, and the commit becomes the new HEAD of your current branch.

#### How Branches Work

Branches in `pig` are pointers to commits. They allow you to work on different versions of your project simultaneously. Key concepts:

- **Branch Creation**: When you create a branch, it points to a specific commit (the current commit by default). You can also specify a starting point.
- **Active Branch**: The `.pig/HEAD` file tracks which branch you're currently on. When you commit, the active branch's pointer is updated to the new commit.
- **Branch Storage**: All branch names and their commit pointers are stored in `.pig/BRANCH_HEADS.json`.

#### Storage Structure

The `.pig` directory contains the following:

```
.pig/
├── objects/              # Compressed file contents
├── commits/              # Commit metadata (JSON files)
├── compressed-files/     # Gzip-compressed versions of tracked files
├── HEAD                  # Current branch or commit reference
├── BRANCH_HEADS.json     # Mapping of branch names to commit hashes
└── staging.json          # Files staged for the next commit
```

**File Storage**: Each file is stored in compressed format with its SHA-256 hash as the filename. This allows `pig` to deduplicate identical files across commits. One key improvement to make is to implement my version of git's "delta-diff" files so I can just store small changes that have been made instead of a full new file each time.

**Commit Storage**: Each commit is stored as a JSON file in the `commits/` directory, containing metadata and references to file hashes rather than storing file contents directly.

#### How Merging Works

When merging branches, `pig` uses a 3-way merge strategy:
1. Find the common ancestor commit between the two branches
2. Compare changes from the base to each branch
3. Apply non-conflicting changes automatically
4. Mark conflicting sections with conflict markers (`<<<<<<< HEAD`, `=======`, `>>>>>>> merge`) for manual resolution.

This merge algorithm probably isn't as polished as what you'll see in git, but it works well enough for this project.

#### Converting From Git to Pig
The `git-convert <git_root>` command will convert an existing git repository into a `pig` repository. This is one of my favorite features because it allows me to take all my favorite git repositories and mess with them using `pig`. I tested this feature with multiple large git repos including `git` itself and it properly converts the repo over (save for symlinks and submodules). 