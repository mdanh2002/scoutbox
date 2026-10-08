#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"
case "$(uname -s 2>/dev/null || true)" in
  Darwin) exec "$ROOT/initial_setup_macos.sh" "$@" ;;
  Linux) exec "$ROOT/initial_setup_ubuntu.sh" "$@" ;;
  *) echo "Unsupported host OS. ScoutBox currently provides initial setup for macOS and Linux/Ubuntu." >&2; exit 1 ;;
esac
