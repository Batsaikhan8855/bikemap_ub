#!/bin/bash
set -e

cd /Users/macbookpro/bikemap_ub

echo "=== Lock файл устгана ==="
rm -f .git/index.lock

echo "=== venv замыг олно ==="
VENV_PATH=$(git ls-files | grep "backend/venv" | head -1 | sed 's|/[^/]*$||' | sed 's|/[^/]*$||' | sed 's|/[^/]*$||')
echo "venv зам: $VENV_PATH"

echo "=== venv git-ээс хасна ==="
git rm -r --cached "$VENV_PATH/" 2>/dev/null || echo "venv аль хэдийн хасагдсан"

echo "=== __pycache__ хасна ==="
git ls-files | grep "__pycache__" | xargs -r git rm -r --cached 2>/dev/null || true

echo "=== *.pyc хасна ==="
git ls-files | grep "\.pyc$" | xargs -r git rm --cached 2>/dev/null || true

echo "=== .gitignore шинэчилнэ ==="
GITIGNORE=$(git ls-files | grep ".gitignore" | head -1 | xargs dirname)/.gitignore
printf "\nvenv/\n__pycache__/\n*.pyc\ndb.sqlite3\n" >> "$GITIGNORE"

echo "=== Commit хийнэ ==="
git add -A
git commit -m "Remove venv and pycache from git tracking"

echo "=== Push хийнэ ==="
git push origin main

echo "=== АМЖИЛТТАЙ! ==="
