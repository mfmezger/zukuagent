import json
import sys
import time
from types import SimpleNamespace

import pytest

import zukuagent
from zukuagent.services import sandbox_service
from zukuagent.services.sandbox_service import MontySandboxService


class FakeMonty:
    init_calls = 0

    def __init__(self, code, *, inputs, external_functions, type_check, type_check_stubs):
        FakeMonty.init_calls += 1
        self.code = code
        self.inputs = tuple(inputs)
        self.external_functions = tuple(external_functions)
        self.type_check = type_check
        self.type_check_stubs = type_check_stubs

    def dump(self):
        payload = {
            "code": self.code,
            "inputs": list(self.inputs),
            "external_functions": list(self.external_functions),
            "type_check": self.type_check,
            "type_check_stubs": self.type_check_stubs,
        }
        return json.dumps(payload).encode("utf-8")

    @classmethod
    def load(cls, payload):
        data = json.loads(payload.decode("utf-8"))
        instance = object.__new__(cls)
        instance.code = data["code"]
        instance.inputs = tuple(data["inputs"])
        instance.external_functions = tuple(data["external_functions"])
        instance.type_check = data["type_check"]
        instance.type_check_stubs = data["type_check_stubs"]
        return instance

    def run(self, *, inputs, external_functions):
        if "adder" in external_functions:
            return external_functions["adder"](inputs["x"], inputs["y"])
        return {"code": self.code, "inputs": inputs}


def test_monty_sandbox_executes_code(monkeypatch):
    FakeMonty.init_calls = 0
    monkeypatch.setattr(sandbox_service, "pydantic_monty", SimpleNamespace(Monty=FakeMonty))

    service = MontySandboxService()
    result = service.run_code(
        "adder(x, y)",
        inputs={"x": 1, "y": 2},
        external_functions={"adder": lambda x, y: x + y},
    )

    assert result.output == 3
    assert result.duration_ms >= 0


def test_monty_sandbox_caches_compiled_programs(monkeypatch):
    FakeMonty.init_calls = 0
    monkeypatch.setattr(sandbox_service, "pydantic_monty", SimpleNamespace(Monty=FakeMonty))

    service = MontySandboxService(enforce_limits=False)
    service.run_code("x + y", inputs={"x": 2, "y": 3})
    service.run_code("x + y", inputs={"x": 4, "y": 5})

    assert FakeMonty.init_calls == 1


def test_monty_sandbox_times_out_with_limits(monkeypatch):
    class SlowMonty(FakeMonty):
        def run(self, *, inputs, external_functions):
            _ = (inputs, external_functions)
            time.sleep(0.5)
            return "done"

    monkeypatch.setattr(sandbox_service, "pydantic_monty", SimpleNamespace(Monty=SlowMonty))
    service = MontySandboxService(execution_timeout_seconds=0.1, max_memory_mb=64, enforce_limits=True)

    with pytest.raises(TimeoutError, match="timed out"):
        service.run_code("x + y", inputs={"x": 2, "y": 3})


def test_monty_sandbox_requires_dependency(monkeypatch):
    monkeypatch.setattr(sandbox_service, "pydantic_monty", None)
    service = MontySandboxService()

    with pytest.raises(RuntimeError, match="pydantic-monty"):
        service.run_code("1 + 1")


def test_main_uses_sandbox_without_initializing_agent(monkeypatch, capsys):
    class FakeSandboxService:
        def __init__(self, *, type_check):
            self.type_check = type_check

        def run_code(self, code):
            assert code == "1 + 1"
            return SimpleNamespace(output="2")

    def fail_agent(*_args, **_kwargs):
        msg = "Agent should not initialize for sandbox mode"
        raise AssertionError(msg)

    monkeypatch.setattr(zukuagent, "MontySandboxService", FakeSandboxService)
    monkeypatch.setattr(zukuagent, "ZukuAgent", fail_agent)
    monkeypatch.setattr(sys, "argv", ["zukuagent", "--sandbox-code", "1 + 1"])

    zukuagent.main()
    assert capsys.readouterr().out.strip() == "2"
