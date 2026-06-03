import os
import sys
import traceback
from pathlib import Path

# Ensure env is loaded
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from qaoa_hardware_solver import retrieve_hardware_result

def main():
    job_id = "d8ecmfg7jphs739khrd0"
    try:
        res = retrieve_hardware_result(job_id, verbose=True)
        print("Success! Result:")
        print(res)
    except Exception as e:
        print("Failed to retrieve result:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
