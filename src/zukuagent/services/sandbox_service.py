"""Sandboxed code execution service backed by pydantic-monty."""

import math
import multiprocessing
from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Any

try:
    import pydantic_monty
except ImportError:
    pydantic_monty = None

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore[assignment]


@dataclass
class SandboxExecutionResult:
    """Structured result for sandboxed execution."""

    output: Any
    duration_ms: float


class MontySandboxService:
    """Run Python snippets in a Monty sandbox with cached program compilation."""

    def __init__(
        self,
        *,
        type_check: bool = False,
        max_cached_programs: int = 64,
        execution_timeout_seconds: float = 2.0,
        max_memory_mb: int = 256,
        enforce_limits: bool = True,
    ) -> None:
        """Configure sandbox execution defaults."""
        self.type_check = type_check
        self.max_cached_programs = max_cached_programs
        self.execution_timeout_seconds = execution_timeout_seconds
        self.max_memory_mb = max_memory_mb
        self.enforce_limits = enforce_limits
        self._build_cached_program = lru_cache(maxsize=max_cached_programs)(self._build_program)

    def run_code(
        self,
        code: str,
        *,
        inputs: dict[str, Any] | None = None,
        external_functions: dict[str, Any] | None = None,
        type_check_stubs: str | None = None,
    ) -> SandboxExecutionResult:
        """Execute code in a sandbox and return output + duration."""
        if pydantic_monty is None:
            msg = "pydantic-monty is not installed. Install it with: uv add pydantic-monty"
            raise RuntimeError(msg)

        program = code.strip()
        if not program:
            msg = "Sandbox code cannot be empty."
            raise ValueError(msg)

        run_inputs = inputs or {}
        run_external_functions = external_functions or {}
        input_names = tuple(sorted(run_inputs))
        external_function_names = tuple(sorted(run_external_functions))
        compiled = self._build_cached_program(program, input_names, external_function_names, type_check_stubs or "")

        started = perf_counter()
        if self.enforce_limits and not run_external_functions:
            output = self._run_with_limits(compiled, run_inputs)
        else:
            output = self._run_compiled_program(compiled, run_inputs, run_external_functions)
        duration_ms = (perf_counter() - started) * 1000

        return SandboxExecutionResult(output=output, duration_ms=duration_ms)

    def _run_with_limits(self, compiled: bytes, run_inputs: dict[str, Any]) -> object:
        """Execute compiled code in an isolated child process with timeout/resource limits."""
        start_methods = multiprocessing.get_all_start_methods()
        start_method = "fork" if "fork" in start_methods else "spawn"
        context = multiprocessing.get_context(start_method)
        result_queue = context.Queue(maxsize=1)
        process = context.Process(
            target=self._sandbox_worker,
            args=(compiled, run_inputs, self.max_memory_mb, self.execution_timeout_seconds, result_queue),
            daemon=True,
        )
        process.start()
        process.join(self.execution_timeout_seconds)

        if process.is_alive():
            process.terminate()
            process.join()
            msg = f"Sandbox execution timed out after {self.execution_timeout_seconds:.2f}s"
            raise TimeoutError(msg)

        if not result_queue.empty():
            status, payload = result_queue.get()
            if status == "ok":
                return payload
            msg = f"Sandbox execution failed: {payload}"
            raise RuntimeError(msg)

        msg = "Sandbox execution failed without returning output."
        raise RuntimeError(msg)

    @staticmethod
    def _sandbox_worker(
        compiled: bytes,
        run_inputs: dict[str, Any],
        max_memory_mb: int,
        execution_timeout_seconds: float,
        result_queue: object,
    ) -> None:
        """Child process entrypoint that enforces memory/CPU bounds before execution."""
        if resource is not None:
            memory_limit_bytes = max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
            cpu_limit_seconds = max(1, math.ceil(execution_timeout_seconds))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit_seconds, cpu_limit_seconds))

        try:
            output = MontySandboxService._run_compiled_program(compiled, run_inputs, {})
            safe_output = output if isinstance(output, str | int | float | bool | type(None) | list | dict | tuple) else repr(output)
            result_queue.put(("ok", safe_output))
        except Exception as exc:
            result_queue.put(("error", f"{type(exc).__name__}: {exc}"))

    @staticmethod
    def _run_compiled_program(compiled: bytes, run_inputs: dict[str, Any], run_external_functions: dict[str, Any]) -> object:
        """Load compiled program and execute it with provided inputs/functions."""
        runner = pydantic_monty.Monty.load(compiled)
        return runner.run(inputs=run_inputs, external_functions=run_external_functions)

    def _build_program(
        self,
        code: str,
        input_names: tuple[str, ...],
        external_function_names: tuple[str, ...],
        type_check_stubs: str,
    ) -> bytes:
        """Build and serialize a Monty program so repeats can be loaded quickly."""
        program = pydantic_monty.Monty(
            code,
            inputs=input_names,
            external_functions=external_function_names,
            type_check=self.type_check,
            type_check_stubs=type_check_stubs or None,
        )
        return program.dump()
