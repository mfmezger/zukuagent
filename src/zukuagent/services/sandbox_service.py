"""Sandboxed code execution service backed by pydantic-monty."""

from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Any

try:
    import pydantic_monty
except ImportError:
    pydantic_monty = None


@dataclass
class SandboxExecutionResult:
    """Structured result for sandboxed execution."""

    output: Any
    duration_ms: float


class MontySandboxService:
    """Run Python snippets in a Monty sandbox with cached program compilation."""

    def __init__(self, *, type_check: bool = False, max_cached_programs: int = 64) -> None:
        """Configure sandbox execution defaults."""
        self.type_check = type_check
        self.max_cached_programs = max_cached_programs
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

        runner = pydantic_monty.Monty.load(compiled)
        started = perf_counter()
        output = runner.run(inputs=run_inputs, external_functions=run_external_functions)
        duration_ms = (perf_counter() - started) * 1000

        return SandboxExecutionResult(output=output, duration_ms=duration_ms)

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
