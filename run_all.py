import os
import sys
import subprocess
import time
import signal
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent.resolve()
FRONTEND_DIR = BASE_DIR / "frontend"

def main():
    print("=" * 65)
    print("Starting Kash AI Application (FastAPI Backend + React Frontend)")
    print("=" * 65)

    python_executable = sys.executable

    # 1. Start FastAPI Backend (Port 8000)
    print("\n[1/2] Launching FastAPI Backend on http://localhost:8000 ...")
    backend_cmd = [
        python_executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ]
    
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(BASE_DIR),
        stdout=None,
        stderr=None,
    )

    # Wait for FastAPI backend to be ready
    import socket
    print("Waiting for FastAPI backend to initialize...")
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.5)
    print("Backend is ready!")

    # 2. Start React Vite Frontend (Port 5173)
    print("\n[2/2] Launching ReactJS Frontend on http://localhost:5173 ...")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    frontend_cmd = [npm_cmd, "run", "dev"]

    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(FRONTEND_DIR),
        stdout=None,
        stderr=None,
    )

    print("\n" + "=" * 65)
    print("[OK] Kash AI System Running Successfully!")
    print("=" * 65)
    print("  * React Frontend Dashboard:    http://localhost:5173")
    print("  * AI Prescription OCR Reader:  http://localhost:5173/ocr-decoder")
    print("  * Voice Agent Consultation:    http://localhost:8000/consultation/voice")
    print("  * FastAPI API Documentation:   http://localhost:8000/docs")
    print("=" * 65)
    print("\nPress Ctrl+C to stop all servers.\n")

    def signal_handler(sig, frame):
        print("\nShutting down servers...")
        try:
            frontend_proc.terminate()
            backend_proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        while True:
            time.sleep(1)
            # Check if any process unexpectedly died
            if backend_proc.poll() is not None:
                print("Backend process terminated unexpectedly.")
                frontend_proc.terminate()
                break
            if frontend_proc.poll() is not None:
                print("Frontend process terminated unexpectedly.")
                backend_proc.terminate()
                break
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
