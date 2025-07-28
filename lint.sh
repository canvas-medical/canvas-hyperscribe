#!/bin/bash
set -e

echo "Running pre-commit hooks (same as commit-time checks)..."
./.git/hooks/pre-commit

echo "All linting checks passed!"