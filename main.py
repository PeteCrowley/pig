import sys
from pathlib import Path

import argparse
from src.commands import map_command

def main():
    parser = argparse.ArgumentParser(description="Pig CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # init command
    subparsers.add_parser("init", help="Initialize a new pig repository")
    
    # add command
    add_parser = subparsers.add_parser("add", help="Add files to staging")
    add_parser.add_argument("filepattern", help="File pattern to add")

    # status command
    subparsers.add_parser("status", help="Show the status of the repository")

    # commit command
    commit_parser = subparsers.add_parser("commit", help="Commit staged changes")
    commit_parser.add_argument("-m", "--message", required=True, help="Commit message")

    # checkout command
    checkout_parser = subparsers.add_parser("checkout", help="Checkout a branch or commit")
    checkout_parser.add_argument("-b", "--create", action="store_true", help="Checkout a new branch")
    checkout_parser.add_argument("name", help="Branch name or commit hash to checkout")
    checkout_parser.add_argument("-s", "--start_point", required=False, help="Starting point for new branch (commit hash or branch name)")

    # switch command
    switch_parser = subparsers.add_parser("switch", help="Switch to an existing branch")
    switch_parser.add_argument("name", help="Branch name to switch to")

    # merge command
    merge_parser = subparsers.add_parser("merge", help="Merge a branch into the current branch")
    merge_parser.add_argument("name", help="Branch name to merge from")

    # log command
    log_parser = subparsers.add_parser("log", help="Show commit logs")

    # branch command
    branch_parser = subparsers.add_parser("branch", help="Manage branches")
    branch_parser.add_argument("-c", "--create", required=False, metavar="BRANCH_NAME", help="Create a new branch")
    branch_parser.add_argument("-d", "--delete", required=False, metavar="BRANCH_NAME", help="Delete the specified branch")
    branch_parser.add_argument("-l", "--list", action="store_true", help="List all branches")

    # rm command
    rm_parser = subparsers.add_parser("rm", help="Remove files from staging")
    rm_parser.add_argument("filepattern", help="File pattern to remove from staging")
    
    
    args = parser.parse_args()
    map_command(args.command)(args)


if __name__ == "__main__":
    main()
