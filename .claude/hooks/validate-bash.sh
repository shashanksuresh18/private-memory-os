#!/bin/bash
# validate-bash.sh — Pre-commit hook for validation
# This hook runs before/after tool execution to enforce quality gates

set -euo pipefail

echo "🔍 Running pre-commit validation..."

# 1. Check for common issues
echo "  ▸ Checking for console.log statements..."
if grep -rn "console\.log" --include="*.js" --include="*.ts" src/ 2>/dev/null; then
    echo "  ⚠️  WARNING: Found console.log statements. Remove before committing."
fi

# 2. Check for hardcoded secrets
echo "  ▸ Scanning for hardcoded secrets..."
SECRETS_PATTERN='(password|secret|api_key|apikey|token|private_key)\s*[:=]\s*["\x27][^"\x27]+'
if grep -rniE "$SECRETS_PATTERN" --include="*.js" --include="*.ts" --include="*.json" src/ 2>/dev/null; then
    echo "  🔴 CRITICAL: Possible hardcoded secrets found! Aborting."
    exit 1
fi

# 3. Check for TODO/FIXME items
echo "  ▸ Checking for TODO/FIXME items..."
TODO_COUNT=$(grep -rn "TODO\|FIXME\|HACK" --include="*.js" --include="*.ts" src/ 2>/dev/null | wc -l)
if [ "$TODO_COUNT" -gt 0 ]; then
    echo "  ℹ️  INFO: Found $TODO_COUNT TODO/FIXME/HACK comments."
fi

# 4. Validate JSON files
echo "  ▸ Validating JSON files..."
for f in $(find . -name "*.json" -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null); do
    if ! python -m json.tool "$f" > /dev/null 2>&1; then
        echo "  🔴 INVALID JSON: $f"
        exit 1
    fi
done

# 5. Check file sizes
echo "  ▸ Checking for oversized files..."
find . -type f -size +1M -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null | while read -r file; do
    echo "  ⚠️  WARNING: Large file detected: $file"
done

echo "✅ Validation complete!"
exit 0
