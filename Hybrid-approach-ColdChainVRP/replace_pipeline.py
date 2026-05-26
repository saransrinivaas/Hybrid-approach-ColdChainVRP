import re
import os

with open('backend/pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_save = '''        # Write the combined payload expected by ResultsView's Comparison tab
        combined_payload = {
            "classical": classical_result,
            "qaoa": final
        }
        
        results_path = os.path.join(BASE_DIR, "results.json")
        with open(results_path, "w") as f:
            json.dump(combined_payload, f, indent=2)
        print(f"\\n  [OK] Final combined results saved -> {results_path}")'''

new_save = '''        # Write the combined payload expected by ResultsView's Comparison tab
        combined_payload = {
            "classical": classical_result,
            "qaoa": final
        }
        
        import urllib.request
        import json
        req = urllib.request.Request(
            "http://127.0.0.1:5000/api/submit-results?type=pipeline_easy",
            data=json.dumps(combined_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        try:
            with urllib.request.urlopen(req) as response:
                print("\\n  [OK] Final combined results submitted to volatile memory")
        except Exception as e:
            print(f"\\n  [WARN] Failed to submit results: {e}")'''

new_content = content.replace(old_save, new_save)

with open('backend/pipeline.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
