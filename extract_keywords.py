import spacy
import re


nlp = spacy.load("en_core_web_sm")


SYMPTOMS_KEYWORDS = [
    "fever", "cough", "headache", "nausea", "pain", "chills", "fatigue", "vomiting", "rash", "sore throat",
    "shortness of breath", "dizziness", "runny nose", "diarrhea", "constipation", "itching", "sneezing",
    "muscle pain", "joint pain", "abdominal pain", "back pain", "weakness", "loss of appetite", "sweating",
    "bleeding", "congestion", "chest pain", "cold", "burning sensation", "swelling", "palpitations"
]
DISEASE_KEYWORDS = ["diabetes", "asthma", "covid", "flu", "malaria", "tuberculosis", "hypertension"]


TIME_PATTERNS = [
    r"\b\d{1,2}\s?(am|pm)\b",
    r"\b\d{1,2}:\d{2}\b",
    r"\b(yesterday|today|tonight|tomorrow|last night|last week|next week|this morning|since)\b",
    r"\b\d+\s(days?|weeks?|months?)\s(ago|later)\b"
]

def extract_keywords(text):
    doc = nlp(text.lower())
    symptoms = set()
    diseases = set()
    times = set()

    for token in doc:
        if token.text in SYMPTOM_KEYWORDS:
            symptoms.add(token.text)
        if token.text in DISEASE_KEYWORDS:
            diseases.add(token.text)

    for pattern in TIME_PATTERNS:
        matches = re.findall(pattern, text.lower())
        times.update(matches)

    return {
        "symptoms": list(symptoms),
        "diseases": list(diseases),
        "time_expressions": list(times)
    }
