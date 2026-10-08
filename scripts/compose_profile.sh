#!/usr/bin/env bash
# Shared Compose profile selector. Source this file, then call `dc ...`.
# SCOUTBOX_AI_RUNTIME: auto (default), nvidia, cpu, external/cloud.
# It may be supplied as an environment variable or as a simple value in .env.
if [[ -z "${SCOUTBOX_AI_RUNTIME:-}" && -f .env ]]; then
  _runtime_from_env="$(awk -F= '/^SCOUTBOX_AI_RUNTIME=/{print $2;exit}' .env 2>/dev/null | tr -d '\r' || true)"
  [[ -n "$_runtime_from_env" ]] && SCOUTBOX_AI_RUNTIME="$_runtime_from_env"
fi
SCOUTBOX_AI_RUNTIME="${SCOUTBOX_AI_RUNTIME:-auto}"
SCOUTBOX_COMPOSE_FILES=(-f docker-compose.yml)
SCOUTBOX_EFFECTIVE_RUNTIME="$SCOUTBOX_AI_RUNTIME"
if [[ "$SCOUTBOX_AI_RUNTIME" == "auto" ]]; then
  if [[ "$(uname -s 2>/dev/null || true)" == "Linux" ]] && command -v nvidia-smi >/dev/null 2>&1 && [[ -f docker-compose.nvidia.yml ]]; then
    SCOUTBOX_EFFECTIVE_RUNTIME="nvidia"
  else
    SCOUTBOX_EFFECTIVE_RUNTIME="external"
  fi
fi
case "$SCOUTBOX_EFFECTIVE_RUNTIME" in
  nvidia)
    [[ -f docker-compose.nvidia.yml ]] && SCOUTBOX_COMPOSE_FILES+=(-f docker-compose.nvidia.yml)
    ;;
  cpu)
    [[ -f docker-compose.cpu-ollama.yml ]] && SCOUTBOX_COMPOSE_FILES+=(-f docker-compose.cpu-ollama.yml)
    ;;
  external|cloud|host|none) ;;
  *)
    echo "WARNING: unknown SCOUTBOX_AI_RUNTIME=$SCOUTBOX_EFFECTIVE_RUNTIME; using base Compose configuration." >&2
    SCOUTBOX_EFFECTIVE_RUNTIME="external"
    ;;
esac
dc(){ docker compose "${SCOUTBOX_COMPOSE_FILES[@]}" "$@"; }
export SCOUTBOX_EFFECTIVE_RUNTIME
