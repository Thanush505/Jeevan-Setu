import os
import re

base_dir = r"c:\Major_Project\JSF-Web_Broswer_simulator\Jeevan-Setu-Final"

patterns = [
    (r"patient_id\s*=\s*1\b", "patient_id = 1"),
    (r"patient_id\s*:\s*1\b", "patient_id: 1"),
    (r"patient_id\s*\|\|\s*['\"]?1['\"]?", "patient_id || 1"),
    (r"get\(['\"]patient_id['\"]\)\s*\|\|\s*['\"]?1['\"]?", "get('patient_id') || 1"),
    (r"Ravi\s+Kumar", "Ravi Kumar"),
    (r"Doctor_transfer_recommendations", "Doctor_transfer_recommendations"),
    (r"patient_id=1", "patient_id=1 in link/url"),
    (r"patientId\s*=\s*1\b", "patientId = 1"),
    (r"patientId\s*\|\|\s*['\"]?1['\"]?", "patientId || 1"),
    (r"selectedPatientId\s*=\s*1\b", "selectedPatientId = 1"),
    (r"activePatientId\s*=\s*1\b", "activePatientId = 1"),
]

print("=== START AUDIT ===")
found_count = 0
for root, dirs, files in os.walk(base_dir):
    if any(x in root for x in [".venv", ".git", "node_modules", "__pycache__"]):
        continue
    for f in files:
        if f.endswith((".html", ".js", ".py")):
            fp = os.path.join(root, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
                for idx, line in enumerate(lines, 1):
                    for pat, label in patterns:
                        if re.search(pat, line, re.IGNORECASE):
                            rel = os.path.relpath(fp, base_dir)
                            print(f"{rel}:{idx} [{label}] -> {line.strip()[:120]}")
                            found_count += 1
                            break
            except Exception as e:
                pass
print(f"=== END AUDIT: {found_count} matches found ===")

