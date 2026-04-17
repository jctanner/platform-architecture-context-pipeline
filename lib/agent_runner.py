"""Claude SDK agent launcher and model utilities.

Three approaches for running agents:

1. **Direct Skill Invocation** (enable_skills=True):
   - Let Claude discover and invoke skills automatically
   - Agent has access to the Skill tool
   - Skills loaded from .claude/skills/ via setting_sources
   - Best for: Simple prompts that don't need heavy templating
   - Example: discover-components, collect-architectures

2. **Templated Prompts** (enable_skills=False, default):
   - Manually extract instructions from SKILL.md
   - Template with runtime data (git metadata, build info, etc.)
   - Full control over prompt construction
   - Best for: Complex workflows needing context injection
   - Example: generate-architecture (injects git, build, kustomize context)

3. **CLI Subprocess** (run_agent_cli):
   - Runs `claude -p` as a subprocess instead of using the SDK
   - Uses --dangerously-skip-permissions for full permission inheritance
   - Sub-agents spawned by the Task tool inherit permissions automatically
   - Best for: Skills that use Task tool for multi-reviewer consensus
   - Example: discover-components with --use-cli

Approaches 1 and 2 use run_agent(). Approach 3 uses run_agent_cli().
"""

import json
import shutil
import time
import asyncio
from pathlib import Path

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions


def get_model_display_name(model_shorthand: str) -> str:
    """
    Convert model shorthand to human-readable display name for generated files.

    Args:
        model_shorthand: Short name (sonnet, opus, haiku)

    Returns:
        Human-readable model name
    """
    display_names = {
        "sonnet": "Claude Sonnet 4.5",
        "opus": "Claude Opus 4.6",
        "haiku": "Claude Haiku 3.5",
    }
    return display_names.get(model_shorthand, model_shorthand)


def get_model_id(model_shorthand: str) -> str:
    """
    Convert model shorthand to full model ID.

    Args:
        model_shorthand: Short name (sonnet, opus, haiku)

    Returns:
        Full model ID string
    """
    # Model IDs without date suffixes -- the SDK resolves to the latest version
    model_mapping = {
        "sonnet": "claude-sonnet-4-5",
        "opus": "claude-opus-4-6",
        "haiku": "claude-haiku-3-5",
    }

    return model_mapping.get(model_shorthand, model_shorthand)


def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


async def run_agent(
    job: dict,
    log_dir: Path,
    model: str = "sonnet",
    enable_skills: bool = False
) -> dict:
    """
    Launch one independent Claude agent session.

    Args:
        job: Dict with 'name', 'cwd', 'prompt' keys
        log_dir: Directory to write log files
        model: Claude model to use (sonnet, opus, or haiku)
        enable_skills: If True, enable Skill tool and load skills from filesystem

    Returns:
        dict with 'name', 'success', 'log_file', and optional 'error' keys
    """
    name = job["name"]
    cwd = job["cwd"]
    prompt = job["prompt"]

    # Create log file for this agent
    log_file = log_dir / f"{name.replace('/', '_')}.log"

    # Convert shorthand to full model ID
    model_id = get_model_id(model)

    # Base allowed tools
    allowed_tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]

    # Add Skill tool if skills are enabled
    if enable_skills:
        allowed_tools.append("Skill")

    options = ClaudeAgentOptions(
        cwd=cwd,
        allowed_tools=allowed_tools,
        permission_mode="bypassPermissions",
        model=model_id,
        # Enable Skills loading from filesystem if requested
        setting_sources=["user", "project"] if enable_skills else None,
        # No max_turns - let agent run as long as needed for thorough analysis
    )

    print(f"\n{'=' * 60}")
    print(f"Starting agent: {name}")
    print(f"Model: {model}")
    print(f"Working directory: {cwd}")
    print(f"Log file: {log_file}")
    print(f"{'=' * 60}")

    # Write log header before try block so error handler always has context
    with open(log_file, 'w') as log:
        log.write(f"Agent: {name}\n")
        log.write(f"Model: {model}\n")
        log.write(f"Working directory: {cwd}\n")
        log.write(f"{'=' * 60}\n\n")
        log.write("PROMPT:\n")
        log.write(prompt)
        log.write(f"\n\n{'=' * 60}\n")
        log.write("AGENT OUTPUT:\n\n")

    start_time = time.monotonic()
    last_activity = start_time

    async def _heartbeat():
        """Print periodic status while the agent is working silently."""
        nonlocal last_activity
        while True:
            await asyncio.sleep(30)
            silence = time.monotonic() - last_activity
            elapsed = time.monotonic() - start_time
            if silence >= 30:
                print(f"[{name}] ... still running ({format_duration(elapsed)} elapsed)")

    heartbeat_task = asyncio.create_task(_heartbeat())

    try:
        with open(log_file, 'a') as log:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)

                async for msg in client.receive_response():
                    last_activity = time.monotonic()
                    # Print to console with component name prefix
                    print(f"[{name}] {msg}")
                    # Also write to log file
                    log.write(f"{msg}\n")
                    log.flush()

        elapsed = time.monotonic() - start_time

        print(f"\n{'=' * 60}")
        print(f"Completed: {name} ({format_duration(elapsed)})")
        print(f"{'=' * 60}")

        return {"name": name, "success": True, "log_file": str(log_file), "duration_seconds": elapsed}

    except Exception as e:
        elapsed = time.monotonic() - start_time

        print(f"\n{'=' * 60}")
        print(f"Failed: {name} ({format_duration(elapsed)})")
        print(f"Error: {e}")
        print(f"{'=' * 60}")

        # Log the error (header already written, so context is preserved)
        with open(log_file, 'a') as log:
            log.write(f"\n\n{'=' * 60}\n")
            log.write(f"ERROR: {e}\n")

        return {"name": name, "success": False, "error": str(e), "log_file": str(log_file), "duration_seconds": elapsed}

    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


async def run_agent_cli(
    job: dict,
    log_dir: Path,
    model: str = "sonnet",
) -> dict:
    """
    Launch a Claude agent session via `claude -p` subprocess.

    Uses the Claude CLI directly instead of the SDK. This enables full Task
    tool support — sub-agents spawned by the Task tool inherit the
    --dangerously-skip-permissions flag, which the SDK's bypassPermissions
    mode does NOT propagate.

    Args:
        job: Dict with 'name', 'cwd', 'prompt' keys
        log_dir: Directory to write log files
        model: Claude model to use (sonnet, opus, or haiku)

    Returns:
        dict with 'name', 'success', 'log_file', and optional 'error' keys
    """
    name = job["name"]
    cwd = job["cwd"]
    prompt = job["prompt"]

    log_file = log_dir / f"{name.replace('/', '_')}.log"

    # Find the claude binary
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return {
            "name": name,
            "success": False,
            "error": "claude CLI not found in PATH",
            "log_file": str(log_file),
            "duration_seconds": 0,
        }

    cmd = [
        claude_bin,
        "--model", model,
        "--print",
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--verbose",
        prompt,
    ]

    print(f"\n{'=' * 60}")
    print(f"Starting agent (CLI mode): {name}")
    print(f"Model: {model}")
    print(f"Working directory: {cwd}")
    print(f"Log file: {log_file}")
    print(f"{'=' * 60}")

    # Write log header
    with open(log_file, 'w') as log:
        log.write(f"Agent: {name}\n")
        log.write(f"Model: {model}\n")
        log.write(f"Mode: CLI subprocess (claude -p)\n")
        log.write(f"Working directory: {cwd}\n")
        log.write(f"{'=' * 60}\n\n")
        log.write("PROMPT:\n")
        log.write(prompt)
        log.write(f"\n\n{'=' * 60}\n")
        log.write("AGENT OUTPUT:\n\n")

    start_time = time.monotonic()
    last_activity = start_time

    async def _heartbeat():
        nonlocal last_activity
        while True:
            await asyncio.sleep(30)
            silence = time.monotonic() - last_activity
            elapsed = time.monotonic() - start_time
            if silence >= 30:
                print(f"[{name}] ... still running ({format_duration(elapsed)} elapsed)")

    heartbeat_task = asyncio.create_task(_heartbeat())

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        with open(log_file, 'a') as log:
            # Process stream-json lines from stdout
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break

                last_activity = time.monotonic()
                line_str = line.decode('utf-8', errors='replace').rstrip()

                if not line_str:
                    continue

                # Parse stream-json events for readable console output
                try:
                    msg = json.loads(line_str)
                    msg_type = msg.get("type")

                    if msg_type == "stream_event":
                        event = msg.get("event", {})
                        event_type = event.get("type")

                        if event_type == "content_block_start":
                            block = event.get("content_block", {})
                            block_type = block.get("type")
                            if block_type == "tool_use":
                                tool_name = block.get("name", "?")
                                print(f"[{name}] tool: {tool_name}")
                                log.write(f"[tool_use] {tool_name}\n")

                        elif event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            delta_type = delta.get("type")
                            if delta_type == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    log.write(text)

                    elif msg_type == "system":
                        subtype = msg.get("subtype", "")
                        if subtype == "task_started":
                            task_desc = msg.get("description", "sub-agent")
                            print(f"[{name}] sub-agent started: {task_desc}")
                            log.write(f"[sub-agent started] {task_desc}\n")
                        elif subtype == "task_notification":
                            status = msg.get("status", "?")
                            print(f"[{name}] sub-agent {status}")
                            log.write(f"[sub-agent {status}]\n")

                    elif msg_type == "result":
                        log.write(f"\n[result] {line_str}\n")

                except (json.JSONDecodeError, ValueError):
                    # Non-JSON output, log as-is
                    log.write(f"{line_str}\n")

                log.flush()

        # Wait for process to finish
        await proc.wait()

        # Capture stderr
        stderr_bytes = await proc.stderr.read()
        stderr_str = stderr_bytes.decode('utf-8', errors='replace').strip()
        if stderr_str:
            with open(log_file, 'a') as log:
                log.write(f"\n{'=' * 60}\n")
                log.write(f"STDERR:\n{stderr_str}\n")

        elapsed = time.monotonic() - start_time
        success = proc.returncode == 0

        print(f"\n{'=' * 60}")
        status = "Completed" if success else "Failed"
        print(f"{status}: {name} ({format_duration(elapsed)}, exit={proc.returncode})")
        print(f"{'=' * 60}")

        result = {
            "name": name,
            "success": success,
            "log_file": str(log_file),
            "duration_seconds": elapsed,
        }
        if not success:
            result["error"] = f"claude exited with code {proc.returncode}"
            if stderr_str:
                result["error"] += f": {stderr_str[:500]}"
        return result

    except Exception as e:
        elapsed = time.monotonic() - start_time

        print(f"\n{'=' * 60}")
        print(f"Failed: {name} ({format_duration(elapsed)})")
        print(f"Error: {e}")
        print(f"{'=' * 60}")

        with open(log_file, 'a') as log:
            log.write(f"\n\n{'=' * 60}\n")
            log.write(f"ERROR: {e}\n")

        return {
            "name": name,
            "success": False,
            "error": str(e),
            "log_file": str(log_file),
            "duration_seconds": elapsed,
        }

    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


async def run_agents_concurrently(
    jobs: list,
    log_dir: Path,
    model: str,
    max_concurrent: int,
    enable_skills: bool = False,
) -> list:
    """
    Run multiple agent jobs with a concurrency limit.

    Logs queue position and slot acquisition so the user can see what's
    happening when agents are waiting for a slot.

    Args:
        jobs: List of dicts with 'name', 'cwd', 'prompt' keys
        log_dir: Directory for agent log files
        model: Model shorthand (sonnet, opus, haiku)
        max_concurrent: Max agents running at once
        enable_skills: If True, enable Skill tool and load skills from filesystem

    Returns:
        List of result dicts (or Exceptions) in the same order as jobs
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    total = len(jobs)

    async def _run(index: int, job: dict):
        if semaphore.locked():
            print(f"[{job['name']}] queued ({index + 1}/{total}), "
                  f"waiting for slot ...")
        async with semaphore:
            return await run_agent(job, log_dir, model, enable_skills)

    print("Starting agent execution...\n")
    return await asyncio.gather(
        *(_run(i, job) for i, job in enumerate(jobs)),
        return_exceptions=True,
    )
