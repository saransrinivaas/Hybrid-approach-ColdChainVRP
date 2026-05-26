import re
import os

with open('backend/compare.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace scenario2 import and SCENARIO_MODULES
new_content = re.sub(
    r"import scenario2 as SC2.*?SCENARIO_LABELS = \{.*?\}",
    """SCENARIO_MODULES = {
    "easy":  SC1,
}

SCENARIO_LABELS = {
    "easy":  f"Easy — {len(SC1.CLINICS)} Clinics / {len(SC1.VEHICLES)} Vehicles" if hasattr(SC1, "CLINICS") else "Easy — 10 Clinics / 2 Vehicles",
}""",
    content,
    flags=re.DOTALL
)

# Remove the file reading logic
new_content = re.sub(
    r"    out_path = os\.path\.join\(BASE_DIR, \"compare_results\.json\"\).*?        except Exception:\n            pass\n",
    "    pass\n",
    new_content,
    flags=re.DOTALL
)

# Replace the save logic at the end
old_save = '''    # Save
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\\n[OK] Results saved → {out_path}")'''

new_save = '''    # Submit to volatile memory via HTTP
    import urllib.request
    import json
    req = urllib.request.Request(
        "http://127.0.0.1:5000/api/submit-results?type=compare",
        data=json.dumps(results, default=str).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            print("\\n[OK] Results submitted to volatile memory")
    except Exception as e:
        print(f"\\n[WARN] Failed to submit compare results: {e}")'''

new_content = new_content.replace(old_save, new_save)

with open('backend/compare.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
