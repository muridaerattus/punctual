"""Exercise remote deployment transitions without an SSH host or Docker daemon."""

import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/deploy-remote.sh"


@pytest.fixture
def deployment(tmp_path):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    docker = binaries / "docker"
    docker.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
path = Path(os.environ['DOCKER_STATE'])
state = json.loads(path.read_text())
args = sys.argv[1:]
exit_code = 0
if args[:2] == ['container', 'inspect']:
    exit_code = 0 if args[2] in state else 1
elif args[0] == 'inspect':
    print('true' if state[args[-1]]['running'] else 'false')
elif args[0] == 'build':
    exit_code = 1 if os.environ.get('FAIL_BUILD') else 0
elif args[0] == 'rename':
    state[args[2]] = state.pop(args[1])
elif args[0] == 'stop':
    state[args[1]]['running'] = False
elif args[0] == 'start':
    state[args[1]]['running'] = True
elif args[0] == 'run':
    if os.environ.get('FAIL_RUN'):
        exit_code = 1
    else:
        state['punctual'] = {'running': True, 'image': args[-1]}
elif args[0] == 'exec':
    exit_code = 1 if os.environ.get('FAIL_HEALTH') else 0
elif args[0] == 'rm':
    state.pop(args[-1], None)
path.write_text(json.dumps(state))
sys.exit(exit_code)
""")
    docker.chmod(0o755)
    sleep = binaries / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    state = tmp_path / "docker.json"
    state.write_text("{}")
    env = {
        **os.environ,
        "HOME": str(home),
        "DOCKER_STATE": str(state),
        "PATH": f"{binaries}:{os.environ['PATH']}",
    }

    def deploy(mcp_host="", **overrides):
        stage = tmp_path / f"stage-{len(list(tmp_path.glob('stage-*')))}"
        stage.mkdir()
        with tarfile.open(stage / "source.tar.gz", "w:gz"):
            pass
        return subprocess.run(
            ["bash", str(SCRIPT), str(stage), "127.0.0.1", "8000", mcp_host],
            env={**env, **overrides},
            check=False,
            text=True,
            capture_output=True,
        )

    return deploy, home / ".local/share/punctual", state


def test_first_deploy_and_update_preserve_key(deployment):
    deploy, config, state = deployment
    first = deploy()
    assert first.returncode == 0, first.stderr
    key = (config / "server.env").read_text()
    assert key.startswith("PUNCTUAL_API_KEY=")
    assert (config / "server.env").stat().st_mode & 0o777 == 0o600
    second = deploy()
    assert second.returncode == 0, second.stderr
    assert (config / "server.env").read_text() == key
    assert set(json.loads(state.read_text())) == {"punctual"}
    assert not (config / "deploy.lock").exists()


@pytest.mark.parametrize("failure", ["FAIL_BUILD", "FAIL_RUN", "FAIL_HEALTH"])
def test_failed_deployment_preserves_previous_container(deployment, failure):
    deploy, config, state = deployment
    assert deploy().returncode == 0
    previous = json.loads(state.read_text())
    key = (config / "server.env").read_text()
    result = deploy(**{failure: "1"})
    assert result.returncode != 0
    assert json.loads(state.read_text()) == previous
    assert (config / "server.env").read_text() == key
    assert not (config / "deploy.lock").exists()


def test_deployment_lock_blocks_parallel_updates(deployment):
    deploy, config, state = deployment
    config.mkdir(parents=True)
    (config / "deploy.lock").mkdir()
    result = deploy()
    assert result.returncode != 0
    assert "Another deployment" in result.stderr
    assert json.loads(state.read_text()) == {}
    assert (config / "deploy.lock").exists()


def test_mcp_host_is_appended_persisted_and_rolled_back(deployment):
    deploy, config, _ = deployment
    assert deploy(mcp_host="existing.example").returncode == 0
    original = (config / "server.env").read_text()
    assert deploy(mcp_host="localhost:8000", FAIL_HEALTH="1").returncode != 0
    assert (config / "server.env").read_text() == original
    assert deploy(mcp_host="localhost:8000").returncode == 0
    saved = (config / "server.env").read_text()
    assert "PUNCTUAL_ALLOWED_HOSTS=existing.example,localhost:8000\n" in saved
    assert "PUNCTUAL_MCP_HOST=localhost:8000\n" in saved
    assert deploy(mcp_host="localhost:8000").returncode == 0
    assert (config / "server.env").read_text().count("localhost:8000") == 2
    saved = (config / "server.env").read_text()
    assert deploy().returncode == 0
    assert (config / "server.env").read_text() == saved


def test_upload_wrapper_packages_source_and_quotes_remote_arguments(tmp_path):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    ssh = binaries / "ssh"
    ssh.write_text("""#!/usr/bin/env python3
import os, sys
from pathlib import Path
command = sys.argv[-1]
with Path(os.environ['SSH_LOG']).open('a') as log:
    log.write(command + '\\n')
if command.startswith('mktemp '):
    print('/tmp/punctual-deploy.TEST1234')
""")
    ssh.chmod(0o755)
    scp = binaries / "scp"
    scp.write_text("""#!/usr/bin/env python3
import os, sys, tarfile
from pathlib import Path
for argument in sys.argv[1:]:
    if argument.endswith('source.tar.gz'):
        with tarfile.open(argument) as archive:
            Path(os.environ['ARCHIVE_LOG']).write_text('\\n'.join(archive.getnames()))
""")
    scp.chmod(0o755)
    log = tmp_path / "ssh.log"
    archive = tmp_path / "archive.log"
    result = subprocess.run(
        [
            "bash",
            str(SCRIPT.with_name("deploy.sh")),
            "deploy@example.com",
            "--bind",
            "[::1]",
            "--mcp-host",
            "localhost:8000",
        ],
        env={
            **os.environ,
            "PATH": f"{binaries}:{os.environ['PATH']}",
            "SSH_LOG": str(log),
            "ARCHIVE_LOG": str(archive),
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    names = archive.read_text().splitlines()
    assert "Dockerfile" in names
    assert "backend/punctual/app.py" in names
    assert "frontend/src/app/App.svelte" in names
    assert not any("node_modules" in name or ".venv" in name for name in names)
    assert any(
        line.startswith("bash /tmp/punctual-deploy.TEST1234/deploy-remote.sh")
        for line in log.read_text().splitlines()
    )
    assert "rm -rf -- '/tmp/punctual-deploy.TEST1234'" in log.read_text()
    assert "localhost:8000" in log.read_text()
