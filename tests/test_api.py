import requests, json

tests = [
    ("I have bleeding gums and high fever", "Dengue edge case"),
    ("I feel tired lost weight and chronic cough for 3 weeks", "TB screening"),
    ("hello", "Greeting"),
    ("I cannot breathe, chest pain", "Emergency"),
    ("fever chills and joint pain for 4 days", "Multi-symptom malaria/dengue"),
]

for text, label in tests:
    d = requests.post("http://localhost:5000/api/chat", json={"text": text}, timeout=30).json()
    t = d.get("type")
    print(f"\n[{label}]")
    print(f"  type = {t}")
    if t == "followup":
        print(f"  question = {d['question']}")
        print(f"  candidates = {d.get('candidates', [])}")
    elif t == "disease":
        print(f"  confidence = {int(d.get('confidence', 0)*100)}%")
        print(f"  reply = {d.get('reply','')[:300]}")
    else:
        print(f"  reply = {d.get('reply','')[:200]}")
