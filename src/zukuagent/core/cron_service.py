"""Cron job management for ZukuAgent tool commands."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from zukuagent.core.settings import settings

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class CronJob:
    """Tracked cron job metadata parsed from crontab entries."""

    job_id: str
    schedule: str
    mode: str
    command: str
    raw_line: str


class CronJobService:
    """Create, list, and remove ZukuAgent-managed cron jobs."""

    _TAG_PATTERN = re.compile(r"\s+#\s+zukuagent-cron:(?P<job_id>[a-z0-9]+):(?P<mode>[a-z-]+)$")

    def __init__(self, *, project_root: Path) -> None:
        """Initialize cron service with project-root scoped paths."""
        crontab_bin = shutil.which("crontab")
        if not crontab_bin:
            msg = "`crontab` executable was not found on PATH."
            raise RuntimeError(msg)

        self.crontab_bin = crontab_bin
        self.project_root = project_root
        self.log_dir = self.project_root / settings.cron_log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def create_agent_job(self, *, schedule: str, message: str, provider: str, model_name: str) -> CronJob:
        """Create a cron line that invokes ZukuAgent with a message."""
        job_id = uuid.uuid4().hex[:12]
        log_file = self.log_dir / f"{job_id}.log"
        quoted_message = shlex.quote(message)
        provider_part = f"--provider {shlex.quote(provider)}" if provider else ""
        model_part = f"--model {shlex.quote(model_name)}" if model_name else ""
        command = (
            f"cd {shlex.quote(str(self.project_root))} && "
            f"{settings.cron_agent_cli} --endpoint cli {provider_part} {model_part} --message {quoted_message} "
            f">> {shlex.quote(str(log_file))} 2>&1"
        )
        command = " ".join(command.split())
        line = self._build_line(schedule=schedule, command=command, job_id=job_id, mode="agent")
        self._append_line(line)
        return CronJob(job_id=job_id, schedule=schedule, mode="agent", command=command, raw_line=line)

    def create_script_job(self, *, schedule: str, script_command: str, sandbox: str | None) -> CronJob:
        """Create a cron line that executes a script command."""
        job_id = uuid.uuid4().hex[:12]
        log_file = self.log_dir / f"{job_id}.log"
        selected_sandbox = (sandbox or settings.cron_script_sandbox_mode).lower()
        inner_command = self._build_script_command(script_command=script_command, sandbox=selected_sandbox)
        command = f"{inner_command} >> {shlex.quote(str(log_file))} 2>&1"
        line = self._build_line(schedule=schedule, command=command, job_id=job_id, mode=f"script-{selected_sandbox}")
        self._append_line(line)
        return CronJob(job_id=job_id, schedule=schedule, mode=f"script-{selected_sandbox}", command=command, raw_line=line)

    def list_jobs(self) -> list[CronJob]:
        """List all ZukuAgent-managed cron jobs."""
        jobs: list[CronJob] = []
        for line in self._read_crontab_lines():
            match = self._TAG_PATTERN.search(line)
            if not match:
                continue
            content = line[: match.start()].rstrip()
            parts = content.split(None, 5)
            if len(parts) < 6:
                continue
            schedule = " ".join(parts[:5])
            command = parts[5]
            jobs.append(
                CronJob(
                    job_id=match.group("job_id"),
                    schedule=schedule,
                    mode=match.group("mode"),
                    command=command,
                    raw_line=line,
                )
            )
        return jobs

    def remove_job(self, job_id: str) -> bool:
        """Remove a managed cron job by ID."""
        lines = self._read_crontab_lines()
        needle = f"zukuagent-cron:{job_id}:"
        new_lines = [line for line in lines if needle not in line]
        if len(new_lines) == len(lines):
            return False
        self._write_crontab_lines(new_lines)
        return True

    def _build_script_command(self, *, script_command: str, sandbox: str) -> str:
        quoted_script = shlex.quote(script_command)
        if sandbox == "none":
            return f"/bin/bash -lc {quoted_script}"
        if sandbox == "monty":
            inner = f"/bin/bash -lc {quoted_script}"
            escaped = shlex.quote(inner)
            return settings.cron_monty_template.format(command=escaped)
        if sandbox == "restricted":
            restricted = f"PATH=/usr/bin:/bin /bin/bash -lc {quoted_script}"
            return f"env -i HOME=$HOME {restricted}"
        msg = f"Unsupported sandbox mode: {sandbox}. Use one of: restricted, monty, none."
        raise ValueError(msg)

    def _build_line(self, *, schedule: str, command: str, job_id: str, mode: str) -> str:
        return f"{schedule} {command} # zukuagent-cron:{job_id}:{mode}"

    def _append_line(self, line: str) -> None:
        lines = self._read_crontab_lines()
        lines.append(line)
        self._write_crontab_lines(lines)

    def _read_crontab_lines(self) -> list[str]:
        result = self._run_crontab("-l", check=False)
        if result.returncode != 0:
            stderr = (result.stderr or "").lower()
            if "no crontab" in stderr:
                return []
            result.check_returncode()
        content = result.stdout or ""
        return [line for line in content.splitlines() if line.strip()]

    def _write_crontab_lines(self, lines: list[str]) -> None:
        payload = "\n".join(lines) + ("\n" if lines else "")
        self._run_crontab("-", check=True, input_text=payload)

    def _run_crontab(self, *args: str, check: bool, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.crontab_bin, *args],
            check=check,
            input=input_text,
            text=True,
            capture_output=True,
        )
