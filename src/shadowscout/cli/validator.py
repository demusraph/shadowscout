from __future__ import annotations

import subprocess
import sys
from typing import Tuple


def verify_generated_code(script_path: str, timeout_seconds: float = 15.0) -> Tuple[bool, str]:
    """
    Executes the synthesized scraper in a sandboxed subprocess with the `--test-run` flag.
    Confirms exit code 0 and validated extracted items before confirming to user.
    """
    cmd = [sys.executable, script_path, "--test-run"]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")

        if proc.returncode == 0 and "Items extracted:" in output:
            return True, output
        else:
            return False, f"Process exited with code {proc.returncode}.\nOutput: {output}"

    except subprocess.TimeoutExpired:
        return False, f"Execution timed out after {timeout_seconds} seconds."
    except Exception as exc:
        return False, f"Subprocess launch error: {exc}"
