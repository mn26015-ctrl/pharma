"""
Gemini AI Integration
Cost-optimized question generation with full caching strategy
"""

import os
import json
import hashlib
import time
import re
from typing import List, Dict, Optional, Tuple
from src.database import cache_get, cache_set


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"  # Most cost-effective


# ─── Prompt Templates ─────────────────────────────────────────────────────────

MCQ_PROMPT = """أنت خبير في تعليم الصيدلة. اقرأ النص الصيدلاني التالي وأنشئ أسئلة اختيار من متعدد (MCQ).

النص:
{text}

أنشئ {count} سؤال MCQ بالشروط التالية:
- متنوعة الصعوبة (سهل/متوسط/صعب)
- مرتبطة مباشرة بالنص
- الخيارات الخاطئة معقولة وليست واضحة
- شرح مختصر للإجابة الصحيحة

أجب فقط بـ JSON صالح، بدون أي نص إضافي، بهذا الهيكل:
{
  "questions": [
    {
      "question": "نص السؤال",
      "option_a": "الخيار أ",
      "option_b": "الخيار ب",
      "option_c": "الخيار ج",
      "option_d": "الخيار د",
      "correct_answer": "A",
      "explanation": "شرح مختصر",
      "topic": "الموضوع الرئيسي",
      "difficulty": "easy|medium|hard"
    }
  ]
}"""

TF_PROMPT = """أنت خبير في تعليم الصيدلة. اقرأ النص التالي وأنشئ أسئلة صح/خطأ.

النص:
{text}

أنشئ {count} سؤال صح/خطأ. النصف صحيح والنصف خاطئ مع تعديل طفيف.

أجب فقط بـ JSON صالح:
{
  "questions": [
    {
      "question": "العبارة",
      "correct_answer": "True|False",
      "explanation": "شرح مختصر لماذا صح أو خطأ",
      "topic": "الموضوع",
      "difficulty": "easy|medium|hard"
    }
  ]
}"""

CLINICAL_PROMPT = """أنت أستاذ متخصص في الصيدلة الإكلينيكية. اقرأ النص التالي وأنشئ حالات إكلينيكية.

النص:
{text}

أنشئ {count} حالة إكلينيكية واقعية تختبر التطبيق العملي.

أجب فقط بـ JSON صالح:
{
  "questions": [
    {
      "question": "حالة إكلينيكية: [وصف المريض والأعراض والمعطيات] - ما هو الإجراء/الدواء/التفسير الصحيح؟",
      "option_a": "الخيار أ",
      "option_b": "الخيار ب",
      "option_c": "الخيار ج",
      "option_d": "الخيار د",
      "correct_answer": "A|B|C|D",
      "explanation": "شرح تفصيلي للقرار الإكلينيكي",
      "topic": "الموضوع",
      "difficulty": "medium|hard"
    }
  ]
}"""

FLASHCARD_PROMPT = """أنت خبير في تعليم الصيدلة. اقرأ النص التالي وأنشئ بطاقات مذاكرة (Flashcards).

النص:
{text}

أنشئ {count} بطاقة مذاكرة تغطي المفاهيم الأساسية والأدوية والمصطلحات.

أجب فقط بـ JSON صالح:
{
  "questions": [
    {
      "question": "السؤال/المصطلح/الدواء",
      "correct_answer": "الإجابة/التعريف/الاستخدام",
      "explanation": "معلومة إضافية مهمة",
      "topic": "الموضوع",
      "difficulty": "easy|medium|hard"
    }
  ]
}"""

PROMPTS = {
    "mcq": MCQ_PROMPT,
    "tf": TF_PROMPT,
    "clinical": CLINICAL_PROMPT,
    "flashcard": FLASHCARD_PROMPT,
}

DEFAULT_COUNTS = {
    "mcq": 5,
    "tf": 4,
    "clinical": 2,
    "flashcard": 4,
}


# ─── Gemini API Call ──────────────────────────────────────────────────────────

def call_gemini(prompt: str, max_retries: int = 3) -> Tuple[Optional[str], int]:
    """
    Call Gemini API. Returns (response_text, tokens_used).
    Returns (None, 0) on failure.
    """
    if not GEMINI_API_KEY:
        return None, 0

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)

        for attempt in range(max_retries):
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=4096,
                    )
                )
                text = response.text
                tokens = getattr(response, 'usage_metadata', None)
                token_count = 0
                if tokens:
                    token_count = getattr(tokens, 'total_token_count', 0)
                return text, token_count

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "quota" in err_str.lower():
                    wait = 2 ** attempt * 5
                    time.sleep(wait)
                elif "400" in err_str:
                    return None, 0
                else:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(2)

    except ImportError:
        # Fallback: use requests directly
        return _call_gemini_rest(prompt, max_retries)
    except Exception:
        return None, 0

    return None, 0


def _call_gemini_rest(prompt: str, max_retries: int = 3) -> Tuple[Optional[str], int]:
    """Direct REST API call without SDK"""
    import urllib.request
    import urllib.error

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }).encode('utf-8')

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                text = data['candidates'][0]['content']['parts'][0]['text']
                tokens = data.get('usageMetadata', {}).get('totalTokenCount', 0)
                return text, tokens
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt * 5)
            else:
                return None, 0
        except Exception:
            if attempt == max_retries - 1:
                return None, 0
            time.sleep(2)

    return None, 0


# ─── Parse JSON Response ──────────────────────────────────────────────────────

def parse_questions_response(text: str) -> List[Dict]:
    """Extract JSON from Gemini response"""
    if not text:
        return []

    # Try direct parse first
    text = text.strip()

    # Remove markdown code blocks
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()

    # Try to find JSON object
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return data.get("questions", [])
        except json.JSONDecodeError:
            pass

    # Try array
    arr_match = re.search(r'\[.*\]', text, re.DOTALL)
    if arr_match:
        try:
            return json.loads(arr_match.group())
        except json.JSONDecodeError:
            pass

    return []


# ─── Main Generation Function ─────────────────────────────────────────────────

def generate_questions_for_chunk(
    chunk_text: str,
    chunk_id: int,
    doc_id: int,
    topic: str = "General",
    q_types: Optional[List[str]] = None
) -> List[Dict]:
    """
    Generate all question types for a single chunk.
    Uses cache to avoid repeated API calls.
    Returns list of question dicts ready for DB insertion.
    """
    if q_types is None:
        q_types = ["mcq", "tf", "clinical", "flashcard"]

    chunk_hash = hashlib.md5(chunk_text.encode()).hexdigest()
    all_questions = []

    for q_type in q_types:
        # Check cache first
        cache_key = f"{q_type}:{chunk_hash}"
        cached = cache_get(cache_key)

        if cached:
            questions_data = cached.get("questions", [])
        else:
            # Build prompt
            count = DEFAULT_COUNTS.get(q_type, 4)
            prompt_template = PROMPTS.get(q_type, PROMPTS["mcq"])
            prompt = prompt_template.format(text=chunk_text[:3000], count=count)

            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()

            response_text, tokens = call_gemini(prompt)
            if not response_text:
                continue

            questions_data = parse_questions_response(response_text)
            if questions_data:
                cache_set(cache_key, prompt_hash, {"questions": questions_data}, tokens)

        # Build DB-ready dicts
        for q in questions_data:
            if not q.get("question") or not q.get("correct_answer"):
                continue

            row = {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "type": q_type,
                "question": q.get("question", ""),
                "option_a": q.get("option_a"),
                "option_b": q.get("option_b"),
                "option_c": q.get("option_c"),
                "option_d": q.get("option_d"),
                "correct_answer": str(q.get("correct_answer", "")).strip(),
                "explanation": q.get("explanation", ""),
                "topic": q.get("topic", topic) or topic,
                "difficulty": q.get("difficulty", "medium"),
            }
            all_questions.append(row)

    return all_questions


# ─── Demo Mode (No API Key) ───────────────────────────────────────────────────

DEMO_QUESTIONS = [
    {
        "type": "mcq",
        "question": "ما هو الميكانيزم الأساسي لعمل مثبطات الـ ACE في علاج ارتفاع ضغط الدم؟",
        "option_a": "تثبيط إنزيم المحول للأنجيوتنسين",
        "option_b": "تثبيط مستقبلات الأنجيوتنسين II",
        "option_c": "تثبيط قنوات الكالسيوم",
        "option_d": "تثبيط مستقبلات بيتا",
        "correct_answer": "A",
        "explanation": "مثبطات ACE تعمل بتثبيط إنزيم المحول للأنجيوتنسين، مما يقلل إنتاج أنجيوتنسين II وبالتالي توسع الأوعية وخفض الضغط.",
        "topic": "Cardiovascular Pharmacology",
        "difficulty": "medium",
    },
    {
        "type": "tf",
        "question": "الأسبرين يعمل عن طريق تثبيط إنزيم الـ COX بشكل لا عكسي.",
        "correct_answer": "True",
        "explanation": "الأسبرين يثبط COX-1 و COX-2 بشكل لا عكسي عن طريق الأستلة، على عكس مضادات الالتهاب الأخرى التي تثبطه بشكل عكسي.",
        "topic": "NSAIDs",
        "difficulty": "medium",
    },
    {
        "type": "clinical",
        "question": "حالة إكلينيكية: مريض 65 عام يعاني من السكري النوع 2 وارتفاع ضغط الدم وبروتينية بسيطة. ما هو أفضل خيار لعلاج ارتفاع الضغط؟",
        "option_a": "مثبطات ACE أو ARB",
        "option_b": "حاصرات بيتا",
        "option_c": "مدرات البول الثيازيدية",
        "option_d": "حاصرات ألفا",
        "correct_answer": "A",
        "explanation": "في مرضى السكري مع بروتينية، تُفضَّل مثبطات ACE أو ARB لأنها تحمي الكلى بخفض الضغط داخل الكبيبات وتقليل البروتينية.",
        "topic": "Clinical Pharmacology",
        "difficulty": "hard",
    },
    {
        "type": "flashcard",
        "question": "ما هي الآثار الجانبية الشائعة لمثبطات ACE؟",
        "correct_answer": "السعال الجاف (الأكثر شيوعاً)، فرط بوتاسيوم الدم، احتمالية الأنجيوإديما، انخفاض ضغط الدم.",
        "explanation": "السعال الجاف يحدث بسبب تراكم البراديكينين. في حالة السعال الشديد يُستبدل بـ ARB.",
        "topic": "ACE Inhibitors",
        "difficulty": "easy",
    },
    {
        "type": "mcq",
        "question": "أيٌّ من الآتي هو مضاد حيوي من مجموعة الماكروليدات؟",
        "option_a": "أموكسيسيلين",
        "option_b": "أزيثرومايسين",
        "option_c": "سيبروفلوكساسين",
        "option_d": "دوكسيسيكلين",
        "correct_answer": "B",
        "explanation": "الأزيثرومايسين ينتمي إلى مجموعة الماكروليدات التي تعمل بتثبيط الوحدة 50S الريبوسومية وإيقاف تخليق البروتين في البكتيريا.",
        "topic": "Antibiotics",
        "difficulty": "easy",
    },
]


def get_demo_questions(doc_id: int, chunk_id: int) -> List[Dict]:
    """Return demo questions when no API key is configured"""
    return [
        {**q, "doc_id": doc_id, "chunk_id": chunk_id}
        for q in DEMO_QUESTIONS
    ]
