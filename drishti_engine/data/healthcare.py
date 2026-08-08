"""Curated general-education health index for the Drishti Engine server.

Entries cover common conditions, symptoms, and medications with plain,
factual, non-diagnostic summaries plus first-line self-care guidance and
clear signs to seek professional care. All content is educational only and
must never be treated as medical advice, diagnosis, or dosing instructions.
"""

from __future__ import annotations

HEALTHCARE_INDEX: list[dict] = [
    {
        "id": "headache",
        "name": "Headache",
        "category": "symptoms",
        "aliases": ["head ache", "head pain", "tension headache", "head hurts"],
        "summary": (
            "Headache is pain in any region of the head that can range from mild to severe "
            "and may be tension-type, migraine, or another kind."
        ),
        "common_signs": ["Dull ache or tightness in the head", "Pressure around the forehead or temples"],
        "self_care": [
            "Rest in a quiet, dimly lit room",
            "Drink water and avoid skipping meals",
            "Apply a cool or warm cloth to the forehead",
        ],
        "when_to_seek": [
            "A sudden, severe, or 'worst ever' headache",
            "Headache with stiff neck, fever, confusion, or slurred speech",
            "Headache after a head injury",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "migraine",
        "name": "Migraine",
        "category": "conditions",
        "aliases": ["migraine headache", "migraine attack"],
        "summary": (
            "Migraine is a recurring neurological condition marked by moderate-to-severe "
            "throbbing headache, often on one side, sometimes with nausea and sensitivity "
            "to light or sound."
        ),
        "common_signs": [
            "Throbbing or pulsing pain, often one-sided",
            "Nausea or vomiting",
            "Sensitivity to light, sound, or smells",
        ],
        "self_care": [
            "Rest in a quiet, dark room",
            "Stay hydrated and keep a consistent sleep schedule",
            "Identify and avoid personal triggers",
        ],
        "when_to_seek": [
            "Headache attacks that are frequent or disabling",
            "New symptoms such as weakness, vision changes, or confusion",
            "A sudden severe headache unlike your usual pattern",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "common-cold",
        "name": "Common cold",
        "category": "conditions",
        "aliases": ["cold", "common cold", "viral cold"],
        "summary": (
            "The common cold is a mild viral infection of the nose and throat that usually "
            "resolves on its own within a week or two."
        ),
        "common_signs": [
            "Runny or blocked nose",
            "Sneezing and sore throat",
            "Mild cough, congestion, or low-grade fever",
        ],
        "self_care": [
            "Rest and drink plenty of fluids",
            "Use a humidifier or inhale steam for congestion",
            "Consider honey for cough in adults (not for infants under one)",
        ],
        "when_to_seek": [
            "Symptoms lasting more than about 10 days",
            "Difficulty breathing, chest pain, or very high fever",
            "Symptoms that worsen after seeming to improve",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "influenza",
        "name": "Influenza (flu)",
        "category": "conditions",
        "aliases": ["flu", "influenza", "seasonal flu"],
        "summary": (
            "Influenza is a contagious respiratory illness caused by influenza viruses, "
            "typically with abrupt onset of fever, muscle aches, and fatigue."
        ),
        "common_signs": [
            "Sudden fever and chills",
            "Muscle aches, fatigue, and headache",
            "Dry cough, sore throat, or runny nose",
        ],
        "self_care": [
            "Rest and stay home to avoid spreading the infection",
            "Drink fluids regularly to stay hydrated",
            "Manage fever with cool fluids and light clothing",
        ],
        "when_to_seek": [
            "Difficulty breathing or shortness of breath",
            "Persistent chest pain or confusion",
            "High fever not improving, especially in young children, older adults, or pregnancy",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "high-blood-pressure",
        "name": "High blood pressure (hypertension)",
        "category": "conditions",
        "aliases": ["hypertension", "high blood pressure", "raised blood pressure"],
        "summary": (
            "High blood pressure is a common condition in which the force of blood against "
            "artery walls is too high, often with no obvious symptoms."
        ),
        "common_signs": [
            "Usually no symptoms for a long time",
            "Occasional headaches or nosebleeds in severe cases",
        ],
        "self_care": [
            "Reduce salt intake and eat a balanced diet",
            "Stay physically active and maintain a healthy weight",
            "Limit alcohol and avoid tobacco",
        ],
        "when_to_seek": [
            "Very high readings as advised by a professional",
            "Chest pain, shortness of breath, severe headache, or vision changes",
            "Ongoing concern about home blood-pressure readings",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "type-2-diabetes",
        "name": "Type 2 diabetes",
        "category": "conditions",
        "aliases": ["diabetes", "type 2 diabetes", "type ii diabetes"],
        "summary": (
            "Type 2 diabetes is a chronic condition where the body does not use insulin "
            "effectively, leading to raised blood sugar levels."
        ),
        "common_signs": [
            "Increased thirst and frequent urination",
            "Unexplained fatigue or blurred vision",
            "Slow-healing sores or frequent infections",
        ],
        "self_care": [
            "Follow a balanced diet and watch portion sizes",
            "Aim for regular physical activity as advised",
            "Monitor blood sugar and attend check-ups as recommended",
        ],
        "when_to_seek": [
            "Symptoms of very high blood sugar such as confusion or severe dehydration",
            "Persistent high readings or repeated hypoglycemia",
            "New numbness, tingling, or wounds that will not heal",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "fever",
        "name": "Fever",
        "category": "symptoms",
        "aliases": ["pyrexia", "high temperature", "temperature", "feeling hot"],
        "summary": (
            "Fever is a temporary rise in body temperature, usually a normal immune response "
            "to infection, that typically improves within a few days."
        ),
        "common_signs": [
            "Raised body temperature and feeling hot to touch",
            "Shivering, sweating, or flushed skin",
        ],
        "self_care": [
            "Rest and drink plenty of fluids",
            "Wear light clothing and keep the room comfortable",
            "Use over-the-counter fever medicine only as directed by a professional",
        ],
        "when_to_seek": [
            "Fever in an infant under three months",
            "Fever lasting more than a few days or very high",
            "Fever with stiff neck, severe pain, rash, confusion, or trouble breathing",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "cough",
        "name": "Cough",
        "category": "symptoms",
        "aliases": ["coughing", "dry cough", "productive cough", "coughing up phlegm"],
        "summary": (
            "A cough is the body's reflex to clear the airways of mucus, irritants, or foreign "
            "particles, and most acute coughs resolve within a few weeks."
        ),
        "common_signs": ["Frequent coughing fits", "Sore chest or throat from coughing", "Cough with mucus (phlegm)"],
        "self_care": [
            "Drink warm fluids and keep airways moist",
            "Rest and avoid smoke or other irritants",
            "Honey in warm water may soothe a cough in adults",
        ],
        "when_to_seek": [
            "Coughing up blood or blood-stained mucus",
            "Shortness of breath, chest pain, or wheezing",
            "Cough lasting more than three weeks or with high fever",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "sore-throat",
        "name": "Sore throat",
        "category": "symptoms",
        "aliases": ["throat pain", "pharyngitis", "scratchy throat", "throat hurts"],
        "summary": (
            "A sore throat is pain, scratchiness, or irritation of the throat that often "
            "worsens when swallowing, commonly due to viral infection."
        ),
        "common_signs": [
            "Pain or scratchiness in the throat",
            "Pain that worsens when swallowing or talking",
            "Mild swelling of the tonsils",
        ],
        "self_care": [
            "Gargle with warm salt water",
            "Drink warm fluids and use lozenges or honey",
            "Rest the voice and avoid smoky or dry air",
        ],
        "when_to_seek": [
            "Difficulty swallowing, breathing, or opening the mouth",
            "High fever, drooling, or a rash",
            "Severe throat pain or a muffled voice",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "abdominal-pain",
        "name": "Abdominal pain",
        "category": "symptoms",
        "aliases": ["stomach ache", "stomach pain", "belly pain", "cramps", "tummy ache"],
        "summary": (
            "Abdominal pain is discomfort in the area between the chest and pelvis and is "
            "usually brief and harmless, though it can occasionally signal a serious issue."
        ),
        "common_signs": ["Cramping or dull ache in the belly", "Bloating, nausea, or gas"],
        "self_care": [
            "Eat small, bland meals and stay hydrated",
            "Rest and apply a warm compress to the area",
            "Avoid heavy or spicy foods until symptoms settle",
        ],
        "when_to_seek": [
            "Severe, sudden, or worsening pain",
            "Pain with vomiting blood, blood in stool, or fever",
            "Pain during pregnancy or after an injury",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "dehydration",
        "name": "Dehydration",
        "category": "conditions",
        "aliases": ["dehydrated", "fluid loss", "low fluids"],
        "summary": (
            "Dehydration occurs when the body loses more fluid than it takes in and does not "
            "have enough water to function normally."
        ),
        "common_signs": [
            "Thirst and a dry mouth",
            "Dark urine or passing urine less often",
            "Dizziness, fatigue, or headache",
        ],
        "self_care": [
            "Drink water or oral rehydration fluids regularly",
            "Avoid caffeinated or sugary drinks in excess",
            "Rest in a cool place and rehydrate during or after exercise",
        ],
        "when_to_seek": [
            "Severe thirst, little or no urine, or very dark urine",
            "Confusion, fainting, or rapid heartbeat",
            "Dehydration in an infant, older adult, or with persistent vomiting",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "ibuprofen",
        "name": "Ibuprofen",
        "category": "medications",
        "aliases": ["advil", "motrin", "nsaid", "ibuprofen"],
        "summary": (
            "Ibuprofen is a non-steroidal anti-inflammatory medicine used to relieve pain, "
            "fever, and inflammation. It should be used only as directed by a professional."
        ),
        "common_signs": ["Used for mild to moderate pain", "Used to reduce fever", "Reduces inflammation"],
        "self_care": [
            "Take exactly as instructed on the label or by a professional",
            "Take with food or milk to reduce stomach upset",
            "Do not combine with other NSAIDs unless advised",
        ],
        "when_to_seek": [
            "Stomach pain, black stools, or signs of an allergic reaction",
            "Asthma, kidney problems, or stomach ulcers before taking it",
            "Concern about drug interactions or correct dosing",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "paracetamol",
        "name": "Paracetamol (acetaminophen)",
        "category": "medications",
        "aliases": ["acetaminophen", "tylenol", "panadol", "paracetamol"],
        "summary": (
            "Paracetamol (acetaminophen) is a common pain reliever and fever reducer. "
            "Overdose can be harmful, so it must be used strictly as directed."
        ),
        "common_signs": ["Used for mild to moderate pain", "Used to reduce fever"],
        "self_care": [
            "Take exactly as instructed on the label or by a professional",
            "Do not exceed the maximum daily dose",
            "Do not combine with other products containing paracetamol",
        ],
        "when_to_seek": [
            "Signs of an overdose such as nausea, vomiting, or jaundice",
            "Liver disease or regular heavy alcohol use before taking it",
            "Symptoms that do not improve or any dosing uncertainty",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
    {
        "id": "low-blood-pressure",
        "name": "Low blood pressure (hypotension)",
        "category": "conditions",
        "aliases": ["hypotension", "low blood pressure", "low bp"],
        "summary": (
            "Low blood pressure is when the force of blood against artery walls is lower "
            "than normal; it may cause symptoms only when blood flow to organs is reduced."
        ),
        "common_signs": [
            "Dizziness or lightheadedness, especially on standing",
            "Fainting or blurry vision",
            "Fatigue, nausea, or poor concentration",
        ],
        "self_care": [
            "Stand up slowly from sitting or lying down",
            "Drink enough fluids throughout the day",
            "Eat regular meals and avoid prolonged standing",
        ],
        "when_to_seek": [
            "Fainting, severe dizziness, or confusion",
            "Signs of shock such as cold, clammy skin or weak pulse",
            "Blood loss, vomiting, or an underlying medical condition",
        ],
        "source": "General public-health reference (NHS/Mayo Clinic style)",
    },
]
