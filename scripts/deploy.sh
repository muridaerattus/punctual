#!/usr/bin/env bash
# Upload the current checkout and deploy it using Docker on a remote host.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/deploy.sh USER@HOST [OPTIONS]

Options:
  --env-file FILE     Docker environment file (stored on the VPS with mode 600)
  --bind ADDRESS      Published listen address (default: 127.0.0.1)
  --port PORT         Published HTTP port (default: 8000)
  --mcp-host HOST     Client-facing hostname[:port]; append to allowed hosts and check MCP
  --ssh-port PORT     SSH port (default: 22)
  --identity FILE     SSH private key
  --help             Show this help

Requires SSH access and permission to run Docker on the VPS. Existing server
configuration is reused unless --env-file is supplied. A first deployment without
an environment file generates an API key on the VPS.
EOF
}

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
port_number() { [[ "$1" =~ ^[0-9]{1,5}$ ]] && (( 10#$1 >= 1 && 10#$1 <= 65535 )); }

if [[ ${1:-} == --help ]]; then usage; exit 0; fi
[[ $# -gt 0 ]] || { usage >&2; exit 1; }
host=$1
shift
[[ $host != -* && $host != *[[:space:]]* ]] || fail 'Invalid SSH destination'
env_file=''
bind=127.0.0.1
port=8000
ssh_port=22
identity=''
mcp_host=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file|--bind|--port|--ssh-port|--identity|--mcp-host)
      [[ $# -ge 2 && -n $2 ]] || fail "Missing value for $1"
      case "$1" in
        --env-file) env_file=$2 ;;
        --bind) bind=$2 ;;
        --port) port=$2 ;;
        --ssh-port) ssh_port=$2 ;;
        --identity) identity=$2 ;;
        --mcp-host) mcp_host=$2 ;;
      esac
      shift 2 ;;
    --help) usage; exit 0 ;;
    *) fail "Unknown option: $1" ;;
  esac
done
port_number "$port" || fail 'Invalid HTTP port'
port_number "$ssh_port" || fail 'Invalid SSH port'
bind_pattern='^([0-9]{1,3}\.){3}[0-9]{1,3}$|^\[[0-9a-fA-F:]+\]$'
[[ $bind =~ $bind_pattern ]] || fail 'Bind address must be IPv4 or bracketed IPv6'
[[ -z $env_file || -f $env_file ]] || fail 'Environment file does not exist'
[[ -z $identity || -f $identity ]] || fail 'SSH identity file does not exist'
mcp_host_pattern='^([a-zA-Z0-9][a-zA-Z0-9.-]*|\[[0-9a-fA-F:]+\])(:[0-9]{1,5})?$'
[[ -z $mcp_host || $mcp_host =~ $mcp_host_pattern ]] || fail 'MCP host must be hostname[:port], without a scheme or path'
for command in ssh scp tar; do command -v "$command" >/dev/null || fail "$command is required"; done

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
extra_excludes=()
if [[ -n $env_file ]]; then
  env_file=$(cd -- "$(dirname -- "$env_file")" && pwd)/$(basename -- "$env_file")
  extra_excludes+=(--exclude="${env_file#"$root/"}")
fi
ssh_args=(-p "$ssh_port")
scp_args=(-P "$ssh_port")
if [[ -n $identity ]]; then ssh_args+=(-i "$identity"); scp_args+=(-i "$identity"); fi
local_stage=$(mktemp -d)
remote_stage=''
cleanup() {
  rm -rf -- "$local_stage"
  if [[ -n $remote_stage ]]; then
    # The staging path was validated above; expansion must happen locally.
    # shellcheck disable=SC2029
    ssh "${ssh_args[@]}" "$host" "rm -rf -- '$remote_stage'" </dev/null || true
  fi
}
trap cleanup EXIT

printf 'Checking Docker on %s…\n' "$host"
ssh "${ssh_args[@]}" "$host" 'command -v bash >/dev/null && docker info >/dev/null' ||
  fail 'The remote user must be able to run Bash and Docker without an interactive sudo prompt'
candidate_stage=$(ssh "${ssh_args[@]}" "$host" 'mktemp -d /tmp/punctual-deploy.XXXXXXXX')
[[ $candidate_stage =~ ^/tmp/punctual-deploy\.[a-zA-Z0-9]+$ ]] || fail 'Unexpected remote staging path'
remote_stage=$candidate_stage

printf 'Uploading source…\n'
tar -czf "$local_stage/source.tar.gz" \
  --exclude='.git' --exclude='.venv' --exclude='node_modules' --exclude='dist' \
  --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
  --exclude='.env' --exclude='.env.*' --exclude='*.env' --exclude='*.db*' \
  --exclude='*.sqlite*' --exclude='*.pem' --exclude='*.key' \
  "${extra_excludes[@]}" \
  -C "$root" Dockerfile .dockerignore backend frontend
scp "${scp_args[@]}" "$local_stage/source.tar.gz" "$root/scripts/deploy-remote.sh" "$host:$remote_stage/"
if [[ -n $env_file ]]; then
  scp "${scp_args[@]}" "$env_file" "$host:$remote_stage/server.env"
fi

# Quote arguments for the remote login shell; the deployment helper is run by Bash.
printf -v remote_command 'bash %q %q %q %q %q' "$remote_stage/deploy-remote.sh" "$remote_stage" "$bind" "$port" "$mcp_host"
# Arguments were shell-quoted locally with printf %q.
# shellcheck disable=SC2029
ssh "${ssh_args[@]}" "$host" "$remote_command"
