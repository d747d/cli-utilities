#!/bin/bash

# Script to clean large files from Git history
# Usage: ./clean_large_files.sh [size_limit_mb]

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default size limit in MB (GitHub's limit is 100MB)
SIZE_LIMIT_MB=${1:-100}
SIZE_LIMIT_BYTES=$((SIZE_LIMIT_MB * 1024 * 1024))

echo -e "${GREEN}Git Large File Cleaner${NC}"
echo "================================"
echo "Size limit: ${SIZE_LIMIT_MB}MB"
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not in a git repository${NC}"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}Error: You have uncommitted changes.${NC}"
    echo "Please commit or stash your changes before running this script."
    echo ""
    echo "Options:"
    echo "  1. Commit your changes: git add . && git commit -m 'Save changes'"
    echo "  2. Stash your changes: git stash"
    echo "  3. Discard changes: git reset --hard HEAD (WARNING: this will lose changes)"
    exit 1
fi

# Check for untracked files
if [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo -e "${YELLOW}Warning: You have untracked files.${NC}"
    echo "These files will not be affected, but you may want to:"
    echo "  - Add them: git add <files>"
    echo "  - Or add to .gitignore"
    echo ""
    echo -n "Continue anyway? (y/N): "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# Create backup branch
BACKUP_BRANCH="backup-before-cleanup-$(date +%Y%m%d-%H%M%S)"
echo -e "${YELLOW}Creating backup branch: $BACKUP_BRANCH${NC}"
git branch $BACKUP_BRANCH

# Find large files in history
echo -e "\n${YELLOW}Searching for files larger than ${SIZE_LIMIT_MB}MB in history...${NC}"
LARGE_FILES=$(git rev-list --objects --all |
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' |
  sed -n 's/^blob //p' |
  awk -v limit=$SIZE_LIMIT_BYTES '$2 >= limit' |
  sort --numeric-sort --key=2 --reverse)

if [ -z "$LARGE_FILES" ]; then
    echo -e "${GREEN}No files larger than ${SIZE_LIMIT_MB}MB found in history!${NC}"
    git branch -d $BACKUP_BRANCH
    exit 0
fi

echo -e "\n${RED}Found large files:${NC}"
echo "$LARGE_FILES" | while read line; do
    hash=$(echo $line | awk '{print $1}')
    size=$(echo $line | awk '{print $2}')
    file=$(echo $line | cut -d' ' -f3-)
    size_mb=$((size / 1024 / 1024))
    echo "  - $file (${size_mb}MB)"
done

# Ask for confirmation
echo -e "\n${YELLOW}WARNING: This will rewrite Git history!${NC}"
echo "A backup branch has been created: $BACKUP_BRANCH"
echo -n "Do you want to proceed with removing these files? (y/N): "
read -r response

if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "Aborted. Backup branch kept: $BACKUP_BRANCH"
    exit 0
fi

# Remove large files from history
echo -e "\n${YELLOW}Removing large files from history...${NC}"
FILES_TO_REMOVE=$(echo "$LARGE_FILES" | cut -d' ' -f3- | sort -u)

for file in $FILES_TO_REMOVE; do
    echo "Removing: $file"
    git filter-branch --force --index-filter \
        "git rm --cached --ignore-unmatch '$file'" \
        --prune-empty --tag-name-filter cat -- --all
done

# Clean up
echo -e "\n${YELLOW}Cleaning up...${NC}"
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Show results
echo -e "\n${GREEN}Cleanup complete!${NC}"
echo "Original history backed up in branch: $BACKUP_BRANCH"
echo ""
echo "Repository size before: $(du -sh .git | cut -f1)"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review the changes with: git log"
echo "2. If everything looks good, force push with:"
echo "   git push origin --force --all"
echo "   git push origin --force --tags"
echo "3. Delete the backup branch when satisfied:"
echo "   git branch -d $BACKUP_BRANCH"
echo ""
echo -e "${RED}WARNING: Force pushing will rewrite remote history!${NC}"
echo "Make sure all team members are aware before proceeding."