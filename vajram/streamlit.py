import subprocess
import sys
import threading


def _consume_pipe(pipe):
    try:
        while pipe.readable():
            chunk = pipe.read(4096)
            if not chunk:
                break
    except Exception:
        pass


def _start_streamlit() -> subprocess.Popen:
    python = sys.executable or "python"
    proc = subprocess.Popen(  # noqa: S603
        [python, "-m", "streamlit", "run", "my_streamlit_app.py",
         "--server.port", "8501",
         "--server.headless", "true",
         "--server.enableCORS", "false",
         "--server.enableXsrfProtection", "false",
          "--server.address", "127.0.0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    t = threading.Thread(target=_consume_pipe, args=(proc.stdout,), daemon=True)
    t.start()
    return proc
