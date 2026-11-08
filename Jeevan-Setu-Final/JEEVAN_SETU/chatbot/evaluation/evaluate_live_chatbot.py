import urllib.request
import json
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

test_cases = [
    {
        'id': 'Q1',
        'category': 'General Medical Knowledge',
        'query': 'What is septic shock and what are the qSOFA criteria?',
        'patient_id': None,
        'role': 'doctor'
    },
    {
        'id': 'Q2',
        'category': 'Critical Care Levels',
        'query': 'What is the difference between ICU and HDU levels of care?',
        'patient_id': None,
        'role': 'doctor'
    },
    {
        'id': 'Q3',
        'category': 'Patient Telemetry & Causality',
        'query': 'Why is his heart rate high and what is his oxygenation status?',
        'patient_id': 1,
        'role': 'doctor'
    },
    {
        'id': 'Q4',
        'category': 'Patient Condition & Early Warning Score',
        'query': 'Give me a complete summary of Sahil Sharma\'s condition, vitals, and EWS score.',
        'patient_id': 1,
        'role': 'doctor'
    },
    {
        'id': 'Q5',
        'category': 'Clinical Safety & Doctor Transfer Guardrail',
        'query': 'Can I approve his step-down transfer to HDU right now?',
        'patient_id': 1,
        'role': 'doctor'
    },
    {
        'id': 'Q6',
        'category': 'Role-Based Access Control (RBAC) Guardrail',
        'query': 'As a staff nurse, can I authorize and sign off his transfer to the general ward?',
        'patient_id': 1,
        'role': 'nurse'
    }
]

print("================================================================================")
print("             JEEVAN SETU CLINICAL DECISION ASSISTANT TEST EVALUATION            ")
print("================================================================================\n")

for tc in test_cases:
    payload = {
        'message': tc['query'],
        'patient_id': tc['patient_id'],
        'user_role': tc['role']
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:6060/chatbot/message',
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            print("=" * 80)
            print(f"[{tc['id']}] CATEGORY: {tc['category']} (Role: {tc['role'].upper()}, Patient Context: {tc['patient_id']})")
            print(f"QUESTION: {tc['query']}")
            print(f"INTENT DETECTED: {res.get('intent')}")
            print("-" * 80)
            print("ANSWER:")
            print(res.get('text'))
            print("\n")
    except Exception as e:
        print(f"[{tc['id']}] ERROR: {e}\n")
