"""Validation of a written book with epubcheck, the W3C's EPUB checker (--check).

Optional: `pip install lparchive2epub[check]` brings the epubcheck package, which bundles the Java
program; a Java runtime must be installed. The jar is run directly rather than through the package's
wrapper so that a JVM that fails to start or runs out of memory is reported, not turned into a crash
on empty output.
"""
import json
import shutil
import subprocess
from dataclasses import dataclass

from lparchive2epub.lib import CheckError, ISSUES_URL

# USAGE and INFO messages are advice about style, not findings about the book
FINDING_SEVERITIES = ("FATAL", "ERROR", "WARNING")
# A 900 MB book takes epubcheck a few minutes; past this it is stuck, not slow
CHECK_TIMEOUT = 1800


@dataclass(frozen=True)
class Finding:
    severity: str          # FATAL, ERROR or WARNING
    id: str                # epubcheck's message ID, e.g. RSC-007
    message: str
    path: str | None = None     # the file inside the EPUB, when the message points at one
    line: int | None = None

    @property
    def is_error(self) -> bool:
        return self.severity in ("FATAL", "ERROR")

    def where(self) -> str:
        if not self.path:
            return ""
        return f"{self.path}:{self.line}" if self.line and self.line > 0 else self.path


@dataclass
class CheckResult:
    version: str           # epubcheck's own version
    findings: list[Finding]

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.is_error]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if not f.is_error]


def unavailable_reason() -> str | None:
    """Why --check cannot run here, or None when it can: the epubcheck package or a Java runtime is missing."""
    try:
        from epubcheck import const
    except ImportError:
        return ("--check needs the epubcheck package: pip install lparchive2epub[check] "
                "(a Java runtime is needed as well)")
    if shutil.which(const.JAVA) is None:
        return f"--check needs a Java runtime: '{const.JAVA}' was not found on the PATH"
    return None


def run_epubcheck(path: str) -> CheckResult:
    """Validate the book at `path`. Raises CheckError when epubcheck itself could not run or finish."""
    from epubcheck import const
    command = [const.JAVA, "-Duser.language=en", "-jar", const.EPUBCHECK, path, "-q", "--json", "-"]
    try:
        completed = subprocess.run(command, capture_output=True, timeout=CHECK_TIMEOUT)
    except FileNotFoundError as e:
        raise CheckError(f"The book was written at {path}, but epubcheck could not run: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise CheckError(f"The book was written at {path}, but epubcheck did not finish within {CHECK_TIMEOUT} s") from e
    try:
        data = json.loads(completed.stdout.decode("utf-8"))
    except ValueError as e:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip().splitlines()
        detail = stderr[-1] if stderr else f"exit status {completed.returncode} and no output"
        raise CheckError(f"The book was written at {path}, but epubcheck could not check it: {detail}") from e
    return parse_epubcheck(data)


def parse_epubcheck(data: dict) -> CheckResult:
    """The findings in epubcheck's JSON output (its `messages`, the first location of each)."""
    findings = []
    for m in data.get("messages") or []:
        if m.get("severity") not in FINDING_SEVERITIES:
            continue
        location = (m.get("locations") or [{}])[0]
        findings.append(Finding(m["severity"], m["ID"], m["message"], location.get("path"), location.get("line")))
    version = str((data.get("checker") or {}).get("checkerVersion") or "?")
    return CheckResult(version, findings)


CHECK_HEADER = "lparchive2epub: epubcheck"


def format_check_report(path: str, result: CheckResult, outcome: str) -> str:
    """epubcheck's findings in the style of the failure report, ending with `outcome`. Every finding is
    the tool's doing (the book is built from scratch), so a bug report is always asked for."""
    counts = []
    if result.errors:
        counts.append(f"{len(result.errors)} error(s)")
    if result.warnings:
        counts.append(f"{len(result.warnings)} warning(s)")
    separator = "-" * 72
    lines = [separator, f"{CHECK_HEADER} {result.version} found {' and '.join(counts)} in {path}"]
    for f in result.findings:
        where = f" {f.where()}" if f.where() else ""
        lines.append(f"  - {f.severity} {f.id}{where}: {f.message}")
    lines.append(separator)
    lines.append(outcome)
    lines.append(f"Please open an issue at {ISSUES_URL} and paste the output between the lines above:")
    lines.append("the tool should produce valid books.")
    return "\n".join(lines)

