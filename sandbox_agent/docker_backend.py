"""Small Docker sandbox. Run from Linux/WSL with Docker Desktop available."""
import os
from pathlib import Path
import subprocess
from uuid import uuid4

from deepagents.backends.sandbox import BaseSandbox
from deepagents.backends.protocol import (
    ExecuteResponse, FileDownloadResponse, FileUploadResponse,
)


class DockerSandbox(BaseSandbox):
    def __init__(self, workspace: Path, image: str = "python:3.13-slim"):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.image = image
        self._id = f"coding-agent-{uuid4().hex[:12]}"

    @property
    def id(self) -> str:
        return self._id

    def __enter__(self):
        try:
            subprocess.run([
                "docker", "run", "--detach", "--rm", "--name", self.id,
                "--user", f"{os.getuid()}:{os.getgid()}",
                "--cap-drop=ALL", "--security-opt=no-new-privileges",
                "--memory=1g", "--cpus=2", "--pids-limit=128",
                "--mount", f"type=bind,source={self.workspace},target=/workspace",
                "--workdir", "/workspace",
                "--env", "HOME=/tmp/agent",
                "--env", "TMPDIR=/tmp/agent",
                "--env", "PYTHONUNBUFFERED=1",
                "--env", "PATH=/tmp/agent/.local/bin:/usr/local/bin:/usr/bin:/bin",
                self.image, "sleep", "infinity",
            ], check=True, capture_output=True, text=True, timeout=180)
            result = self.execute("mkdir -p /tmp/agent")
            if result.exit_code != 0:
                raise RuntimeError(result.output)
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        # Remove only the uniquely named container owned by this instance.
        subprocess.run(["docker", "rm", "--force", self.id],
                       capture_output=True, timeout=30)

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        seconds = 120 if timeout is None else max(1, timeout)
        # timeout runs inside Docker, so timed-out commands are stopped there too.
        result = subprocess.run([
            "docker", "exec", self.id, "timeout", "--kill-after=2s",
            f"{seconds}s", "sh", "-c", command,
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
           timeout=seconds + 15)
        output = result.stdout.decode("utf-8", errors="replace")
        limit = 30000
        return ExecuteResponse(
            output=output[:limit], exit_code=result.returncode,
            truncated=len(output) > limit,
        )

    def _transfer(self, path: str, content: bytes | None = None):
        # Paths are passed as arguments, never interpolated into shell commands.
        script = """
import pathlib, sys
try:
    p = pathlib.Path(sys.argv[1])
    if sys.argv[2] == 'upload':
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(sys.stdin.buffer.read())
    else:
        sys.stdout.buffer.write(p.read_bytes())
except FileNotFoundError:
    sys.exit(2)
except PermissionError:
    sys.exit(3)
except IsADirectoryError:
    sys.exit(4)
except (ValueError, NotADirectoryError):
    sys.exit(5)
"""
        result = subprocess.run([
            "docker", "exec", "--interactive", self.id, "python", "-c",
            script, path, "download" if content is None else "upload",
        ], input=content, capture_output=True, timeout=30)
        error = {0: None, 2: "file_not_found", 3: "permission_denied",
                 4: "is_directory", 5: "invalid_path"}.get(
            result.returncode, result.stderr.decode("utf-8", errors="replace")
            or "Docker file transfer failed",
        )
        return result.stdout, error

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses = []
        for path, content in files:
            try:
                _, error = self._transfer(path, content)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                error = str(exc)
            responses.append(FileUploadResponse(path=path, error=error))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses = []
        for path in paths:
            try:
                content, error = self._transfer(path)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                content, error = None, str(exc)
            responses.append(FileDownloadResponse(
                path=path, content=content if error is None else None, error=error,
            ))
        return responses
