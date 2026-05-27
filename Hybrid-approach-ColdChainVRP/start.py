import subprocess
import time
import webbrowser
import os
import sys

def main():
    print("Starting Quantum VRP Dashboard Pipeline...")
    
    # Path to frontend
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
    
    # 1. Start Flask Server (Backend)
    print("Starting Flask Backend...")
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
    
    venv_python = os.path.join(backend_dir, 'venv', 'Scripts', 'python.exe')
    if not os.path.exists(venv_python):
        venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv', 'Scripts', 'python.exe')
    if not os.path.exists(venv_python):
        venv_python = sys.executable
        
    backend = subprocess.Popen(
        [venv_python, "server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=backend_dir
    )
    
    # Wait for flask to start
    time.sleep(2)
    
    # 2. Start Vite Server (Frontend)
    print("Starting Vite Frontend...")
    # using shell=True for npm on Windows
    frontend = subprocess.Popen(
        "npm run dev",
        shell=True,
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    
    # Wait for vite to start
    time.sleep(3)
    
    # 3. Open browser
    print("Opening browser to http://localhost:5173/")
    webbrowser.open("http://localhost:5173/")
    
    print("\nBoth servers are running. Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        backend.terminate()
        # npm/node subprocesses on windows might need taskkill, but terminate is fine for now
        frontend.terminate()
        print("Done.")

if __name__ == "__main__":
    main()
