# ==========================================
# services/intent_classifier.py — Intent Routing
# ==========================================
import re
import logging
from config import client, GROQ_API_KEY

logger = logging.getLogger(__name__)


def detect_direct_disease_query(user_en: str):
    """
    Detect if the user is asking specifically about a named disease.
    """
    DIRECT_DISEASE_PATTERNS = [
        r"do i have", r"i have", r"i think i have", r"i may have", r"i might have",
        r"is it", r"do i suffer from", r"what is", r"tell me about",
        r"information about", r"info on", r"about", r"symptoms of",
        r"signs of", r"treatment for", r"cure for",
    ]
    query_lower = user_en.lower()
    has_direct_pattern = any(re.search(p, query_lower) for p in DIRECT_DISEASE_PATTERNS)
    if not has_direct_pattern:
        return None
    return True


def classify_intent(user_en: str, history: list) -> str:
    """
    Classify the user's intent to route to the correct handler.
    Uses fast rule-based pre-checks first, then falls back to LLM.
    """
    low = user_en.lower().strip()

    # --- 1. Greetings ---
    GREETINGS = {"hi", "hello", "hey", "namaste", "hola", "good morning",
                 "good evening", "good afternoon", "howdy", "greetings",
                 "sup", "what's up", "bye", "goodbye", "thanks", "thank you",
                 "ok", "okay", "sure", "alright"}
    if low in GREETINGS or (len(low.split()) <= 2 and any(g in low for g in GREETINGS)):
        return "greeting"

    # --- 2. Emergency red flags ---
    RED_FLAGS = ["can't breathe", "cant breathe", "difficulty breathing",
                 "shortness of breath", "chest pain", "loss of consciousness",
                 "severe bleeding", "unconscious", "heart attack", "stroke",
                 "not breathing", "seizure", "overdose", "poisoning",
                 "medical emergency", "help emergency", "urgent help",
                 "allergic reaction", "anaphylaxis"]
    if any(f in low for f in RED_FLAGS):
        return "emergency"

    # --- 3. Symptom diagnosis fast-path ---
    SYMPTOM_INDICATORS = [
        "i have ", "i've got ", "i am having ", "i'm having ",
        "i feel ", "i am feeling ", "i'm feeling ",
        "suffering from ", "experiencing ", "i've been having ",
        "i got ", "i have been ", "i've been ",
        "mujhe ", "muje ", "meri ", "mera ",
        "ho raha ", "ho rahi ", "hai mujhe", "lag raha",
    ]
    SYMPTOM_WORDS = [
        "headache", "head ache", "migraine", "fever", "temperature",
        "cough", "cold", "flu", "pain", "ache", "aches",
        "nausea", "vomit", "vomiting", "diarrhea", "diarrhoea",
        "rash", "itch", "itching", "swelling", "swollen",
        "dizzy", "dizziness", "tired", "fatigue", "weakness", "weak",
        "sore throat", "runny nose", "stuffy nose", "congestion",
        "chills", "shiver", "body ache", "joint pain", "back pain",
        "stomach pain", "abdominal pain", "breathing",
        "bleeding", "wound", "injury",
        "anxiety", "depression", "stress", "insomnia",
        "appetite", "weight loss", "weight gain",
        # Hindi symptom keywords (transliterated)
        "bukhar", "dard", "khasi", "ulti", "sar dard",
        "jodon", "thakaan", "chakkte", "chakte", "khujli",
        "sujan", "chakkar", "kamzori", "bhukh", "dast",
        "balgam", "nakhun", "peeth", "nabz",
    ]
    INFO_EXCLUSIONS = [
        "what is", "what causes", "how long does", "is it contagious",
        "cure for", "cause of", "reason for", "how does",
    ]
    has_indicator = any(ind in low for ind in SYMPTOM_INDICATORS)
    has_symptom   = any(word in low for word in SYMPTOM_WORDS)
    has_exclusion = any(exc in low for exc in INFO_EXCLUSIONS)
    if has_indicator and has_symptom and not has_exclusion:
        return "symptom_diagnosis"

    # --- 3b. Bare symptom list fast-path (e.g., "fever, joint pain, rash") ---
    # Handles input that is ONLY symptoms with no subject phrase (common for Hindi/short inputs)
    tokens = [t.strip() for t in re.split(r'[,،;\n]+|\band\b', low) if t.strip()]
    matching_symptom_tokens = [t for t in tokens if any(word in t for word in SYMPTOM_WORDS)]
    # If the majority of tokens are symptom words and there's no exclusion phrase, treat as diagnosis
    if len(tokens) >= 1 and len(matching_symptom_tokens) >= 1 and not has_exclusion:
        # Avoid mis-routing pure info questions
        if not any(q in low for q in ["what is", "what are", "how to", "why does", "tell me", "information"]):
            return "symptom_diagnosis"

    # --- 4. First Aid ---
    FIRST_AID_TRIGGERS = [
        "first aid", "firstaid", "emergency treatment",
        "what to do for", "what to do if", "what should i do for",
        "how to treat a", "how to treat", "how to help someone",
        "how do i treat", "how to handle a", "how to manage a",
        "steps for", "treatment for burn", "treatment for cut",
        "treatment for fracture", "treatment for snake", "treatment for poison",
        "choking", "drowning", "how to stop bleeding", "cpr",
        "heimlich", "nosebleed", "sprain treatment", "treating a wound",
    ]
    if any(t in low for t in FIRST_AID_TRIGGERS):
        return "first_aid"

    # --- 5. Drug / Medicine Info ---
    DRUG_TRIGGERS = [
        "dosage of", "dose of", "side effect", "side effects of",
        "drug interaction", "how much", "can i take", "is it safe to take",
        "paracetamol", "ibuprofen", "aspirin", "amoxicillin", "metformin",
        "azithromycin", "omeprazole", "cetirizine", "dolo", "crocin",
        "pantoprazole", "ranitidine", "montelukast", "atorvastatin",
        "antibiotic", "antifungal", "antiviral", "painkiller", "pain killer",
    ]
    DRUG_QUESTION_HINTS = ["medicine", "drug", "tablet", "capsule", "syrup", "injection", "medication"]
    has_drug_question = any(t in low for t in DRUG_TRIGGERS)
    has_drug_hint = (
        any(h in low for h in DRUG_QUESTION_HINTS) and
        any(q in low for q in ["what is", "tell me about", "information", "info", "uses", "use of", "how to use"])
    )
    if has_drug_question or has_drug_hint:
        return "drug_info"

    # --- 6. Direct Disease ---
    if detect_direct_disease_query(low):
        return "direct_disease"

    # --- 7. Out of scope ---
    NON_MEDICAL_HINTS = ["weather", "cricket", "sports", "movie", "stock",
                         "political", "news", "recipe", "cook", "game",
                         "song", "music", "flight", "hotel"]
    if any(h in low for h in NON_MEDICAL_HINTS):
        return "out_of_scope"

    if not GROQ_API_KEY:
        return "symptom_diagnosis"

    # --- 8. LLM-based classification ---
    history_snippet = ""
    if history:
        last_turns = history[-4:]
        history_snippet = "\n".join([f"{m['role'].capitalize()}: {m['content'][:80]}" for m in last_turns])

    try:
        prompt = (
            "You are an intent classifier for a medical chatbot called MediMitra.\n"
            "Classify the user's message into EXACTLY ONE of these intents:\n\n"
            "  - greeting      : casual greetings, thanks, bye, small talk\n"
            "  - emergency     : life-threatening symptoms, calls for urgent help\n"
            "  - vaccination   : asking about vaccines, immunization schedules\n"
            "  - drug_info     : asking about a medicine/drug.\n"
            "  - first_aid     : asking what to do in an acute injury/emergency situation.\n"
            "  - direct_disease: user asks about or confirms a specific named disease.\n"
            "  - symptom_diagnosis: user describes symptoms to find out what disease they have.\n"
            "  - general_medical: any other medical/health question.\n"
            "  - out_of_scope  : completely non-medical (weather, sports, etc.)\n\n"
            "IMPORTANT: Questions about a specific medicine's uses/dosage/side effects = drug_info\n"
            "IMPORTANT: 'what disease do I have?' = symptom_diagnosis (NOT general_medical)\n"
            "IMPORTANT: 'do I have [specific disease]?' = direct_disease\n\n"
            f"Conversation History:\n{history_snippet}\n\n"
            f"User: {user_en}\n\n"
            "Reply with ONLY the intent label, nothing else."
        )
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
            timeout=20
        )
        intent = resp.choices[0].message.content.strip().lower()
        VALID = {"greeting", "emergency", "vaccination", "direct_disease",
                 "symptom_diagnosis", "general_medical", "out_of_scope",
                 "drug_info", "first_aid"}
        classified = "general_medical"
        for v in VALID:
            if v in intent:
                classified = v
                break
        # Safety net: if LLM says general_medical but message has symptom words, upgrade.
        if classified == "general_medical" and not has_exclusion:
            if any(word in low for word in SYMPTOM_WORDS):
                classified = "symptom_diagnosis"
        return classified
    except Exception as e:
        logger.error(f"Intent classification error: {e}")
        return "symptom_diagnosis"
