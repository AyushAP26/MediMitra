# ==========================================
# data/static_data.py — Static Data & Loaders
# ==========================================
import os
import json
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_health_tips():
    """Load health tips from health_tips.json file"""
    try:
        tips_file = os.path.join(BASE_DIR, "health_tips.json")
        with open(tips_file, 'r', encoding='utf-8') as f:
            tips_data = json.load(f)
        all_tips = []
        for category in tips_data:
            all_tips.extend(category.get("tips", []))
        return all_tips
    except Exception as e:
        logger.error(f"Error loading health tips: {e}")
        return [
            "Drink at least 8 glasses of water a day to stay hydrated.",
            "Wash your hands frequently with soap and water for 20 seconds.",
            "Get 7-9 hours of sleep every night for better immune health."
        ]

HEALTH_TIPS = load_health_tips()
logger.info(f"Loaded {len(HEALTH_TIPS)} health tips from health_tips.json")

# Normalization Dictionary
NORMALIZATION = {
    "temperature": "fever",
    "high temperature": "fever",
    "feverish": "fever",
    "vomit": "vomiting",
    "throwing up": "vomiting",
    "tummy ache": "abdominal pain",
    "stomach pain": "abdominal pain",
    "muscle ache": "body aches",
    "body ache": "body aches",
    "loose motion": "diarrhea",
    "loose stools": "diarrhea",
}

GENERIC_SYMPTOMS = set([
    "fever", "temperature", "pain", "headache", "nausea", "vomiting",
    "diarrhea", "fatigue", "cough", "sore throat", "body aches",
    "weakness", "chills", "abdominal pain", "malaise", "lethargy", "crying"
])

MAJOR_SYMPTOMS = set([
    "jaundice", "seizures", "paralysis", "hydrophobia", "bleeding", "bleeding gums",
    "unconscious", "confusion", "stiffness", "chronic cough", "weight loss",
    "white patches", "joint pain", "difficulty breathing", "chest pain", "slurred speech",
    "sudden weakness", "vision loss", "dark urine", "pale stools", "swelling",
    "rash", "bullseye rash", "stiff neck", "high fever", "bloody diarrhea"
])

VACCINE_SCHEDULES = {
    "newborn": [
        {"name": "BCG", "purpose": "Prevents tuberculosis", "timing": "At birth"},
        {"name": "Hepatitis B (birth dose)", "purpose": "Prevents hepatitis B", "timing": "Within 24 hours of birth"},
        {"name": "OPV-0 (Oral Polio Vaccine)", "purpose": "Prevents polio", "timing": "At birth"},
        {"name": "DPT", "purpose": "Prevents diphtheria, whooping cough, tetanus", "timing": "At 6, 10, and 14 weeks"},
        {"name": "Hib", "purpose": "Prevents meningitis and pneumonia", "timing": "At 6, 10, and 14 weeks"},
        {"name": "Rotavirus Vaccine", "purpose": "Prevents severe diarrhea", "timing": "At 6, 10, and 14 weeks"},
        {"name": "PCV", "purpose": "Prevents pneumonia, meningitis, ear infections", "timing": "At 6, 10, and 14 weeks"},
        {"name": "IPV", "purpose": "Prevents polio", "timing": "At 6 and 14 weeks"},
    ],
    "pregnant": [
        {"name": "Tdap", "purpose": "Protects newborns from whooping cough", "timing": "27–36 weeks of pregnancy"},
        {"name": "Influenza", "purpose": "Protects mother and baby from flu", "timing": "Any trimester during flu season"},
    ],
    "elderly": [
        {"name": "Influenza", "purpose": "Prevents seasonal flu", "timing": "Annual"},
        {"name": "Pneumococcal (PPSV23, PCV13)", "purpose": "Prevents pneumonia", "timing": "As recommended"},
        {"name": "Shingles (Zoster)", "purpose": "Prevents shingles", "timing": "Age 50+, 2 doses"},
        {"name": "Tdap/Td", "purpose": "Booster for tetanus, diphtheria, pertussis", "timing": "Every 10 years"},
    ],
}
