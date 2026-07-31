"""
Starts / stops the user's uploaded program as a REAL background process
(subprocess), with a best-effort resource ceiling so one hosted process
can't take the whole VPS down.
"""
import os
import signal
import subprocess
import resource
import config

_running_procs = {}  # hosting_id -> subprocess.Popen


def _limit_resources(mem_limit_mb: int):
    # runs inside the child process right before exec
    mem_bytes = mem_limit_mb * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        resource.setrlimit(
            resource.RLIMIT_CPU,
            (config.PROCESS_CPU_LIMIT_SEC, config.PROCESS_CPU_LIMIT_SEC),
        )
    except Exception:
        pass  # not fatal - some sandboxes disallow setrlimit
    os.setsid()  # own process group so we can kill it and any children cleanly


def start_process(hosting_id: int, filepath: str, language: str,
                   category: str = "bot", port: int = None, vip: bool = False) -> int:
    workdir = os.path.dirname(filepath)
    log_path = os.path.join(workdir, "run.log")
    log_file = open(log_path, "ab", buffering=0)

    env = os.environ.copy()
    mem_limit = config.VIP_MEM_LIMIT_MB if vip else config.PROCESS_MEM_LIMIT_MB

    if category == "website":
        # static hosting: if it's a zip, it's already been extracted to `workdir`
        # by the caller. Serve that folder over a real HTTP port.
        cmd = ["python3", "-m", "http.server", str(port)]
        cwd = workdir
    else:
        ext = os.path.splitext(filepath)[1]
        runner = config.RUNNERS.get(ext)
        if not runner:
            raise ValueError(f"No runner configured for {ext}")
        cmd = runner + [filepath]
        cwd = workdir
        if category == "api" and port:
            # the user's API script should read this to know which port to bind
            env["PORT"] = str(port)

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=log_file,
        stderr=log_file,
        env=env,
        preexec_fn=lambda: _limit_resources(mem_limit),
    )
    _running_procs[hosting_id] = proc
    return proc.pid


def stop_process(hosting_id: int, pid: int = None):
    proc = _running_procs.pop(hosting_id, None)
    target_pid = proc.pid if proc else pid
    if not target_pid:
        return
    try:
        os.killpg(os.getpgid(target_pid), signal.SIGTERM)
    except ProcessLookupError:
        pass
    except Exception:
        try:
            os.kill(target_pid, signal.SIGTERM)
        except Exception:
            pass


def is_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
