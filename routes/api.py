# ==========================================
# routes/api.py — Flask Blueprint: All Routes
# ==========================================
import re
import random
import logging
from flask import Blueprint, render_template, request, jsonify

from config import client, GROQ_API_KEY, BASE_DIR
from utils.helpers import detect_lang_safe, normalize_symptom_token, LANGUAGE_MAP
from data.static_data import HEALTH_TIPS, VACCINE_SCHEDULES
from services.llm_service import (
    translate_to_english, extract_symptoms,
    generate_differential_diagnosis, generate_drug_info,
    generate_first_aid, generate_general_answer
)
from services.intent_classifier import classify_intent, detect_direct_disease_query

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)


# ==========================================
# HELPER: Vaccination Schedule
# ==========================================
def is_vaccination_schedule_query(user_text_lower):
    age_groups = ["newborn", "baby", "infant", "child", "children", "kid",
                  "pregnant", "pregnancy", "expecting", "mother",
                  "elderly", "senior", "old age", "aged"]
    schedule_patterns = ["vaccines for", "vaccination for", "immunization for",
                         "what vaccines", "which vaccines", "vaccine schedule",
                         "vaccination schedule", "immunization schedule"]
    has_age_group = any(age in user_text_lower for age in age_groups)
    has_schedule_pattern = any(pattern in user_text_lower for pattern in schedule_patterns)
    if has_age_group and has_schedule_pattern:
        return True
    for age in age_groups:
        if f"{age} vaccine" in user_text_lower or f"vaccine {age}" in user_text_lower:
            return True
    return False


def get_age_group_from_query(user_text_lower):
    if any(word in user_text_lower for word in ["newborn", "baby", "infant", "child", "children", "kid"]):
        return "newborn"
    elif any(word in user_text_lower for word in ["pregnant", "pregnancy", "expecting", "mother"]):
        return "pregnant"
    elif any(word in user_text_lower for word in ["elderly", "senior", "old age", "aged"]):
        return "elderly"
    return None


def handle_emergency_triage(user_en, lang):
    red_flags = [
        "difficulty breathing", "cant breathe", "can't breathe", "breathing issue",
        "shortness of breath", "breathless", "chest pain", "loss of consciousness",
        "severe bleeding", "heart attack", "stroke", "not breathing", "seizure",
        "overdose", "poisoning", "anaphylaxis", "allergic reaction",
    ]
    if any(flag in user_en.lower() for flag in red_flags):
        msg = "🚨 This may be a medical emergency. Please call emergency services (112 / 108) or go to the nearest hospital immediately. Do not delay."
        if lang != "en" and lang != "English":
            try:
                msg = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": f"Translate the following emergency alert to {lang}. Keep the emoji 🚨 and provide a clear, urgent translation:\n\n{msg}"}],
                    timeout=30
                ).choices[0].message.content.strip()
            except Exception:
                pass
        return jsonify({"type": "triage", "level": "red", "reply": msg})
    return None


def handle_vaccination_schedule(user_en, lang):
    if not is_vaccination_schedule_query(user_en.lower()):
        return None
    age_group = get_age_group_from_query(user_en.lower())
    if age_group and age_group in VACCINE_SCHEDULES:
        vaccines_list = VACCINE_SCHEDULES[age_group]
        age_group_display = age_group.capitalize() + "s" if age_group != "pregnant" else "Pregnant Women"
        response_lines = [f"**Vaccination Schedule for {age_group_display}:**"]
        for v in vaccines_list:
            response_lines.append(f"\n**{v['name']}**\n- Purpose: {v['purpose']}\n- Timing: {v['timing']}")
        response_lines.append("\n*Note: Consult a doctor for personalized advice.*")
        reply_en = "\n".join(response_lines)
        reply = reply_en
        if lang != "en" and lang != "English":
            try:
                reply = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": f"Translate the following vaccination schedule to {lang}. Keep vaccine names (BCG, DTP, etc.) in English, but translate the timing and purpose:\n\n{reply_en}"}],
                    temperature=0.3,
                    timeout=30
                ).choices[0].message.content.strip()
            except Exception:
                pass
        return jsonify({
            "type": "info", "reply": reply,
            "sources": [f"{age_group_display} Vaccination Schedule"],
            "vaccines": [v["name"] for v in vaccines_list],
            "reset_context": True
        })
    return None


def handle_direct_disease_query(user_text, user_en, history, lang):
    """Return a structured Knowledge Card for a named disease."""
    prompt = f"""
    You are MediMitra, an expert medical assistant.
    The user is asking about: {user_en}
    
    Provide a concise, expert summary of this condition in {lang}.
    Use EXACTLY this Markdown structure (even if not in English):
    
    ### 1. [Disease Name]
    [Provide a 1-2 sentence overview of the disease here. Do NOT repeat the disease name in this first line.]
    
    **Key Symptoms:** [3-4 key symptoms]
    
    **Primary Cause:** [Brief cause]
    
    **Home Care & Treatment:** [3-4 key home measures or treatments]
    
    **Prevention Tips:** [3-4 key prevention tips]
    
    **When to See Doctor:** [Warning signs]
    
    Keep it professional and helpful. Use bold only for the labels above. Avoid italics. End with a medical disclaimer.
    """
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            timeout=30
        )
        reply = resp.choices[0].message.content.strip()
        return jsonify({
            "type": "disease", "reply": reply,
            "sources": [], "vaccines": [],
            "reset_context": True
        })
    except Exception as e:
        logger.error(f"Direct disease query error: {e}")
        return None


def get_symptom_ledger(history, user_en):
    """
    Build confirmed/denied symptom sets from recent history.
    Also recovers original symptoms from earlier user messages so that
    a bare yes/no follow-up answer doesn't wipe out the symptom context.
    """
    all_confirmed = set()
    all_denied    = set()
    recent_history = history[-6:] if len(history) > 6 else history

    # Short yes/no tokens that carry no symptom info
    YES_NO_TOKENS = {"yes", "no", "nope", "nah", "yeah", "yep", "yup",
                     "haan", "nahi", "na", "ha", "ok", "okay"}

    # --- Pass 1: Resolve confirmed/denied from bot follow-up ↔ user answer pairs ---
    for i, msg in enumerate(recent_history):
        if msg["role"] == "bot" and i + 1 < len(recent_history):
            followup_q = msg["content"]
            next_msg   = recent_history[i + 1]
            if next_msg["role"] == "user":
                ans    = next_msg["content"].lower().strip()
                is_no  = any(word in ans for word in ["no", "nope", "nah", "nahi", "na"])
                is_yes = any(word in ans for word in ["yes", "yeah", "yep", "yup", "haan", "ha"])
                s_match = re.search(
                    r"(?:Do you (?:also )?have|Have you experienced)\s+([^?]+)\?",
                    followup_q, re.IGNORECASE
                )
                if s_match:
                    sym = normalize_symptom_token(s_match.group(1).strip())
                    if is_no:  all_denied.add(sym)
                    if is_yes: all_confirmed.add(sym)

    # --- Pass 2: Extract symptoms from earlier substantive user messages ---
    # This recovers the original symptoms when the current user_en is just "Yes"/"No"
    is_current_yesno = user_en.lower().strip() in YES_NO_TOKENS
    if is_current_yesno:
        for msg in recent_history:
            if msg["role"] == "user":
                content = msg["content"].strip()
                # Skip short yes/no messages — only process real symptom messages
                words = content.split()
                if len(words) >= 2 and content.lower() not in YES_NO_TOKENS:
                    prev_extracted = extract_symptoms(content)
                    prev_syms = prev_extracted.get("symptoms", [])
                    # Add to confirmed only if not already denied
                    all_confirmed.update(s for s in prev_syms if s not in all_denied)

    current_extracted = extract_symptoms(user_en)
    all_confirmed.update(current_extracted.get("symptoms", []))
    return all_confirmed, all_denied, current_extracted


# ==========================================
# ROUTES
# ==========================================
@api_bp.route("/")
def index():
    return render_template("index.html")


@api_bp.route("/api/tips")
def health_tips():
    return jsonify({"tips": random.sample(HEALTH_TIPS, min(3, len(HEALTH_TIPS)))})


@api_bp.route("/api/chat", methods=["POST"])
def chat_api():
    payload           = request.json or {}
    user_text         = (payload.get("text") or "").strip()
    history           = payload.get("history") or []
    followup_answer   = (payload.get("followup_answer") or "").strip()
    followup_question = payload.get("followup_question")
    original_lang     = payload.get("original_lang")

    if not user_text:
        return jsonify({"error": "empty"}), 400
    if len(user_text) > 1000:
        return jsonify({"type": "info", "reply": "Please keep your message under 1000 characters for the best results."}), 400
    if len(history) > 20:
        history = history[-20:]

    try:
        # 1. Language Detection & Translation
        lang_code = original_lang or detect_lang_safe(user_text)
        lang = LANGUAGE_MAP.get(lang_code, lang_code) if len(lang_code) == 2 else lang_code

        is_english = lang in ["en", "English"]
        if is_english or followup_answer:
            user_en = user_text
        else:
            user_en = translate_to_english(user_text)

        # 2. Intent Classification
        if followup_answer:
            intent = "symptom_diagnosis"
        else:
            intent = classify_intent(user_en, history)
        logger.info(f"[Intent] '{user_en[:60]}' → {intent}")

        # 3. Route by Intent

        # --- GREETING ---
        if intent == "greeting":
            low = user_en.lower().strip()
            if any(w in low for w in ["bye", "goodbye", "see you", "later"]):
                reply = "Goodbye! Stay healthy. Feel free to come back anytime if you have health questions. 😊"
            elif any(w in low for w in ["thanks", "thank you", "thx"]):
                reply = "You're welcome! I'm always here to help with your health questions. Take care! 💙"
            elif any(w in low for w in ["sorry", "my bad"]):
                reply = "No worries at all! How can I assist you with your health today?"
            else:
                reply = (
                    "Hello! I'm **MediMitra**, your personal medical assistant. 👋\n\n"
                    "I can help you with:\n"
                    "- 🩺 **Symptom checking** and disease information\n"
                    "- 💊 **Treatment & medication** guidance\n"
                    "- 🥗 **Diet, lifestyle & prevention** tips\n"
                    "- 💉 **Vaccination schedules**\n"
                    "- 🚑 **Emergency triage** guidance\n"
                    "- ❓ **Any medical question** you have\n\n"
                    "What health concern can I help you with today?"
                )
            is_pure_ascii_short = all(ord(c) < 128 for c in user_text.strip()) and len(user_text.split()) <= 3
            if lang != "en" and lang != "English" and not is_pure_ascii_short:
                try:
                    reply = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "user", "content": f"Translate the following text to {lang}. Keep emojis and markdown formatting intact. Return ONLY the translation.\n\n{reply}"}],
                        timeout=30
                    ).choices[0].message.content.strip()
                except Exception:
                    pass
            return jsonify({"type": "greeting", "reply": reply})

        # --- EMERGENCY ---
        if intent == "emergency":
            triage_res = handle_emergency_triage(user_en, lang)
            if triage_res:
                return triage_res

        # --- DRUG / MEDICINE INFO ---
        if intent == "drug_info":
            return jsonify(generate_drug_info(user_text, history, lang))

        # --- FIRST AID ---
        if intent == "first_aid":
            return jsonify(generate_first_aid(user_text, history, lang))

        # --- VACCINATION SCHEDULE ---
        if intent == "vaccination":
            vaccine_res = handle_vaccination_schedule(user_en, lang)
            if vaccine_res:
                return vaccine_res
            # Fall through to general_medical

        # --- DIRECT DISEASE QUERY ---
        if intent == "direct_disease":
            direct_res = handle_direct_disease_query(user_text, user_en, history, lang)
            if direct_res:
                return direct_res
            intent = "general_medical"

        # --- OUT OF SCOPE ---
        if intent == "out_of_scope":
            reply = (
                "I'm MediMitra, a **medical assistant**. I'm only able to help with health and medical topics.\n\n"
                "Could you ask me a health-related question? For example:\n"
                "- 'What are the symptoms of dengue?'\n"
                "- 'How do I reduce fever at home?'\n"
                "- 'What foods should I avoid with diabetes?'"
            )
            if lang != "en" and lang != "English":
                try:
                    reply = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "user", "content": f"Translate the following text to {lang}. Return ONLY the translation.\n\n{reply}"}],
                        timeout=30
                    ).choices[0].message.content.strip()
                except Exception:
                    pass
            return jsonify({"type": "info", "reply": reply})

        # --- GENERAL MEDICAL Q&A ---
        if intent == "general_medical":
            gen_out = generate_general_answer(user_text, history, target_lang=lang)
            return jsonify({
                "type": "info",
                "reply": gen_out["reply"],
                "sources": gen_out.get("sources", []),
                "reset_context": False
            })

        # --- SYMPTOM DIAGNOSIS ---
        user_msgs = [m["content"] for m in history if m["role"] == "user"]
        full_context = " | ".join(user_msgs[-3:]) + " | " + user_en if history else user_en

        # Count how many follow-up rounds have already happened (yes/no answers in history)
        YES_NO_SET = {"yes", "no", "nope", "nah", "yeah", "yep", "yup", "haan", "nahi", "na", "ha"}
        followup_round = sum(
            1 for m in history
            if m["role"] == "user" and m["content"].strip().lower() in YES_NO_SET
        )
        # Also count if current message is a followup answer
        if followup_answer:
            followup_round += 1

        all_confirmed, all_denied, extracted = get_symptom_ledger(history, user_en)
        symptoms = extracted.get("symptoms", [])
        duration = extracted.get("duration", "")
        severity = extracted.get("severity", "")

        if followup_answer and followup_question:
            s_match = re.search(
                r"(?:Do you (?:also )?have|Have you experienced)\s+([^?]+)\?",
                followup_question, re.IGNORECASE
            )
            if s_match:
                sym = normalize_symptom_token(s_match.group(1).strip())
                ans = followup_answer.lower().strip()
                if any(word in ans for word in ["no", "nope", "nah", "nahi", "na"]):
                    all_denied.add(sym)
                elif any(word in ans for word in ["yes", "yeah", "yep", "yup", "haan", "ha"]):
                    all_confirmed.add(sym)

        is_vaccine_q = any(v in user_en.lower() for v in ["vaccine", "vaccination", "teeka", "immuniz"])
        if is_vaccine_q:
            vaccine_res = handle_vaccination_schedule(user_en, lang)
            if vaccine_res:
                return vaccine_res

        SYMPTOM_CHECK_PATTERNS = ["what disease", "which disease", "what do i have", "am i sick", "how sick"]
        is_symptom_check = any(p in user_en.lower() for p in SYMPTOM_CHECK_PATTERNS)
        is_info_q = (
            any(k in user_en.lower() for k in ["what is", "how to", "prevent", "cure for", "treatment"])
            and not is_symptom_check and len(symptoms) == 0
        )
        if is_info_q:
            gen_out = generate_general_answer(user_text, history, target_lang=lang)
            return jsonify({"type": "info", "reply": gen_out["reply"], "reset_context": True})

        if not symptoms and not all_confirmed:
            gen_out = generate_general_answer(user_text, history, target_lang=lang)
            return jsonify({"type": "info", "reply": gen_out["reply"]})

        result_dict = generate_differential_diagnosis(
            symptoms=symptoms, duration=duration, severity=severity,
            confirmed=all_confirmed, denied=all_denied,
            history=history, target_lang=lang,
            followup_round=followup_round
        )
        return jsonify(result_dict)

    except Exception as e:
        logger.exception(f"Unhandled API error: {e}")
        return jsonify({"type": "info", "reply": "I apologize, but I encountered an internal error. Please try again later."})
