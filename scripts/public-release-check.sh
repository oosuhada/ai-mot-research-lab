#!/bin/sh
set -eu

echo "[1/5] checking tracked secrets"
if git grep -nE '(sk-[A-Za-z0-9_-]{20,}|gh[opsu]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)' -- ':!scripts/public-release-check.sh'; then
  echo "Potential secret-like value found in tracked files." >&2
  exit 1
fi

echo "[2/5] checking tracked PDFs and database dumps"
tracked_binary="$(git ls-files '*.pdf' '*.dump' '*.sql.gz' '*.sqlite' '*.sqlite3' '*.db')"
if [ -n "$tracked_binary" ]; then
  printf '%s\n' "$tracked_binary" >&2
  echo "PDF/database artifact is tracked." >&2
  exit 1
fi

echo "[3/5] checking tracked file sizes (> 10 MiB)"
large_files="$(git ls-files -z | xargs -0 -I{} sh -c 'test -f "$1" && test "$(wc -c < "$1")" -gt 10485760 && echo "$1" || true' sh {} || true)"
if [ -n "$large_files" ]; then
  printf '%s\n' "$large_files" >&2
  echo "Tracked file larger than 10 MiB found." >&2
  exit 1
fi

echo "[4/5] checking old repository branding and private reference paths"
if git grep -nE '(ai-tech-management-research-lab|bist-mini-2-main|drive-download-20260706T090026Z-3-001)' -- ':!scripts/public-release-check.sh'; then
  echo "Old/private project reference found in tracked files." >&2
  exit 1
fi

echo "[5/5] checking environment files"
unexpected_env="$(git ls-files '.env' '.env.*' | grep -v '^\.env\.example$' || true)"
if [ -n "$unexpected_env" ]; then
  printf '%s\n' "$unexpected_env" >&2
  echo "Unexpected environment file is tracked." >&2
  exit 1
fi

echo "Public release checks passed."
