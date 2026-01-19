#!/bin/bash
# Author: gadwant
# Release script for pdperf (Pandas Performance Optimizer)
# Usage: ./release.sh <version> [--no-upload] [--no-git]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments
VERSION="$1"
SKIP_UPLOAD=false
SKIP_GIT=false

for arg in "$@"; do
    case $arg in
        --no-upload)
            SKIP_UPLOAD=true
            ;;
        --no-git)
            SKIP_GIT=true
            ;;
    esac
done

# Check version argument
if [ -z "$VERSION" ]; then
    echo -e "${RED}Error: Version number required${NC}"
    echo ""
    echo "Usage: ./release.sh <version> [--no-upload] [--no-git]"
    echo ""
    echo "Examples:"
    echo "  ./release.sh 0.2.1              # Full release"
    echo "  ./release.sh 0.2.1 --no-upload  # Build only, don't upload"
    echo "  ./release.sh 0.2.1 --no-git     # Upload but don't create git tag"
    exit 1
fi

# Validate version format (basic check)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Invalid version format. Use X.Y.Z (e.g., 0.2.1)${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  pdperf Release Script v$VERSION${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Activate virtual environment if exists
if [ -d ".venv" ]; then
    echo -e "${YELLOW}[1/8] Activating virtual environment...${NC}"
    source .venv/bin/activate
else
    echo -e "${YELLOW}[1/8] No virtual environment found, using system Python...${NC}"
fi

# Step 1b: Install package in editable mode
echo -e "${YELLOW}[1b/8] Installing package in editable mode...${NC}"
pip install -e . -q
echo -e "${GREEN}✓ Package installed${NC}"

# Step 2: Run tests
echo -e "${YELLOW}[2/8] Running tests...${NC}"
if pytest -v; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${RED}✗ Tests failed! Aborting release.${NC}"
    exit 1
fi
echo ""

# Step 3: Update version in pyproject.toml
echo -e "${YELLOW}[3/8] Updating version in pyproject.toml...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
else
    # Linux
    sed -i "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
fi
echo -e "${GREEN}✓ pyproject.toml updated to $VERSION${NC}"

# Step 4: Update version in __init__.py
echo -e "${YELLOW}[4/8] Updating version in __init__.py...${NC}"
INIT_FILE="src/pandas_perf_opt/__init__.py"
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" "$INIT_FILE"
else
    sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" "$INIT_FILE"
fi
echo -e "${GREEN}✓ __init__.py updated to $VERSION${NC}"

# Step 4b: Update version in CITATION.cff
echo -e "${YELLOW}[4b/8] Updating version in CITATION.cff...${NC}"
CITATION_FILE="CITATION.cff"
TODAY=$(date +%Y-%m-%d)
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/^version: \".*\"/version: \"$VERSION\"/" "$CITATION_FILE"
    sed -i '' "s/^date-released: \".*\"/date-released: \"$TODAY\"/" "$CITATION_FILE"
else
    sed -i "s/^version: \".*\"/version: \"$VERSION\"/" "$CITATION_FILE"
    sed -i "s/^date-released: \".*\"/date-released: \"$TODAY\"/" "$CITATION_FILE"
fi
echo -e "${GREEN}✓ CITATION.cff updated to $VERSION ($TODAY)${NC}"
echo ""

# Step 5: Clean old builds
echo -e "${YELLOW}[5/8] Cleaning old builds...${NC}"
rm -rf dist/ build/ ./*.egg-info src/*.egg-info
echo -e "${GREEN}✓ Cleaned dist/, build/, and egg-info directories${NC}"
echo ""

# Step 6: Build package
echo -e "${YELLOW}[6/8] Building package...${NC}"
python -m build
echo -e "${GREEN}✓ Package built successfully${NC}"
echo ""

# Step 7: Verify build
echo -e "${YELLOW}[7/8] Verifying build with twine...${NC}"
if twine check dist/*; then
    echo -e "${GREEN}✓ Package verification passed${NC}"
else
    echo -e "${RED}✗ Package verification failed!${NC}"
    exit 1
fi
echo ""

# Step 8: Upload to PyPI
if [ "$SKIP_UPLOAD" = false ]; then
    echo -e "${YELLOW}[8/8] Uploading to PyPI...${NC}"
    echo -e "${BLUE}You may be prompted for your PyPI credentials.${NC}"
    if twine upload dist/*; then
        echo -e "${GREEN}✓ Successfully uploaded to PyPI${NC}"
    else
        echo -e "${RED}✗ Upload failed!${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}[8/8] Skipping upload (--no-upload flag)${NC}"
fi
echo ""

# Git operations
if [ "$SKIP_GIT" = false ]; then
    echo -e "${YELLOW}Creating git commit and tag...${NC}"
    
    git add .
    git commit -m "Release v$VERSION" || echo "Nothing to commit"
    git tag -a "v$VERSION" -m "v$VERSION"
    
    echo ""
    echo -e "${BLUE}Push to remote with:${NC}"
    echo "  git push origin main"
    echo "  git push origin v$VERSION"
    echo ""
    
    read -p "Push to origin now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin main
        git push origin "v$VERSION"
        echo -e "${GREEN}✓ Pushed to origin${NC}"
    fi
else
    echo -e "${YELLOW}Skipping git operations (--no-git flag)${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Release v$VERSION complete! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Create a GitHub release at: https://github.com/adwantg/pdperf/releases/new"
echo "  2. Verify installation: pip install pdperf==$VERSION"
echo ""
