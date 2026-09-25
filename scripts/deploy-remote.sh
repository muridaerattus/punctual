#!/usr/bin/env bash
# Invoked by deploy.sh on the VPS, not directly by users.
set -euo pipefail
umask 077

stage=${1:?Missing staging directory}
bind=${2:?Missing bind address}
port=${3:?Missing port}
mcp_host=${4:-}
config_dir="$HOME/.local/share/punctual"
mkdir -p "$config_dir"
chmod 700 "$config_dir"

# mkdir provides a deployment lock without requiring flock on the VPS.
lock="$config_dir/deploy.lock"
mkdir "$lock" 2>/dev/null || { echo 'Another deployment is running (deploy.lock exists)' >&2; exit 1; }
switch_started=false
committed=false
had_previous=false
was_running=false
finish() {
  result=$?
  trap - EXIT
  if $switch_started && ! $committed; then rollback; fi
  rmdir "$lock"
  exit "$result"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

image="punctual:deploy-$(date -u +%Y%m%d%H%M%S)-$$"
candidate_env="$stage/candidate.env"
if [[ -f $stage/server.env ]]; then
  cp "$stage/server.env" "$candidate_env"
elif [[ -f $config_dir/server.env ]]; then
  cp "$config_dir/server.env" "$candidate_env"
else
  key=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
  printf 'PUNCTUAL_API_KEY=%s\n' "$key" > "$candidate_env"
  echo 'Generated an API key; configuration will be saved on the VPS.'
fi
grep -Eq '^PUNCTUAL_API_KEY=.+$' "$candidate_env" || { echo 'Environment file must contain PUNCTUAL_API_KEY' >&2; exit 1; }
if [[ -n $mcp_host ]]; then
  # Append rather than replace existing allowed hosts; persist the probe host too.
  allowed=$(sed -n 's/^PUNCTUAL_ALLOWED_HOSTS=//p' "$candidate_env" | tail -n 1 | tr -d '\r')
  case ",$allowed," in
    *",$mcp_host,"*) ;;
    *) allowed="${allowed:+$allowed,}$mcp_host" ;;
  esac
  sed '/^PUNCTUAL_ALLOWED_HOSTS=/d; /^PUNCTUAL_MCP_HOST=/d' "$candidate_env" > "$stage/hosts.env"
  printf '\nPUNCTUAL_ALLOWED_HOSTS=%s\nPUNCTUAL_MCP_HOST=%s\n' "$allowed" "$mcp_host" >> "$stage/hosts.env"
  mv "$stage/hosts.env" "$candidate_env"
fi

mkdir "$stage/source"
tar -xzf "$stage/source.tar.gz" -C "$stage/source"
echo 'Building image on the VPS…'
docker build -t "$image" "$stage/source"

# Keep the previous container (including its settings) until health checks pass.
if docker container inspect punctual-previous >/dev/null 2>&1; then
  echo 'Container punctual-previous already exists; resolve the earlier deployment before retrying.' >&2
  exit 1
fi
rollback() {
  echo 'Deployment failed. Restoring the previous container…' >&2
  docker logs --tail 80 punctual >&2 2>/dev/null || true
  docker rm -f punctual >/dev/null 2>&1 || true
  if $had_previous; then
    docker rename punctual-previous punctual
    if $was_running; then docker start punctual >/dev/null; fi
  fi
}

if docker container inspect punctual >/dev/null 2>&1; then
  was_running=$(docker inspect --format '{{.State.Running}}' punctual)
  docker rename punctual punctual-previous
  had_previous=true
  switch_started=true
  docker stop punctual-previous >/dev/null
else
  switch_started=true
fi

if ! docker run -d --name punctual --restart unless-stopped \
  -p "$bind:$port:8000" --env-file "$candidate_env" \
  -e PUNCTUAL_DB=/data/punctual.db -e PUNCTUAL_STATIC=/app/static \
  -v punctual-data:/data "$image" >/dev/null; then
  exit 1
fi

echo 'Waiting for frontend, authentication and MCP checks…'
healthy=false
for ((attempt = 0; attempt < 30; attempt++)); do
  if docker exec punctual python -c '
import os
import json
import sys
from punctual.cli.diagnostics import diagnose
host = os.environ.get("PUNCTUAL_MCP_HOST")
if not host:
    print("No external MCP host configured; checking loopback. Use --mcp-host to validate the client-facing Host header.")
result = diagnose("http://127.0.0.1:8000", os.environ["PUNCTUAL_API_KEY"], host)
print(json.dumps(result))
sys.exit(0 if result["ok"] else 1)
' > "$stage/health.log" 2>&1; then
    healthy=true
    break
  fi
  sleep 2
done
cat "$stage/health.log"
if ! $healthy; then exit 1; fi

cp "$candidate_env" "$config_dir/server.env.next"
chmod 600 "$config_dir/server.env.next"
mv "$config_dir/server.env.next" "$config_dir/server.env"
committed=true
if $had_previous; then docker rm punctual-previous >/dev/null; fi
printf 'Deployed %s\nListening on %s:%s\nConfiguration: %s/server.env\nDatabase volume: punctual-data\n' \
  "$image" "$bind" "$port" "$config_dir"
