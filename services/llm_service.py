# ==========================================
# services/llm_service.py — LLM Generation Functions
# ==========================================
import json
import logging
from config import client, GROQ_API_KEY

logger = logging.getLogger(__name__)


def translate_to_english(text: str) -> str:
    if not GROQ_API_KEY: return text
    try:
        prompt = f"Translate the following medical query to English. Return ONLY the translation, nothing else.\n\nQuery: {text}"
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            timeout=30
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text


def extract_symptoms(text: str) -> dict:
    """
    LLM-powered dynamic symptom extraction.
    Returns a dict: 'symptoms', 'duration', 'severity'.
    """
    if not GROQ_API_KEY:
        return {"symptoms": [], "duration": "", "severity": ""}
    try:
        system_prompt = (
            "You are an expert NLP medical data extractor.\n"
            "Extract structured medical info from the user's message.\n"
            "Return a JSON object with EXACTLY these keys:\n"
            "  'symptoms': list of symptom names described by the user (empty list if none). Standardize them (e.g., 'tummy ache' -> 'abdominal pain', 'throwing up' -> 'vomiting', 'high temperature' -> 'fever').\n"
            "  'duration': string describing how long (e.g. '3 days', 'since yesterday') or empty string if not mentioned.\n"
            "  'severity': one of 'mild', 'moderate', 'severe', or empty string if not clearly stated.\n\n"
            "Rules:\n"
            "  - DO NOT include negated symptoms (e.g., 'I don't have a cough' -> exclude 'cough').\n"
            "  - Ensure symptoms are concise medical terms.\n"
            "  - Examples:\n"
            "    - 'I have severe bleeding gums and fever for 2 days' -> symptoms: ['bleeding gums', 'fever'], duration: '2 days', severity: 'severe'\n"
            "    - 'I think I might have dengue' -> symptoms: []\n"
            "    - 'Do I have malaria? I feel constant chills' -> symptoms: ['chills']\n"
        )
        user_prompt = f"User Message: {text}\n\nJSON:"
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        syms = data.get("symptoms", [])
        return {
            "symptoms": [s.lower() for s in syms] if isinstance(syms, list) else [],
            "duration": str(data.get("duration", "") or ""),
            "severity": str(data.get("severity", "") or "").lower()
        }
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return {"symptoms": [], "duration": "", "severity": ""}


def generate_differential_diagnosis(symptoms: list, duration: str, severity: str,
                                    confirmed: set, denied: set, history: list, target_lang: str,
                                    followup_round: int = 0) -> dict:
    """
    Core Generative AI diagnostic engine.
    Returns structured JSON with a follow-up question or a final diagnosis list.
    """
    if not GROQ_API_KEY:
        return {"type": "info", "reply": "Diagnosis engine unavailable (No API Key)."}

    history_snippet = ""
    if history:
        last_turns = history[-6:]
        history_snippet = "\n".join([f"{m['role'].capitalize()}: {m['content'][:150]}" for m in last_turns])

    prompt = (
        f"You are MediMitra, an elite expert medical diagnostician. Always respond in {target_lang}.\n"
        "A patient is presenting with the following clinical profile:\n"
        f"  - Extracted Core Symptoms: {', '.join(symptoms)}\n"
        f"  - Verified Confirmed Symptoms (from chat): {', '.join(confirmed)}\n"
        f"  - Denied Symptoms (patient explicitly said NO): {', '.join(denied)}\n"
        f"  - Duration: {duration or 'Not specified'}\n"
        f"  - Severity: {severity or 'Not specified'}\n\n"
        f"Conversation History:\n{history_snippet}\n\n"
        "INSTRUCTIONS:\n"
        f"1. Analyze the clinical profile using your vast medical knowledge and respond ENTIRELY in {target_lang}.\n"
        "2. Generate a Differential Diagnosis (top 3 most likely conditions). You are NOT limited to any database.\n"
        + (
            # After at least one follow-up round, force a final diagnosis — no more questions.
            f"3. MANDATORY FINAL DIAGNOSIS REQUIRED: The patient has already answered {followup_round} follow-up question(s). "
            "You MUST now return SCHEMA B (action: diagnose) with your best differential diagnosis. "
            "Do NOT ask another follow-up question. Use all available symptom data to make your best assessment now.\n\n"
            if followup_round >= 1 else
            "3. IF the clinical picture is too vague (e.g., just 'fever' or 'headache'), or if you need to distinguish between two highly likely conditions, YOU MUST GENERATE A FOLLOW-UP QUESTION. Ask about a pathognomonic/discriminating symptom. Keep it simple (e.g., 'Do you also have pain behind your eyes?').\n"
            "4. IF the clinical picture is strong and you are confident (e.g., 'bleeding gums and fever' -> Dengue), generate the final diagnosis.\n\n"
        )
        + f"CRITICAL: The values for 'question' and all text in the diagnosis 'description', 'why_selected', and 'measures' MUST be in {target_lang}.\n\n"
        "You MUST respond ONLY with a raw JSON object matching one of these two schemas:\n\n"
        "SCHEMA A (Needs Follow-up):\n"
        "{\n"
        '  "action": "followup",\n'
        '  "question": "The specific discriminative question to ask",\n'
        '  "candidates": ["Disease 1", "Disease 2"]\n'
        "}\n\n"
        "SCHEMA B (Confident Diagnosis):\n"
        "{\n"
        '  "action": "diagnose",\n'
        '  "confidence": 0.95,\n'
        '  "diseases": [\n'
        '    {\n'
        '      "name": "Disease Name",\n'
        '      "description": "Short explanation of the disease",\n'
        '      "why_selected": "Explain why this matches the symptoms over other conditions",\n'
        '      "prevention": ["Tip 1", "Tip 2"],\n'
        '      "measures": ["Home remedy 1", "When to see doctor"]\n'
        '    }\n'
        '  ]\n'
        "}\n\n"
        "CRITICAL: Return ONLY valid JSON block. No markdown wrappers. No conversational text."
    )

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
            timeout=30
        )
        raw_json = resp.choices[0].message.content.strip()
        data = json.loads(raw_json)

        if data.get("action") == "followup":
            question = data.get("question", "Could you tell me more about your symptoms?")
            return {
                "type": "followup",
                "question": question,
                "candidates": data.get("candidates", []),
                "detected_lang": target_lang
            }
        else:
            diseases = data.get("diseases", [])
            confidence = data.get("confidence", 0.0)
            reply_blocks = []
            if confidence >= 0.85:
                reply_blocks.append(f"Based on your symptoms, I am {int(confidence*100)}% confident in this assessment:\n")
            else:
                reply_blocks.append(f"Based on your symptoms, here are the most likely possibilities (Confidence: {int(confidence*100)}%):\n")

            for i, d in enumerate(diseases[:3]):
                name = d.get('name', 'Unknown')
                desc = d.get('description', '')
                why  = d.get('why_selected', '')
                meas = ", ".join(d.get('measures', []))
                block  = f"### {i+1}. {name}\n"
                block += f"{desc}\n\n"
                block += f"**Key Evidence:** {why}\n\n"
                if meas:
                    block += f"**Suggested Action:** {meas}\n"
                reply_blocks.append(block)

            reply_blocks.append("\n*Disclaimer: I am an AI, not a doctor. Please consult a healthcare professional for an official diagnosis.*")
            final_reply = "\n".join(reply_blocks)
            return {
                "type": "disease",
                "reply": final_reply,
                "confidence": confidence,
                "sources": [],
                "vaccines": [],
                "reset_context": True
            }
    except Exception as e:
        logger.error(f"Generative Diagnosis Error: {e}")
        return {"type": "info", "reply": "I encountered an error trying to analyze your symptoms. Please try again or seek a doctor if urgent."}


def generate_drug_info(user_text: str, history: list, target_lang: str = "en") -> dict:
    """Generate a structured medicine/drug information card using LLM."""
    if not GROQ_API_KEY:
        return {"type": "drug_info", "reply": "Drug information service unavailable (No API Key)."}

    messages = [
        {
            "role": "system",
            "content": (
                f"You are MediMitra, a knowledgeable medical assistant. Always respond in {target_lang}.\n\n"
                "When asked about a medicine or drug, respond using EXACTLY this format:\n\n"
                "### [Drug Name] ([Generic/Brand Name if different])\n"
                "**Drug Class:** [e.g. Analgesic, Antibiotic, NSAID]\n"
                "**Primary Uses:** [What it treats — 2-3 key uses as a short list]\n"
                "**How It Works:** [Simple 1-sentence explanation]\n"
                "**Typical Dosage:**\n"
                "- Adults: [dose]\n"
                "- Children: [dose or 'Consult a doctor']\n"
                "**Common Side Effects:** [3-5 as bullet points]\n"
                "**Important Warnings:**\n"
                "- [Warning 1]\n"
                "- [Warning 2]\n"
                "**Drug Interactions:** [Key interactions or 'None significant for typical use']\n"
                "**When to See a Doctor:** [Red flags / overdose symptoms]\n\n"
                "CRITICAL RULES:\n"
                "- Start DIRECTLY with '### [Drug Name]' — no intro text\n"
                "- Use ONLY '###' for the drug name header (not ## or #)\n"
                "- Keep descriptions concise and practical\n"
                "- Always end with: '*Not medical advice — consult a pharmacist or doctor before use.*'\n"
                "- If asked about multiple drugs, create a '### [Drug Name]' section for each"
            )
        }
    ]
    for m in history[-6:]:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": m["content"]})
    messages.append({"role": "user", "content": user_text})

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=700,
            timeout=30
        )
        reply = response.choices[0].message.content.strip()
        return {"type": "drug_info", "reply": reply}
    except Exception as e:
        logger.error(f"Drug info error: {e}")
        return {"type": "drug_info", "reply": "I couldn't retrieve drug information right now. Please try again or consult a pharmacist."}


def generate_first_aid(user_text: str, history: list, target_lang: str = "en") -> dict:
    """Generate structured first aid instructions using LLM."""
    if not GROQ_API_KEY:
        return {"type": "first_aid", "reply": "First aid service unavailable (No API Key)."}

    messages = [
        {
            "role": "system",
            "content": (
                f"You are MediMitra, a trained first aid guide. Always respond in {target_lang}.\n\n"
                "When asked about first aid, respond using EXACTLY this format:\n\n"
                "### First Aid: [Condition/Injury Name]\n"
                "**Severity Assessment:** [Minor / Moderate / Severe — 1 sentence]\n\n"
                "**Immediate Steps:**\n"
                "1. [Step 1 — most urgent action first]\n"
                "2. [Step 2]\n"
                "3. [Step 3]\n"
                "(Continue numbering all steps — typically 4-7 steps)\n\n"
                "**What NOT To Do:**\n"
                "- [Common mistake to avoid 1]\n"
                "- [Common mistake to avoid 2]\n\n"
                "**🚨 Call Emergency Services (112/108) If:**\n"
                "- [Serious sign 1]\n"
                "- [Serious sign 2]\n\n"
                "CRITICAL RULES:\n"
                "- Start DIRECTLY with '### First Aid: [Condition]' — no intro text\n"
                "- Use ONLY '###' for the condition header (not ## or #)\n"
                "- Steps must be clear, numbered, and actionable\n"
                "- ALWAYS include the emergency call section\n"
                "- Always end with: '*Not a substitute for professional medical care. Call emergency services for severe cases.*'\n"
                "- If the situation sounds immediately life-threatening, START with 'Call 112/108 NOW' as step 1"
            )
        }
    ]
    for m in history[-6:]:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": m["content"]})
    messages.append({"role": "user", "content": user_text})

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.2,
            max_tokens=700,
            timeout=30
        )
        reply = response.choices[0].message.content.strip()
        return {"type": "first_aid", "reply": reply}
    except Exception as e:
        logger.error(f"First aid error: {e}")
        return {"type": "first_aid", "reply": "I couldn't retrieve first aid instructions right now. Please call emergency services (112/108) if this is urgent."}


def generate_general_answer(user_text: str, history: list, target_lang: str = "English",
                            db_context: list = None) -> dict:
    """Answers any medical/health question in a natural, conversational way."""
    context_snippet = ""
    if db_context:
        snippets = []
        for d in db_context[:3]:
            name = d.get("name", "")
            desc = d.get("description", "")[:200]
            measures = "; ".join(d.get("measures", [])[:3])
            snippets.append(f"[{name}] {desc} | Measures: {measures}")
        context_snippet = (
            "\n\nRelevant Medical DB Context (use if helpful, don't force it):\n"
            + "\n".join(snippets)
        )

    messages = [
        {
            "role": "system",
            "content": (
                f"You are MediMitra, an intelligent, friendly medical assistant. "
                f"Always respond in {target_lang}.\n\n"
                "Your capabilities:\n"
                "- Answer any health or medical question clearly and helpfully\n"
                "- Explain medical concepts in simple language\n"
                "- Provide lifestyle, diet, and prevention advice\n"
                "- Compare diseases, symptoms, or treatments\n"
                "- Discuss mental health, first aid, medications, anatomy, etc.\n"
                "- Remember the conversation history and refer back when relevant\n\n"
                "Formatting rules:\n"
                "- Use bullet points or numbered lists when listing multiple items\n"
                "- Use **bold** ONLY for section titles or primary terms (labels)\n"
                "- Do NOT mix bold and italics (e.g., avoid ***this***)\n"
                "- Keep descriptions in plain text for readability\n"
                "- Be thorough but concise — aim for 150-300 words\n"
                "- Do NOT use the 'Disease 1 / Disease 2' card format unless asked to compare diseases\n"
                "- Always end with: 'Not medical advice — consult a doctor for diagnosis.'\n\n"
                "IMPORTANT: You are a MEDICAL assistant. Politely decline non-medical topics."
                + context_snippet
            )
        }
    ]
    for m in history[-8:]:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": m["content"]})
    messages.append({"role": "user", "content": user_text})

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=800,
            timeout=30
        )
        raw = response.choices[0].message.content.strip()
        reply = raw.replace("\n\n", "\n").strip()
        return {"reply": reply, "raw": raw, "vaccines": [], "sources": []}
    except Exception as e:
        logger.error(f"General answer error: {e}")
        return {
            "reply": "I'm sorry, I had trouble generating a response. Please try rephrasing your question.",
            "raw": "", "vaccines": [], "sources": []
        }
