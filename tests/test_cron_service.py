"""Tests for cron job management service."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from zukuagent.core.cron_service import CronJobService
from zukuagent.core.settings import settings


class _FakeCompletedProcess:
    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def check_returncode(self) -> None:
        if self.returncode != 0:
            raise subprocess.CalledProcessError(self.returncode, "crontab", output=self.stdout, stderr=self.stderr)


@pytest.fixture
def fake_crontab(monkeypatch):
    state = {"lines": [], "writes": []}
    monkeypatch.setattr("zukuagent.core.cron_service.shutil.which", lambda _name: "/usr/bin/crontab")

    def _fake_run(cmd, check=False, capture_output=False, text=False, input=None):
        del check, capture_output, text
        if cmd[1:] == ["-l"]:
            if not state["lines"]:
                return _FakeCompletedProcess(returncode=1, stderr="no crontab for user")
            return _FakeCompletedProcess(returncode=0, stdout="\n".join(state["lines"]) + "\n")
        if cmd[1:] == ["-"]:
            lines = [line for line in (input or "").splitlines() if line.strip()]
            state["lines"] = lines
            state["writes"].append(lines[:])
            return _FakeCompletedProcess(returncode=0)
        msg = f"Unexpected subprocess command: {cmd}"
        raise AssertionError(msg)

    monkeypatch.setattr("zukuagent.core.cron_service.subprocess.run", _fake_run)
    return state


def test_create_agent_job_adds_tagged_crontab_line(tmp_path: Path, monkeypatch, fake_crontab) -> None:
    monkeypatch.setattr(settings, "cron_log_dir", ".zukuagent/cron")
    monkeypatch.setattr(settings, "cron_agent_cli", "zukuagent")
    service = CronJobService(project_root=tmp_path)

    job = service.create_agent_job(schedule="0 9 * * 1-5", message="daily summary", provider="google", model_name="gemini-2.5-flash")

    assert job.job_id
    assert job.mode == "agent"
    assert any(f"zukuagent-cron:{job.job_id}:agent" in line for line in fake_crontab["lines"])
    assert "--message 'daily summary'" in job.raw_line


def test_create_script_job_uses_restricted_sandbox_by_default(tmp_path: Path, monkeypatch, fake_crontab) -> None:
    monkeypatch.setattr(settings, "cron_script_sandbox_mode", "restricted")
    service = CronJobService(project_root=tmp_path)

    job = service.create_script_job(schedule="*/30 * * * *", script_command="/opt/jobs/run.sh", sandbox=None)

    assert job.mode == "script-restricted"
    assert "env -i HOME=$HOME PATH=/usr/bin:/bin /bin/bash -lc /opt/jobs/run.sh" in job.raw_line


def test_list_and_remove_jobs(tmp_path: Path, fake_crontab) -> None:
    service = CronJobService(project_root=tmp_path)
    first = service.create_script_job(schedule="0 * * * *", script_command="/tmp/a.sh", sandbox="none")
    second = service.create_agent_job(schedule="5 * * * *", message="ping", provider="google", model_name="m")

    jobs = service.list_jobs()

    assert {job.job_id for job in jobs} == {first.job_id, second.job_id}
    assert service.remove_job(first.job_id) is True
    assert service.remove_job("missing") is False


def test_create_job_rejects_newline_input(tmp_path: Path, monkeypatch, fake_crontab) -> None:
    monkeypatch.setattr(settings, "cron_log_dir", ".zukuagent/cron")
    monkeypatch.setattr(settings, "cron_agent_cli", "zukuagent")
    service = CronJobService(project_root=tmp_path)

    with pytest.raises(ValueError, match="single line"):
        service.create_agent_job(
            schedule="* * * * *",
            message="ping\n* * * * * /bin/touch /tmp/pwned",
            provider="google",
            model_name="gemini-2.5-flash",
        )

    with pytest.raises(ValueError, match="single line"):
        service.create_script_job(
            schedule="* * * * *",
            script_command="/opt/jobs/run.sh\n* * * * * /bin/touch /tmp/pwned",
            sandbox="none",
        )


def test_create_job_rejects_invalid_schedule(tmp_path: Path, fake_crontab) -> None:
    service = CronJobService(project_root=tmp_path)

    with pytest.raises(ValueError, match="five cron fields"):
        service.create_script_job(schedule="@daily", script_command="/opt/jobs/run.sh", sandbox="restricted")
