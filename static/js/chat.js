// ==========================================
// MediMitra Chat Frontend - Full Intelligence
// ==========================================

const chatWindow = document.getElementById("chatWindow");
const msgInput = document.getElementById("msg");
const sendBtn = document.getElementById("send");
const quick = document.getElementById("quickActions");
const triageBtn = document.getElementById("emergencyBtn");
const vaccineSelect = document.getElementById("vaccineSelect");

let lastFollowup = null;
let originalLang = "en";
let messageHistory = []; // {role: "user"|"bot", content: string}

// ==========================================
// MARKDOWN RENDERER
// Converts LLM markdown output to clean HTML
// ==========================================
function renderMarkdown(text) {
  if (!text) return "";

  // 1. Escape HTML entities first (prevent XSS)
  text = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // 2. Bold: **text** or __text__
  text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/__(.*?)__/g, "<strong>$1</strong>");

  // 3. Italic: *text* or _text_
  text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  text = text.replace(/_([^_]+)_/g, "<em>$1</em>");

  // 4. Horizontal Rule: ---
  text = text.replace(/^---$/gm, '<hr class="md-hr">');

  // 5. Split into lines for block-level processing
  const lines = text.split("\n");
  const result = [];
  let inList = false;
  let inNumberedList = false;
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();

    // Headings: ###, ##, #
    if (/^###\s/.test(line)) {
      if (inList) { result.push("</ul>"); inList = false; }
      if (inNumberedList) { result.push("</ol>"); inNumberedList = false; }
      result.push(`<h3 class="md-h3">${line.replace(/^###\s/, "")}</h3>`);
    }
    else if (/^##\s/.test(line)) {
      if (inList) { result.push("</ul>"); inList = false; }
      if (inNumberedList) { result.push("</ol>"); inNumberedList = false; }
      result.push(`<h2 class="md-h2">${line.replace(/^##\s/, "")}</h2>`);
    }
    else if (/^#\s/.test(line)) {
      if (inList) { result.push("</ul>"); inList = false; }
      if (inNumberedList) { result.push("</ol>"); inNumberedList = false; }
      result.push(`<h1 class="md-h1">${line.replace(/^#\s/, "")}</h1>`);
    }
    // Numbered list: "1. item"
    else if (/^\d+\.\s/.test(line)) {
      if (inList) { result.push("</ul>"); inList = false; }
      if (!inNumberedList) { result.push('<ol class="md-list">'); inNumberedList = true; }
      result.push(`<li>${line.replace(/^\d+\.\s/, "")}</li>`);
    }
    // Bullet list: "- item" or "• item"
    else if (/^[-•]\s/.test(line)) {
      if (inNumberedList) { result.push("</ol>"); inNumberedList = false; }
      if (!inList) { result.push('<ul class="md-list">'); inList = true; }
      result.push(`<li>${line.replace(/^[-•]\s/, "")}</li>`);
    }
    // Horizontal Rule (already handled by regex but for line-by-line consistency)
    else if (line === "---" || line === "<hr class=\"md-hr\">") {
      if (inList) { result.push("</ul>"); inList = false; }
      if (inNumberedList) { result.push("</ol>"); inNumberedList = false; }
      if (line === "---") result.push('<hr class="md-hr">');
      else result.push(line);
    }
    // Empty line: close lists, add paragraph break
    else if (line === "") {
      if (inList) { result.push("</ul>"); inList = false; }
      if (inNumberedList) { result.push("</ol>"); inNumberedList = false; }
      result.push('<div class="md-spacer"></div>');
    }
    // Regular text line
    else {
      if (inList) { result.push("</ul>"); inList = false; }
      if (inNumberedList) { result.push("</ol>"); inNumberedList = false; }
      // If it's already a paragraph from a previous step, just push it
      if (line.startsWith("<p") || line.startsWith("<div") || line.startsWith("<hr")) {
        result.push(line);
      } else {
        result.push(`<p class="md-p">${line}</p>`);
      }
    }
    i++;
  }

  // Close any open lists
  if (inList) result.push("</ul>");
  if (inNumberedList) result.push("</ol>");

  return result.join("");
}

// ==========================================
// DISEASE CARD RENDERER
// ==========================================
function renderDiseaseCards(reply) {
  // Look for "### 1. " or "### [Name]" (matches even if no number)
  const diseaseHeaderRegex = /^###\s(\d+\.\s)?(.*)/m;
  if (!diseaseHeaderRegex.test(reply)) return null;

  // Split by "### " headers. 
  // Regex looks for "### " at start of line, optional "1. ", and text.
  const contents = reply.split(/^###\s(?:\d+\.\s)?.*$/m).filter(p => p.trim().length > 0);
  const titles = reply.match(/^###\s(?:\d+\.\s)?(.*)/gm) || [];

  let html = '<div class="disease-container">';

  // Handle intro text if it exists before the first header
  if (!reply.trim().startsWith("###")) {
    const introText = reply.split(/^###/)[0];
    if (introText.trim().length > 0) {
      html += `<div class="diagnosis-intro">${renderMarkdown(introText)}</div>`;
    }
  }

  titles.forEach((fullTitle, idx) => {
    // Clean header markdown
    const titleText = fullTitle.replace(/^###\s(\d+\.\s)?/, "").trim();
    const content = contents[idx] || "";

    html += `
      <div class="disease-box premium-card" style="animation-delay: ${idx * 0.08}s">
        <div class="disease-header">
          <span class="disease-icon">🩺</span>
          <span class="disease-badge">${idx + 1}</span>
          <span class="disease-title">${titleText}</span>
        </div>
        <div class="disease-content">${renderMarkdown(content)}</div>
      </div>`;
  });

  html += "</div>";
  return html;
}

// ==========================================
// INFO CARD RENDERER (generic health tips)
// ==========================================
function renderInfoCard(reply) {
  // Simple check: if reply is empty, skip rendering
  if (!reply || reply.trim().length === 0) return null;
  // Build a premium‑style card similar to disease cards but with an info icon
  const html = `
    <div class="disease-box premium-card" style="animation-delay: 0s; border-left: 5px solid var(--accent);">
      <div class="disease-header">
        <span class="disease-icon">ℹ️</span>
        <span class="disease-badge">Info</span>
        <span class="disease-title">Health Tips</span>
      </div>
      <div class="disease-content">${renderMarkdown(reply)}</div>
    </div>`;
  return html;
}

// ==========================================
// DRUG INFO CARD RENDERER
// Renders a green-accented medicine info card
// ==========================================
function renderDrugCard(reply) {
  // Check for ### header (drug name)
  if (!/^###\s/.test(reply)) return null;

  const titles = reply.match(/^###\s.*/gm) || [];
  const contents = reply.split(/^###\s.*$/m).filter(p => p.trim().length > 0);

  let html = '<div class="drug-container">';

  titles.forEach((fullTitle, idx) => {
    const titleText = fullTitle.replace(/^###\s/, "").trim();
    const content = contents[idx] || "";
    html += `
      <div class="drug-card" style="animation-delay: ${idx * 0.08}s">
        <div class="drug-header">
          <span class="drug-icon">💊</span>
          <span class="drug-name">${titleText}</span>
        </div>
        <div class="drug-content">${renderMarkdown(content)}</div>
      </div>`;
  });

  html += "</div>";
  return html;
}

// ==========================================
// FIRST AID CARD RENDERER
// Renders an orange-accented step-by-step first aid card
// ==========================================
function renderFirstAidCard(reply) {
  // Check for ### First Aid: header
  if (!/^###\s/i.test(reply)) return null;

  const titles = reply.match(/^###\s.*/gm) || [];
  const contents = reply.split(/^###\s.*$/m).filter(p => p.trim().length > 0);

  let html = '<div class="first-aid-container">';

  titles.forEach((fullTitle, idx) => {
    const titleText = fullTitle.replace(/^###\s/, "").trim();
    const content = contents[idx] || "";

    // Detect emergency warning section and style it specially
    const renderedContent = renderMarkdown(content)
      .replace(
        /<p class="md-p"><strong>🚨([^<]*)<\/strong><\/p>/g,
        '<p class="md-p first-aid-emergency"><strong>🚨$1</strong></p>'
      );

    html += `
      <div class="first-aid-card" style="animation-delay: ${idx * 0.08}s">
        <div class="first-aid-header">
          <span class="first-aid-icon">🩹</span>
          <span class="first-aid-title">${titleText}</span>
        </div>
        <div class="first-aid-content">${renderedContent}</div>
      </div>`;
  });

  html += "</div>";
  return html;
}

// ==========================================
// APPEND MESSAGE
// ==========================================
function scrollBottom() {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      chatWindow.scrollTop = chatWindow.scrollHeight;
    });
  });
}

function appendMessage(html, who = "bot", type = "", originalText = "") {
  const wrap = document.createElement("div");
  wrap.className = who === "bot" ? "bot-msg" : "user-msg";
  if (type) wrap.dataset.type = type;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = html;
  wrap.appendChild(bubble);
  chatWindow.appendChild(wrap);
  scrollBottom();

  // Save clean text to history for LLM context
  // Prefer originalText (the raw reply string) over stripping full card HTML
  const plainText = originalText
    ? originalText.replace(/<[^>]*>?/gm, " ").replace(/\s+/g, " ").trim()
    : html.replace(/<[^>]*>?/gm, " ").replace(/\s+/g, " ").trim();
  messageHistory.push({ role: who, content: plainText });

  // Auto-trim history to last 16 entries (8 turns)
  if (messageHistory.length > 16) {
    messageHistory = messageHistory.slice(messageHistory.length - 16);
  }
}

// ==========================================
// TYPING INDICATOR
// ==========================================
function showTyping() {
  const id = "loader-" + Date.now();
  const wrap = document.createElement("div");
  wrap.className = "bot-msg";
  wrap.id = id;
  wrap.innerHTML = `
    <div class="bubble">
      <div class="typing-indicator"><span></span><span></span><span></span></div>
    </div>`;
  chatWindow.appendChild(wrap);
  scrollBottom();
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) chatWindow.removeChild(el);
}

// ==========================================
// RESPONSE HANDLER
// Handles all 7 intent response types
// ==========================================
function handleResponse(data, userText) {
  const type = data.type || "";

  // --- GREETING ---
  if (type === "greeting") {
    appendMessage(renderMarkdown(data.reply), "bot", "greeting", data.reply);
    lastFollowup = null;
    return;
  }

  // --- EMERGENCY / TRIAGE ---
  if (type === "triage") {
    const html = `
      <div class="triage-box">
        <div class="triage-icon">🚨</div>
        <div class="triage-text"><strong>Emergency Alert</strong><br>${renderMarkdown(data.reply)}</div>
      </div>`;
    appendMessage(html, "bot", "triage", data.reply);
    // BUG-003 fix: always clear follow-up state after triage so subsequent
    // messages aren't accidentally treated as answers to the triage question.
    lastFollowup = null;
    return;
  }

  // --- FOLLOW-UP QUESTION ---
  if (type === "followup") {
    const html = `
      <div class="followup-box">
        <div class="followup-icon">❓</div>
        <div>${renderMarkdown(data.question)}</div>
        <div class="followup-btns">
          <button class="followup-btn yes-btn" onclick="answerFollowup('yes', this)">✅ Yes</button>
          <button class="followup-btn no-btn"  onclick="answerFollowup('no', this)">❌ No</button>
        </div>
      </div>`;
    appendMessage(html, "bot", "followup");
    lastFollowup = { question: data.question, answer: "" };
    if (data.detected_lang) originalLang = data.detected_lang;
    return;
  }

  // --- CONTEXT RESET ---
  // BUG-001 frontend fix: when the backend signals reset_context, clear
  // messageHistory so old session symptoms don't bleed into the next query.
  if (data.reset_context) {
    messageHistory = [];
    lastFollowup = null;
  }

  // --- DISEASE CARDS ---
  if (type === "disease") {
    const cardHtml = renderDiseaseCards(data.reply);
    if (cardHtml) {
      appendMessage(cardHtml, "bot", "disease", data.reply);
    } else {
      appendMessage(renderMarkdown(data.reply), "bot", "disease", data.reply);
    }
    lastFollowup = null;
    return;
  }

  // --- DRUG INFO CARD ---
  if (type === "drug_info") {
    const cardHtml = renderDrugCard(data.reply);
    if (cardHtml) {
      appendMessage(cardHtml, "bot", "drug_info", data.reply);
    } else {
      appendMessage(renderMarkdown(data.reply), "bot", "drug_info", data.reply);
    }
    lastFollowup = null;
    return;
  }

  // --- FIRST AID CARD ---
  if (type === "first_aid") {
    const cardHtml = renderFirstAidCard(data.reply);
    if (cardHtml) {
      appendMessage(cardHtml, "bot", "first_aid", data.reply);
    } else {
      appendMessage(renderMarkdown(data.reply), "bot", "first_aid", data.reply);
    }
    lastFollowup = null;
    return;
  }

  // --- INFO / GENERAL Q&A ---
  if (type === "info") {
    const cardHtml = renderInfoCard(data.reply);
    if (cardHtml) {
      appendMessage(cardHtml, "bot", "info", data.reply);
    } else {
      appendMessage(renderMarkdown(data.reply), "bot", "info", data.reply);
    }
    lastFollowup = null;
    return;
  }

  // Fallback
  appendMessage(renderMarkdown(data.reply || "Sorry, I couldn't process that."), "bot");
}

// ==========================================
// FOLLOW-UP YES/NO BUTTONS
// ==========================================
function answerFollowup(answer, btn) {
  // Disable both buttons after click
  const box = btn.closest(".followup-box");
  if (box) box.querySelectorAll(".followup-btn").forEach(b => b.disabled = true);

  // Show user answer as chat bubble
  const label = answer === "yes" ? "Yes" : "No";
  appendMessage(label, "user");

  // Send to server
  sendMessage(label, true);
}

// ==========================================
// CORE SEND FUNCTION
// ==========================================
async function sendMessage(text, isFollowup = false) {
  const typingId = showTyping();

  const payload = {
    text,
    history: messageHistory,
  };

  if (isFollowup && lastFollowup) {
    payload.followup_answer = text;
    payload.followup_question = lastFollowup.question;
    payload.original_lang = originalLang;
  }

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    removeTyping(typingId);
    handleResponse(data, text);
  } catch (err) {
    removeTyping(typingId);
    console.error(err);
    appendMessage("⚠️ Network error. Please try again.", "bot", "error");
  }
}

async function sendForm() {
  if (!msgInput) return;
  const text = msgInput.value.trim();
  if (!text) return;

  // Append user message
  appendMessage(text, "user");
  msgInput.value = "";

  // Auto-resize reset
  msgInput.style.height = "auto";

  // Was this a follow-up reply? (typed answer, not button)
  const isFollowing = !!lastFollowup;
  if (isFollowing) {
    // This typed message IS the follow-up answer
    await sendMessage(text, true);
    lastFollowup = null;
  } else {
    await sendMessage(text, false);
  }
}

// ==========================================
// UTILITIES
// ==========================================
function sendUserMessage(text) {
  if (msgInput) {
    msgInput.value = text;
    sendForm();
  }
}

// ==========================================
// HEALTH TIPS
// ==========================================
async function loadDailyTips() {
  const tipList = document.getElementById("dailyTips");
  if (!tipList) return;
  try {
    const res = await fetch("/api/tips");
    const data = await res.json();
    if (data.tips && data.tips.length > 0) {
      tipList.innerHTML = data.tips.map(tip => `<li>• ${tip}</li>`).join("");
    }
  } catch {
    tipList.innerHTML = "<li>• Stay hydrated and rest well.</li>";
  }
}
loadDailyTips();

// ==========================================
// DYNAMIC QUICK ACTIONS
// Full range: symptoms, diseases, general Q&A
// ==========================================
function loadQuickActions() {
  const actionPool = [
    // Symptom-based
    "I have fever and headache",
    "I have cough and cold",
    "I have stomach pain",
    "I have skin rash",
    "I have joint pain",
    "I feel very tired",
    // General medical Q&A
    "What causes fever?",
    "Difference between cold and flu",
    "Foods to avoid in diabetes",
    "How to reduce blood pressure?",
    "How to improve immunity?",
    "Tips for better sleep",
    // Disease info
    "Tell me about diabetes",
    "What are symptoms of malaria?",
    "How to prevent dengue?",
    // Vaccines
    "What vaccines for newborn?",
    "Vaccine schedule for elderly",
    // 💊 Drug Info
    "What is Paracetamol?",
    "Side effects of Ibuprofen",
    "Uses of Amoxicillin",
    "What is Metformin used for?",
    // 🩹 First Aid
    "First aid for burn",
    "First aid for choking",
    "How to treat a sprain?",
    "What to do for a nosebleed?",
    "First aid for snake bite",
  ];

  const shuffled = actionPool.sort(() => 0.5 - Math.random());
  const selected = shuffled.slice(0, 5);

  if (quick) {
    quick.innerHTML = selected
      .map(text => `<button class="chip">${text}</button>`)
      .join("");
  }
}
loadQuickActions();

// ==========================================
// EVENT LISTENERS
// ==========================================

// Quick action chips
if (quick) {
  quick.addEventListener("click", e => {
    if (e.target.matches(".chip")) sendUserMessage(e.target.textContent);
  });
}

// Vaccine dropdown
if (vaccineSelect) {
  vaccineSelect.addEventListener("change", e => {
    const vaccine = e.target.value;
    if (vaccine) {
      sendUserMessage(`Tell me about the ${vaccine} vaccine – what is it used for and when should it be given?`);
      e.target.value = "";
    }
  });
}

// Emergency triage button
if (triageBtn) {
  triageBtn.addEventListener("click", () => {
    sendUserMessage("I have a medical emergency — I have chest pain and difficulty breathing. What should I do?");
  });
}

// Send button
if (sendBtn) sendBtn.addEventListener("click", () => sendForm());

// Enter key to send (Shift+Enter for newline)
if (msgInput) {
  msgInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendForm();
    }
  });

  // Auto-resize textarea
  msgInput.addEventListener("input", () => {
    msgInput.style.height = "auto";
    msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + "px";
  });
}
