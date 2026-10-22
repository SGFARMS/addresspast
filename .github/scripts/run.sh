#!/usr/bin/env bash
# Run a command; on failure, surface the last lines of its output as an error annotation
# (annotations are visible in the run page and through the checks API, logs are not always).
#   .github/scripts/run.sh <title> <command...>
# Set NOTICE_ON_SUCCESS=1 to also post the tail as a notice when it succeeds.
set -uo pipefail
title="$1"; shift
log="$(mktemp)"
"$@" 2>&1 | tee "$log"
status=${PIPESTATUS[0]}
encode() { tail -n "${1:-60}" "$log" | cut -c1-300 | sed -e 's/%/%25/g' | sed -e ':a;N;$!ba;s/\r//g;s/\n/%0A/g'; }
if [ "$status" -ne 0 ]; then
  echo "::error title=${title} failed::$(encode 60)"
elif [ "${NOTICE_ON_SUCCESS:-0}" = "1" ]; then
  echo "::notice title=${title}::$(encode 45)"
fi
exit "$status"
