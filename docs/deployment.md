# Deployment and configuration

[Documentation index](../README.md#documentation)

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `PUNCTUAL_API_KEY` | Required | Shared bearer key; server refuses to start without it |
| `PUNCTUAL_DB` | `punctual.db` in working directory | SQLite file; parent directory must exist |
| `PUNCTUAL_STATIC` | Repository `frontend/dist` | Built frontend directory |
| `PUNCTUAL_ALLOWED_HOSTS` | Loopback/server hosts | Comma-separated additional MCP Host values, including port if needed |
| `PUNCTUAL_ALLOWED_ORIGINS` | Same-origin / loopback | Comma-separated additional permitted MCP browser origins |
| `PUNCTUAL_MCP_HOST` | Unset (loopback check) | Deployment diagnostic Host header; saved by `--mcp-host` |

## Browser OIDC sign-in

Leave all OIDC settings unset for the existing local, bearer-key sign-in mode.
For a hosted team workspace, configure these server-only variables together:

| Variable | Example / default |
| --- | --- |
| `PUNCTUAL_PUBLIC_URL` | `https://punctual.example.com` (exact HTTPS origin) |
| `PUNCTUAL_OIDC_ISSUER` | `https://auth.example.com/application/o/punctual/` (use your provider's issuer) |
| `PUNCTUAL_OIDC_CLIENT_ID` | `punctual` |
| `PUNCTUAL_OIDC_CLIENT_SECRET` | Confidential client secret, from protected runtime configuration |
| `PUNCTUAL_OIDC_GROUP` | Required when OIDC is enabled; no default. Example: `Example Team`, an exact entry in the signed ID token's `groups` array |
| `PUNCTUAL_SESSION_SECONDS` | `900`; 60–3600, capped by the ID token's expiry |

Keep `PUNCTUAL_API_KEY` and existing allowed MCP hosts: API/MCP/CLI agents continue
using the same bearer key. MCP is bearer-only even when a browser cookie is present.
The hosted frontend offers **Sign in with SSO**, clears any old browser-stored
API key, and never receives the client secret, ID token, access token or bearer key.
Team members share every board; forwarded identity headers grant no access.

Register exactly `https://punctual.example.com/api/auth/callback` (or your
public origin plus `/api/auth/callback`) with the provider. Use a confidential
authorization-code client, RS256 signing and `openid profile email` scopes; include
groups in the ID token. Require team membership and S256 PKCE at the provider too.
Discovery must report the configured issuer exactly and HTTPS endpoints including
an end-session endpoint. Authlib handles code exchange/client authentication/PKCE;
PyJWT validates the RSA signature, issuer, audience, expiry and issued-at time.
Punctual additionally checks nonce, authorized party and group membership.
State is bound to a five-minute, single-use server-side transaction and secure
HTTP-only cookie. Callback destinations are fixed, not supplied by callers.

Browser sessions use random opaque `__Host-` cookies with Secure, HttpOnly,
SameSite=Lax and Path=/; only their SHA-256 hashes are kept in process memory.
**Run exactly one backend worker/replica.** Sessions have a fixed deadline, never
refresh, and expire no later than the ID token. A restart/deploy immediately revokes
all browser sessions and unfinished logins. No session database or schema migration
is added; task data, revisions and leases retain their existing persistence.
Session capacity is bounded (4096 sessions, 1024 pending logins).

Sign-in starts are limited to 10 per client address and 100 globally in a rolling
60-second window. Excess attempts receive HTTP 429 with `Retry-After`; rejected
attempts do not extend the window. These limits also bound the rate-limiter's
memory and prevent anonymous requests from filling the pending-login pool.
In-flight starts reserve capacity before contacting the provider, and release it
on failure or cancellation. Provider discovery is cached for five minutes, with
one refresh at a time and a five-second retry backoff after failures.

Client addresses come from the ASGI server, not directly from forwarding headers.
Behind a reverse proxy, configure Uvicorn's `--forwarded-allow-ips` with the actual
trusted proxy addresses so clients receive separate limits. Restrict direct access
to the backend; do not trust forwarding headers from arbitrary internet clients.
Clients sharing one address share its sign-in limit.

Group removal blocks new logins; an existing session lasts only to its deadline
(at most 15 minutes by default, often shorter with provider token expiry).
For immediate offboarding, remove membership and restart Punctual to revoke all
browser sessions. No backchannel logout or individual administrative revocation
endpoint is implemented. Signing out revokes the local session before navigating
to the provider's end-session flow; finish that flow to end provider SSO too.
Other browser sessions remain subject to their own deadlines.

Cookie-authenticated writes and logout require the exact configured `Origin` plus
`X-Punctual-CSRF: 1`. This non-secret header forces cross-origin preflight; Punctual
does not enable CORS. Bearer requests remain independent of browser CSRF handling.
Keep the frontend on the same HTTPS origin as the API. Do not log callback query
strings or cookies: the Docker command disables Uvicorn access logs; use
`--no-access-log` for other hosted launchers and redact/disable proxy access logs.
Do not enable request-body/debug logging around authentication.

Before exposing a new deployment, test anonymous/nonmember denial, member login,
cookie-authenticated reads/writes, logout/replay denial, and existing bearer MCP.
Retain the provider rollout hold until application tests pass. Site-specific
Authentik provisioning, secrets transfer, proxy activation and rollout evidence
belong in the infrastructure repository.

## Docker

Requires Docker Engine or Docker Desktop. Run these commands from the repository
root (the directory containing `Dockerfile`). The image builds the frontend and
installs the backend and CLI; local Python and Node installations are not needed.

### Build and start

```sh
export PUNCTUAL_API_KEY='replace-with-your-shared-key'
docker build -t punctual .
docker run -d \
  --name punctual \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -e PUNCTUAL_API_KEY \
  -v punctual-data:/data \
  punctual
```

Open **http://localhost:8000** and sign in with the API key you exported. The HTTP
API is at `/api/tasks`; the MCP endpoint is **http://localhost:8000/mcp/**. Both
require `Authorization: Bearer <your-key>`.

The named volume `punctual-data` is created automatically and holds
`/data/punctual.db`. Tasks and leases survive container replacement. Alembic
migrations run automatically on startup. The container runs as a non-root user
(UID 10001); if you use a bind-mounted directory instead of the named volume,
make it writable by that UID.

### Check and manage the container

```sh
docker logs --tail 100 -f punctual
curl http://localhost:8000/health
docker exec punctual punctual --json list
docker stop punctual
docker start punctual
```

`docker logs -f` follows output; press Ctrl+C to stop following. The bundled CLI
inherits the container's API key and connects to its local backend.

### Update the image

After updating the source, rebuild and recreate the container using the same volume:

```sh
docker build -t punctual .
docker stop punctual
docker rm punctual
docker run -d \
  --name punctual \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -e PUNCTUAL_API_KEY \
  -v punctual-data:/data \
  punctual
```

Ensure `PUNCTUAL_API_KEY` is still exported in your shell. Container removal does
not remove the named volume. Keep any additional environment variables and port
mappings from your original deployment when recreating it. Docker environment
changes require container recreation, not just `docker restart`.

### Remote access

The commands above publish the service on the Docker host's loopback interface.
For a VPS, place a TLS reverse proxy in front of port 8000 and add the external
MCP hostname to the container's environment when creating it:

```sh
-e PUNCTUAL_ALLOWED_HOSTS='punctual.example.com'
```

Include the port in that value when clients use a non-default port, for example
`punctual.example.com:8443`. For a reverse proxy running in another container, put
both containers on a shared Docker network and proxy to `punctual:8000`.

Punctual is intended for small trusted groups, not sensitive information. One
backend process is sufficient for a lightweight VPS.

## Deploy to a remote VPS

Use `scripts/deploy.sh` from your local checkout. It uploads the current source
(including uncommitted changes), builds the image **on the VPS**, and starts or
updates the `punctual` container. Local Docker is not required.

Prerequisites:

- Locally: Bash, SSH, SCP, and tar.
- On the VPS: Bash, Docker Engine, and permission for the SSH user to run Docker
  without an interactive `sudo` prompt. Docker must be able to pull build images
  and download dependencies.
- Working SSH authentication, using your SSH agent, key, or normal SSH configuration.

From the repository root:

```sh
./scripts/deploy.sh deploy@your-vps
```

On the first deployment, the script generates an API key. Subsequent deployments
reuse the configuration in `~/.local/share/punctual/server.env` on the VPS. Retrieve
your generated key with:

```sh
ssh deploy@your-vps 'cat ~/.local/share/punctual/server.env'
```

Alternatively, create a local environment file and pass it explicitly:

```sh
cat > .env.deploy <<'EOF'
PUNCTUAL_API_KEY=replace-with-your-shared-key
PUNCTUAL_ALLOWED_HOSTS=punctual.example.com
EOF
chmod 600 .env.deploy
./scripts/deploy.sh deploy@your-vps --env-file .env.deploy
```

`--env-file` replaces the saved server configuration after a successful deployment.
The script stores that configuration with mode `600`. Environment files, databases,
Git history, dependency directories, and build output are excluded from the source
upload. It fixes the database and static paths to the Docker image's `/data` and
`/app/static` locations.

Available options:

```sh
./scripts/deploy.sh deploy@your-vps \
  --ssh-port 2222 \
  --identity ~/.ssh/vps_key \
  --bind 127.0.0.1 \
  --port 8000
```

The default bind address is `127.0.0.1`. Use your reverse proxy for remote access,
or open an SSH tunnel and visit **http://localhost:8000**:

```sh
ssh -N -L 8000:127.0.0.1:8000 deploy@your-vps
```

For direct network access, pass `--bind 0.0.0.0`. Supply the same bind/port options
on subsequent deployments; only the environment file is automatically reused.

Set the hostname and port MCP clients actually use with `--mcp-host`:

```sh
./scripts/deploy.sh argonaut --bind 0.0.0.0 --port 8000 --mcp-host localhost:8000
```

For HTTPS behind a proxy, use its public hostname (for example,
`--mcp-host punctual.example.com`). This option appends to existing
`PUNCTUAL_ALLOWED_HOSTS` and saves `PUNCTUAL_MCP_HOST` for future health checks.
The merged environment is saved only after deployment succeeds. An explicit
`--env-file` still replaces the saved configuration before these additions.

Deployment uses the same checks as [`punctual doctor`](mcp.md#connection-diagnostics),
including authenticated `server/discover` and `tools/list`, before removing the previous container.
Checks run inside the container using the configured external Host header;
they validate application host policy, not external DNS, TLS, proxy routing or
firewall access. Without `--mcp-host` or a saved `PUNCTUAL_MCP_HOST`, checks use
loopback and print a reminder. Run `doctor` from a client machine to verify the
complete network path. A failed check prints sanitized diagnostics and rolls back.

The deployment preserves the `punctual-data` volume and checks the frontend,
health endpoint, and authenticated task API before removing the old container.
If the new container fails to start or become healthy, it restores the previous
container. This involves a short interruption while containers are switched.
Rollback restores the container, **not database migrations**; back up the database
before deploying schema changes that are incompatible with the old application.

Deployments are serialized using `~/.local/share/punctual/deploy.lock`. If a host
crash leaves a stale lock, remove that empty directory after confirming no deploy
is running. Old image tags are retained so they remain available for recovery.

## Backups

Back up a running database using SQLite's backup API, rather than copying only
the `.db` file while WAL writes are active:

For Docker:

```sh
docker exec punctual python -c "import sqlite3; s=sqlite3.connect('/data/punctual.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d); d.close(); s.close()"
docker cp punctual:/data/backup.db ./punctual-backup.db
```

For a local installation, run this from the directory containing the database:

```sh
python -c "import sqlite3; s=sqlite3.connect('punctual.db'); d=sqlite3.connect('backup.db'); s.backup(d); d.close(); s.close()"
```

To restore, stop the server, replace the database with the backup, remove any stale
`-wal`/`-shm` files belonging to the old database, then restart.
