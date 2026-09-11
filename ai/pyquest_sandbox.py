"""Small, deliberately restrictive executor for PyQuest student snippets.

This is **not** a general-purpose Python sandbox.  It supports the subset of
Python used in the early PyQuest lessons (variables, ``print``, ``input``,
conditions and bounded ``for ... in range(...)`` loops).  Code runs in a child
process so a timed-out submission can be terminated without stopping Streamlit.

There is intentionally no database code here.  The caller must persist an
attempt/reward only after receiving a verified outcome.
"""

from __future__ import annotations

import ast
import io
import multiprocessing as mp
import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Literal


DEFAULT_TIMEOUT_SECONDS = 1.5
MAX_CODE_CHARACTERS = 8_000
MAX_OUTPUT_CHARACTERS = 4_000
MAX_RANGE_ITEMS = 10_000


class SandboxValidationError(ValueError):
    """Raised internally when code is outside the supported learning subset."""


class _OutputLimitReached(RuntimeError):
    pass


@dataclass(frozen=True)
class SandboxOutcome:
    """A serialisable execution/evaluation result for the application layer."""

    status: Literal["passed", "failed", "blocked", "timeout", "runtime_error"]
    passed: bool
    output: str = ""
    error: str | None = None
    expected_output: str | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RewardDecision:
    """Pure reward calculation; save these values through the caller's database API."""

    verified_first_attempts: int
    coins_awarded: int
    xp_awarded: int
    milestone_reached: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reward_decision(
    *, passed: bool, first_attempt: bool, verified_first_attempts: int
) -> RewardDecision:
    """Award one coin and 30 XP for each third verified correct first attempt.

    ``verified_first_attempts`` is a cumulative persisted count, not a session
    counter.  Failed or later attempts do not increment it.
    """

    count = max(0, int(verified_first_attempts))
    if not (passed and first_attempt):
        return RewardDecision(count, 0, 0, False)
    count += 1
    milestone = count % 3 == 0
    return RewardDecision(count, 1 if milestone else 0, 30 if milestone else 0, milestone)


_ALLOWED_STATEMENTS = (ast.Assign, ast.AnnAssign, ast.Expr, ast.If, ast.For, ast.Pass)
_ALLOWED_EXPRESSIONS = (
    ast.Constant,
    ast.Name,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,
    ast.List,
    ast.Tuple,
)
_SAFE_CALLS = {"print", "input", "int", "float", "str", "bool", "len", "range", "abs", "min", "max"}
_SAFE_OPERATORS = (
    ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)


def _validation_error(message: str) -> SandboxOutcome:
    return SandboxOutcome("blocked", False, error=message)


class _SubsetValidator(ast.NodeVisitor):
    """Reject every AST node except the explicitly supported beginner subset."""

    def visit(self, node: ast.AST) -> Any:  # noqa: ANN401
        if isinstance(node, ast.Module):
            return self.generic_visit(node)
        if isinstance(node, ast.stmt) and not isinstance(node, _ALLOWED_STATEMENTS):
            raise SandboxValidationError(f"{type(node).__name__} is not available in this lesson yet.")
        if isinstance(node, ast.expr) and not isinstance(node, _ALLOWED_EXPRESSIONS):
            raise SandboxValidationError(f"{type(node).__name__} is not available in this lesson yet.")
        if isinstance(node, ast.operator | ast.unaryop | ast.boolop | ast.cmpop):
            if not isinstance(node, _SAFE_OPERATORS):
                raise SandboxValidationError("That operator is not available in this lesson yet.")
        return super().visit(node)

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id.startswith("__"):
            raise SandboxValidationError("Private Python names are not allowed.")
        return None

    def visit_Assign(self, node: ast.Assign) -> Any:
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            raise SandboxValidationError("Use a single variable name on the left side of =.")
        self.visit(node.targets[0])
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        if not isinstance(node.target, ast.Name) or node.value is None:
            raise SandboxValidationError("Use a variable name and a value in an assignment.")
        self.visit(node.target)
        self.visit(node.value)

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_CALLS:
            raise SandboxValidationError("Only the lesson's safe functions can be called.")
        if node.keywords:
            raise SandboxValidationError("Keyword arguments are not available in this lesson yet.")
        for argument in node.args:
            self.visit(argument)

    def visit_For(self, node: ast.For) -> Any:
        if not isinstance(node.target, ast.Name):
            raise SandboxValidationError("Use one loop variable in a for loop.")
        if not (
            isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == "range"
        ):
            raise SandboxValidationError("For loops must use range(...).")
        self.visit(node.target)
        self.visit(node.iter)
        for statement in node.body:
            self.visit(statement)
        if node.orelse:
            raise SandboxValidationError("for/else is not available in this lesson yet.")


class _BoundedOutput(io.StringIO):
    def __init__(self, limit: int) -> None:
        super().__init__()
        self.limit = limit

    def write(self, value: str) -> int:
        if self.tell() + len(value) > self.limit:
            remaining = max(0, self.limit - self.tell())
            if remaining:
                super().write(value[:remaining])
            raise _OutputLimitReached("Output is too long; print less information and try again.")
        return super().write(value)


def _bounded_range(*values: int) -> range:
    if not 1 <= len(values) <= 3:
        raise TypeError("range expects one, two, or three whole numbers")
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        raise TypeError("range values must be whole numbers")
    result = range(*values)
    if len(result) > MAX_RANGE_ITEMS:
        raise ValueError(f"range is limited to {MAX_RANGE_ITEMS} items in PyQuest")
    return result


def _worker(connection: Any, code: str, inputs: tuple[str, ...], output_limit: int) -> None:
    """Child-process entry point.  Keep this top-level for Windows spawn mode."""

    stream = _BoundedOutput(output_limit)
    input_values = iter(inputs)

    def safe_print(*values: Any, sep: str = " ", end: str = "\n") -> None:
        if not isinstance(sep, str) or not isinstance(end, str):
            raise TypeError("print separator and ending must be text")
        stream.write(sep.join(str(value) for value in values) + end)

    def safe_input(prompt: str = "") -> str:
        if prompt:
            safe_print(prompt, end="")
        try:
            return next(input_values)
        except StopIteration as error:
            raise EOFError("No test input was supplied for input().") from error

    safe_builtins = {
        "print": safe_print,
        "input": safe_input,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "len": len,
        "range": _bounded_range,
        "abs": abs,
        "min": min,
        "max": max,
    }
    # The supplied mapping is the entire built-in surface: no import, files,
    # attributes, reflection, networking, or process controls are reachable.
    namespace: dict[str, Any] = {"__builtins__": safe_builtins}
    try:
        compiled = compile(code, "<pyquest-submission>", "exec")
        exec(compiled, namespace, namespace)  # noqa: S102 - validated AST + isolated allowlist
        connection.send({"status": "ok", "output": stream.getvalue(), "error": None})
    except _OutputLimitReached as error:
        connection.send({"status": "runtime_error", "output": stream.getvalue(), "error": str(error)})
    except Exception as error:  # student errors are returned, never raised into Streamlit
        connection.send({"status": "runtime_error", "output": stream.getvalue(), "error": f"{type(error).__name__}: {error}"})
    finally:
        connection.close()


def _normalise_output(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.strip().splitlines())


def run_student_code(
    code: str,
    *,
    inputs: Iterable[str] = (),
    expected_output: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_output_characters: int = MAX_OUTPUT_CHARACTERS,
) -> SandboxOutcome:
    """Validate and run a beginner snippet in a timed child process.

    When ``expected_output`` is provided, a successful execution only passes
    when its normalised output exactly matches that expected output.
    """

    if not isinstance(code, str) or not code.strip():
        return _validation_error("Write some Python code before running it.")
    if len(code) > MAX_CODE_CHARACTERS:
        return _validation_error(f"Code is limited to {MAX_CODE_CHARACTERS} characters.")
    if timeout_seconds <= 0 or timeout_seconds > 10:
        return _validation_error("Choose a timeout between 0 and 10 seconds.")
    if max_output_characters < 1 or max_output_characters > MAX_OUTPUT_CHARACTERS:
        return _validation_error(f"Output limit must be between 1 and {MAX_OUTPUT_CHARACTERS} characters.")

    try:
        tree = ast.parse(code, mode="exec")
        _SubsetValidator().visit(tree)
    except SyntaxError as error:
        return _validation_error(f"Syntax error: {error.msg} (line {error.lineno}).")
    except SandboxValidationError as error:
        return _validation_error(str(error))

    try:
        supplied_inputs = tuple(str(value) for value in inputs)
    except TypeError:
        return _validation_error("Inputs must be an iterable of text values.")

    parent, child = mp.get_context("spawn").Pipe(duplex=False)
    process = mp.get_context("spawn").Process(
        target=_worker, args=(child, code, supplied_inputs, max_output_characters), daemon=True
    )
    started = time.monotonic()
    try:
        process.start()
    except (OSError, RuntimeError) as error:
        parent.close()
        child.close()
        return SandboxOutcome("runtime_error", False, error=f"Sandbox could not start: {error}")
    child.close()
    timeout = float(timeout_seconds)
    if not parent.poll(timeout):
        process.terminate()
        process.join(timeout=0.5)
        parent.close()
        return SandboxOutcome(
            "timeout", False, error=f"Code exceeded the {timeout:g}-second limit.",
            duration_ms=round((time.monotonic() - started) * 1000),
        )

    try:
        payload = parent.recv()
    except EOFError:
        payload = {"status": "runtime_error", "output": "", "error": "Sandbox process ended unexpectedly."}
    finally:
        parent.close()
        process.join(timeout=0.5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=0.5)

    output = str(payload.get("output") or "")
    error = payload.get("error")
    duration_ms = round((time.monotonic() - started) * 1000)
    if payload.get("status") != "ok":
        return SandboxOutcome(
            "runtime_error", False, output=output, error=str(error or "Code could not run."),
            duration_ms=duration_ms,
        )

    if expected_output is not None and _normalise_output(output) != _normalise_output(str(expected_output)):
        return SandboxOutcome(
            "failed", False, output=output,
            error="The output did not match the expected result.", expected_output=str(expected_output),
            duration_ms=duration_ms,
        )
    return SandboxOutcome("passed", True, output=output, expected_output=expected_output, duration_ms=duration_ms)
