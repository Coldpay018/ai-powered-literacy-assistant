import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

import models


ASSESSMENT_STABLE_KEY = "initial-literacy"
ASSESSMENT_VERSION = "initial-literacy-v1"


LANGUAGE_CONTENT = {
    "en": {
        "title": "Initial Literacy Assessment",
        "words": ["book", "river", "school", "market", "garden", "letter", "family", "morning"],
        "sentences": [
            "Ravi reads a book every morning.",
            "The child keeps the pencil on the table.",
            "Mina waters the small plant.",
            "The bus stops near the school.",
            "Asha writes a letter to her friend.",
        ],
        "passages": [
            ("Maya goes to the market with her mother. They buy rice and fresh vegetables.", "What did Maya buy?", "rice and vegetables"),
            ("A small bird sits on the window. It sings when the sun rises.", "When does the bird sing?", "when the sun rises"),
            ("Kiran cleans his desk before he studies. He keeps his books in a neat row.", "What does Kiran do before studying?", "cleans his desk"),
            ("Leela shares her storybook with her younger brother. They read two pages together.", "Who reads with Leela?", "her younger brother"),
            ("The teacher writes three new words on the board. The class reads them aloud.", "Where are the words written?", "on the board"),
        ],
        "typing": ["I can read.", "The sun is bright.", "My school is near my home.", "We learn new words daily."],
        "completion": [
            ("I drink water when I am ____.", ["thirsty"], ["thirsty"]),
            ("A book has many ____.", ["pages"], ["pages"]),
            ("We write with a ____.", ["pen", "pencil"], ["pen", "pencil"]),
            ("The opposite of night is ____.", ["day"], ["day"]),
        ],
        "short": [
            ("Write two sentences about your daily routine.", ["daily", "morning", "school", "read"]),
            ("Write two sentences about your family.", ["family", "home", "mother", "father"]),
            ("Write two sentences about your favourite activity.", ["like", "play", "read", "learn"]),
            ("Write two sentences about your school.", ["school", "teacher", "class", "learn"]),
        ],
    },
    "hi": {
        "title": "प्रारंभिक साक्षरता आकलन",
        "words": ["किताब", "नदी", "स्कूल", "बाजार", "बगीचा", "पत्र", "परिवार", "सुबह"],
        "sentences": [
            "रवि हर सुबह किताब पढ़ता है।",
            "बच्चा पेंसिल मेज पर रखता है।",
            "मीना छोटे पौधे को पानी देती है।",
            "बस स्कूल के पास रुकती है।",
            "आशा अपनी सहेली को पत्र लिखती है।",
        ],
        "passages": [
            ("माया अपनी माँ के साथ बाजार जाती है। वे चावल और ताजी सब्जियां खरीदते हैं।", "माया ने क्या खरीदा?", "चावल और सब्जियां"),
            ("एक छोटी चिड़िया खिड़की पर बैठती है। सूरज निकलने पर वह गाती है।", "चिड़िया कब गाती है?", "सूरज निकलने पर"),
            ("किरण पढ़ने से पहले अपनी मेज साफ करता है। वह किताबें सीधी पंक्ति में रखता है।", "किरण पढ़ने से पहले क्या करता है?", "मेज साफ करता है"),
            ("लीला अपनी कहानी की किताब छोटे भाई के साथ बांटती है। वे दो पन्ने साथ पढ़ते हैं।", "लीला के साथ कौन पढ़ता है?", "छोटा भाई"),
            ("शिक्षक बोर्ड पर तीन नए शब्द लिखते हैं। कक्षा उन्हें जोर से पढ़ती है।", "शब्द कहाँ लिखे हैं?", "बोर्ड पर"),
        ],
        "typing": ["मैं पढ़ सकता हूँ।", "सूरज चमक रहा है।", "मेरा स्कूल घर के पास है।", "हम रोज नए शब्द सीखते हैं।"],
        "completion": [
            ("प्यास लगने पर मैं ____ पीता हूँ।", ["पानी"], ["पानी"]),
            ("किताब में कई ____ होते हैं।", ["पन्ने"], ["पन्ने"]),
            ("हम ____ से लिखते हैं।", ["कलम", "पेंसिल"], ["कलम", "पेंसिल"]),
            ("रात का उल्टा ____ है।", ["दिन"], ["दिन"]),
        ],
        "short": [
            ("अपनी दिनचर्या के बारे में दो वाक्य लिखें।", ["सुबह", "स्कूल", "पढ़", "दिन"]),
            ("अपने परिवार के बारे में दो वाक्य लिखें।", ["परिवार", "घर", "माँ", "पिता"]),
            ("अपनी पसंदीदा गतिविधि के बारे में दो वाक्य लिखें।", ["पसंद", "खेल", "पढ़", "सीख"]),
            ("अपने स्कूल के बारे में दो वाक्य लिखें।", ["स्कूल", "शिक्षक", "कक्षा", "सीख"]),
        ],
    },
    "ta": {
        "title": "தொடக்க எழுத்தறிவு மதிப்பீடு",
        "words": ["புத்தகம்", "நதி", "பள்ளி", "சந்தை", "தோட்டம்", "கடிதம்", "குடும்பம்", "காலை"],
        "sentences": [
            "ரவி ஒவ்வொரு காலையும் புத்தகம் வாசிக்கிறான்.",
            "குழந்தை பென்சிலை மேசையில் வைக்கிறது.",
            "மீனா சிறிய செடிக்கு தண்ணீர் ஊற்றுகிறாள்.",
            "பேருந்து பள்ளி அருகில் நிற்கிறது.",
            "ஆஷா தனது தோழிக்கு கடிதம் எழுதுகிறாள்.",
        ],
        "passages": [
            ("மாயா தன் அம்மாவுடன் சந்தைக்கு செல்கிறாள். அவர்கள் அரிசியும் பச்சை காய்கறிகளும் வாங்குகிறார்கள்.", "மாயா என்ன வாங்கினாள்?", "அரிசி மற்றும் காய்கறிகள்"),
            ("ஒரு சிறிய பறவை ஜன்னலில் உட்கார்கிறது. சூரியன் உதிக்கும் போது அது பாடுகிறது.", "பறவை எப்போது பாடுகிறது?", "சூரியன் உதிக்கும் போது"),
            ("கிரண் படிப்பதற்கு முன் மேசையை சுத்தம் செய்கிறான். அவன் புத்தகங்களை ஒழுங்காக வைக்கிறான்.", "கிரண் படிப்பதற்கு முன் என்ன செய்கிறான்?", "மேசையை சுத்தம் செய்கிறான்"),
            ("லீலா தன் கதைப்புத்தகத்தை தம்பியுடன் பகிர்கிறாள். அவர்கள் இரண்டு பக்கங்களை சேர்ந்து வாசிக்கிறார்கள்.", "லீலாவுடன் யார் வாசிக்கிறார்?", "தம்பி"),
            ("ஆசிரியர் பலகையில் மூன்று புதிய சொற்களை எழுதுகிறார். வகுப்பு அவற்றை சத்தமாக வாசிக்கிறது.", "சொற்கள் எங்கே எழுதப்பட்டுள்ளன?", "பலகையில்"),
        ],
        "typing": ["நான் வாசிக்க முடியும்.", "சூரியன் பிரகாசமாக உள்ளது.", "என் பள்ளி என் வீட்டிற்கு அருகில் உள்ளது.", "நாம் தினமும் புதிய சொற்கள் கற்கிறோம்."],
        "completion": [
            ("தாகமாக இருக்கும் போது நான் ____ குடிப்பேன்.", ["தண்ணீர்"], ["தண்ணீர்"]),
            ("புத்தகத்தில் பல ____ உள்ளன.", ["பக்கங்கள்"], ["பக்கங்கள்"]),
            ("நாம் ____ கொண்டு எழுதுகிறோம்.", ["பேனா", "பென்சில்"], ["பேனா", "பென்சில்"]),
            ("இரவு என்பதற்கு எதிர் ____.", ["பகல்"], ["பகல்"]),
        ],
        "short": [
            ("உங்கள் தினசரி செயல்களை பற்றி இரண்டு வாக்கியங்கள் எழுதுங்கள்.", ["காலை", "பள்ளி", "வாசி", "நாள்"]),
            ("உங்கள் குடும்பத்தை பற்றி இரண்டு வாக்கியங்கள் எழுதுங்கள்.", ["குடும்பம்", "வீடு", "அம்மா", "அப்பா"]),
            ("உங்களுக்கு பிடித்த செயல்பாட்டைப் பற்றி இரண்டு வாக்கியங்கள் எழுதுங்கள்.", ["பிடிக்கும்", "விளையாடு", "வாசி", "கல்"]),
            ("உங்கள் பள்ளியை பற்றி இரண்டு வாக்கியங்கள் எழுதுங்கள்.", ["பள்ளி", "ஆசிரியர்", "வகுப்பு", "கல்"]),
        ],
    },
    "te": {
        "title": "ప్రారంభ అక్షరాస్యత అంచనా",
        "words": ["పుస్తకం", "నది", "పాఠశాల", "బజారు", "తోట", "లేఖ", "కుటుంబం", "ఉదయం"],
        "sentences": [
            "రవి ప్రతి ఉదయం పుస్తకం చదువుతాడు.",
            "బిడ్డ పెన్సిల్‌ను బల్లపై పెడుతుంది.",
            "మీనా చిన్న మొక్కకు నీరు పోస్తుంది.",
            "బస్సు పాఠశాల దగ్గర ఆగుతుంది.",
            "ఆశ తన స్నేహితురాలికి లేఖ రాస్తుంది.",
        ],
        "passages": [
            ("మాయ తన తల్లితో బజారుకు వెళ్తుంది. వారు బియ్యం మరియు తాజా కూరగాయలు కొనుగోలు చేస్తారు.", "మాయ ఏమి కొనింది?", "బియ్యం మరియు కూరగాయలు"),
            ("ఒక చిన్న పక్షి కిటికీపై కూర్చుంది. సూర్యుడు ఉదయించినప్పుడు అది పాడుతుంది.", "పక్షి ఎప్పుడు పాడుతుంది?", "సూర్యుడు ఉదయించినప్పుడు"),
            ("కిరణ్ చదవడానికి ముందు తన బల్లను శుభ్రం చేస్తాడు. అతను పుస్తకాలను వరుసగా పెడతాడు.", "కిరణ్ చదవడానికి ముందు ఏమి చేస్తాడు?", "బల్లను శుభ్రం చేస్తాడు"),
            ("లీలా తన కథా పుస్తకాన్ని తమ్ముడితో పంచుకుంటుంది. వారు రెండు పేజీలు కలిసి చదువుతారు.", "లీలాతో ఎవరు చదువుతారు?", "తమ్ముడు"),
            ("ఉపాధ్యాయుడు బోర్డుపై మూడు కొత్త పదాలు రాస్తారు. తరగతి వాటిని గట్టిగా చదువుతుంది.", "పదాలు ఎక్కడ రాయబడ్డాయి?", "బోర్డుపై"),
        ],
        "typing": ["నేను చదవగలను.", "సూర్యుడు ప్రకాశంగా ఉన్నాడు.", "నా పాఠశాల నా ఇంటి దగ్గర ఉంది.", "మనం రోజూ కొత్త పదాలు నేర్చుకుంటాం."],
        "completion": [
            ("దాహంగా ఉన్నప్పుడు నేను ____ తాగుతాను.", ["నీరు"], ["నీరు"]),
            ("పుస్తకంలో చాలా ____ ఉంటాయి.", ["పేజీలు"], ["పేజీలు"]),
            ("మనం ____ తో రాస్తాము.", ["పెన్", "పెన్సిల్"], ["పెన్", "పెన్సిల్"]),
            ("రాత్రికి వ్యతిరేక పదం ____.", ["పగలు"], ["పగలు"]),
        ],
        "short": [
            ("మీ రోజువారీ పనుల గురించి రెండు వాక్యాలు రాయండి.", ["ఉదయం", "పాఠశాల", "చదువు", "రోజు"]),
            ("మీ కుటుంబం గురించి రెండు వాక్యాలు రాయండి.", ["కుటుంబం", "ఇల్లు", "అమ్మ", "నాన్న"]),
            ("మీకు ఇష్టమైన పనిపై రెండు వాక్యాలు రాయండి.", ["ఇష్టం", "ఆట", "చదువు", "నేర్చు"]),
            ("మీ పాఠశాల గురించి రెండు వాక్యాలు రాయండి.", ["పాఠశాల", "ఉపాధ్యాయుడు", "తరగతి", "నేర్చు"]),
        ],
    },
}


def _options(correct: str, distractors: list[str]):
    values = [correct, *distractors[:3]]
    return [{"id": f"option_{index + 1}", "text": value} for index, value in enumerate(values)]


def _sentence_distractors(sentence: str):
    cleaned = sentence.strip()
    words = cleaned.rstrip(".।").split()
    if len(words) < 4:
        return [cleaned.rstrip(".।"), words[0] if words else cleaned, " ".join(reversed(words))]

    first = " ".join(words[1:])
    second = " ".join([words[1], words[0], *words[2:]])
    third = " ".join([*words[:-2], words[-1], words[-2]])
    suffix = "।" if cleaned.endswith("।") else "."
    return [f"{first}{suffix}", f"{second}{suffix}", f"{third}{suffix}"]


def _reading_distractors(language: str, passage_index: int, words: list[str]):
    english = [
        ["a book", "a letter", "flowers"],
        ["in the evening", "when the class starts", "after lunch"],
        ["writes a letter", "buys vegetables", "waters a plant"],
        ["her teacher", "the shopkeeper", "the bus driver"],
        ["in a book", "on the desk", "near the window"],
    ]
    if language == "en":
        return english[passage_index]
    return [words[passage_index], words[(passage_index + 4) % len(words)], words[(passage_index + 5) % len(words)]]


def _validate_option_question(question: dict):
    if question["question_type"] not in {"reading_mcq", "mcq"}:
        return

    options = question.get("options") or []
    if len(options) < 3:
        raise ValueError(f"{question['stable_key']} must have at least three options")

    option_ids = [option.get("id") for option in options]
    if len(option_ids) != len(set(option_ids)):
        raise ValueError(f"{question['stable_key']} has duplicate option IDs")

    correct_option_id = question["correct"].get("correct_option_id")
    option_by_id = {option["id"]: option["text"] for option in options}
    if correct_option_id not in option_by_id:
        raise ValueError(f"{question['stable_key']} is missing its correct option")

    prompt = question.get("prompt", "").strip()
    if not prompt:
        raise ValueError(f"{question['stable_key']} has an empty prompt")

    correct_text = option_by_id[correct_option_id]
    if question.get("skill_tag") == "sentence meaning" and correct_text in prompt:
        raise ValueError(f"{question['stable_key']} prompt reveals the complete correct answer")

    passage = question.get("passage")
    if passage and question["section"] == "reading" and question["language"] == "en":
        answer_tokens = [token for token in correct_text.lower().split() if len(token) > 2]
        if answer_tokens and not any(token in passage.lower() for token in answer_tokens):
            raise ValueError(f"{question['stable_key']} answer is not supported by its passage")


def _question_payload(question: dict):
    return {
        "stable_key": question["stable_key"],
        "assessment_version": ASSESSMENT_VERSION,
        "section": question["section"],
        "language": question["language"],
        "difficulty": question["difficulty"],
        "question_type": question["question_type"],
        "passage": question.get("passage"),
        "prompt": question["prompt"],
        "options_json": json.dumps(question.get("options"), ensure_ascii=False) if question.get("options") else None,
        "correct_answer_json": json.dumps(question["correct"], ensure_ascii=False),
        "scoring_config_json": json.dumps(question.get("scoring", {}), ensure_ascii=False),
        "marks": question["marks"],
        "skill_tag": question["skill_tag"],
        "is_active": True,
        "updated_at": datetime.now(timezone.utc),
    }


def build_question_bank():
    bank = []
    for language, content in LANGUAGE_CONTENT.items():
        words = content["words"]
        sentences = content["sentences"]
        passages = content["passages"]
        word_meaning_prompts = [
            "Choose the word for something people read.",
            "Choose the word for flowing water.",
            "Choose the word for a place to learn.",
            "Choose the word for a place where people buy things.",
            "Choose the word for a place with plants.",
            "Choose the word for a written message.",
            "Choose the word that means a group of related people living together.",
            "Choose the word for the early part of the day.",
        ]

        for index in range(5):
            correct = words[index]
            bank.append({
                "stable_key": f"{language}-reading-beginner-{index + 1}",
                "language": language,
                "section": "reading",
                "difficulty": "beginner",
                "question_type": "reading_mcq",
                "prompt": word_meaning_prompts[index],
                "options": _options(correct, [words[(index + 1) % len(words)], words[(index + 2) % len(words)], words[(index + 3) % len(words)]]),
                "correct": {"correct_option_id": "option_1"},
                "marks": 2,
                "skill_tag": "word recognition",
            })

        for index in range(5):
            passage, prompt, answer = passages[index]
            bank.append({
                "stable_key": f"{language}-reading-intermediate-{index + 1}",
                "language": language,
                "section": "reading",
                "difficulty": "intermediate",
                "question_type": "reading_mcq",
                "passage": passage,
                "prompt": prompt,
                "options": _options(answer, _reading_distractors(language, index, words)),
                "correct": {"correct_option_id": "option_1"},
                "marks": 3,
                "skill_tag": "literal comprehension",
            })

        for index in range(3):
            passage, prompt, answer = passages[index]
            bank.append({
                "stable_key": f"{language}-reading-advanced-{index + 1}",
                "language": language,
                "section": "reading",
                "difficulty": "advanced",
                "question_type": "reading_mcq",
                "passage": passage,
                "prompt": prompt,
                "options": _options(answer, _reading_distractors(language, index, words)),
                "correct": {"correct_option_id": "option_1"},
                "marks": 4,
                "skill_tag": "passage comprehension",
            })

        for index, text in enumerate(content["typing"]):
            bank.append({
                "stable_key": f"{language}-typing-beginner-{index + 1}",
                "language": language,
                "section": "typing",
                "difficulty": "beginner",
                "question_type": "copy_typing",
                "prompt": text,
                "correct": {"reference_text": text},
                "marks": 5,
                "skill_tag": "copy accuracy",
            })

        for index, (prompt, accepted, keywords) in enumerate(content["completion"]):
            bank.append({
                "stable_key": f"{language}-typing-intermediate-{index + 1}",
                "language": language,
                "section": "typing",
                "difficulty": "intermediate",
                "question_type": "sentence_completion",
                "prompt": prompt,
                "correct": {"accepted_answers": accepted, "required_keywords": keywords},
                "marks": 6,
                "skill_tag": "sentence completion",
            })

        for index, (prompt, keywords) in enumerate(content["short"]):
            bank.append({
                "stable_key": f"{language}-typing-advanced-{index + 1}",
                "language": language,
                "section": "typing",
                "difficulty": "advanced",
                "question_type": "short_response",
                "prompt": prompt,
                "correct": {"required_keywords": keywords, "minimum_words": 6},
                "marks": 10,
                "skill_tag": "short response",
            })

        mcq_items = [
            ("Choose the word for a place to learn.", 2),
            ("Choose the word that means a group of related people living together.", 6),
            ("Choose the word used for reading.", 0),
            ("Choose the word for the early part of the day.", 7),
            ("Choose the word for a written message.", 5),
            ("Choose the word for a place with plants.", 4),
            ("Choose the word for flowing water.", 1),
            ("Choose the word for a place where people buy things.", 3),
        ]
        for index, (prompt, correct_index) in enumerate(mcq_items):
            localized_correct = words[correct_index]
            distractors = [word for word_index, word in enumerate(words) if word_index != correct_index]
            bank.append({
                "stable_key": f"{language}-mcq-beginner-{index + 1}",
                "language": language,
                "section": "mcq",
                "difficulty": "beginner",
                "question_type": "mcq",
                "prompt": prompt,
                "options": _options(localized_correct, distractors[:3]),
                "correct": {"correct_option_id": "option_1"},
                "marks": 2,
                "skill_tag": "vocabulary",
            })

        for index in range(8):
            bank.append({
                "stable_key": f"{language}-mcq-intermediate-{index + 1}",
                "language": language,
                "section": "mcq",
                "difficulty": "intermediate",
                "question_type": "mcq",
                "prompt": "Choose the complete sentence.",
                "options": _options(sentences[index % len(sentences)], _sentence_distractors(sentences[index % len(sentences)])),
                "correct": {"correct_option_id": "option_1"},
                "marks": 3,
                "skill_tag": "sentence meaning",
            })

        for index in range(5):
            passage, prompt, answer = passages[index]
            bank.append({
                "stable_key": f"{language}-mcq-advanced-{index + 1}",
                "language": language,
                "section": "mcq",
                "difficulty": "advanced",
                "question_type": "mcq",
                "passage": passage,
                "prompt": prompt,
                "options": _options(answer, _reading_distractors(language, index, words)),
                "correct": {"correct_option_id": "option_1"},
                "marks": 4,
                "skill_tag": "basic comprehension",
            })
    for question in bank:
        _validate_option_question(question)
    return bank


def seed_initial_assessment(db: Session) -> dict[str, int]:
    assessment = (
        db.query(models.Assessment)
        .filter(models.Assessment.version == ASSESSMENT_VERSION)
        .first()
    )
    if not assessment:
        assessment = models.Assessment(
            stable_key=ASSESSMENT_STABLE_KEY,
            title="Initial Literacy Assessment",
            version=ASSESSMENT_VERSION,
            is_active=True,
        )
        db.add(assessment)
        db.flush()

    created = 0
    updated = 0
    for question in build_question_bank():
        payload = _question_payload(question)
        existing = (
            db.query(models.AssessmentQuestion)
            .filter(models.AssessmentQuestion.stable_key == question["stable_key"])
            .first()
        )
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            updated += 1
        else:
            db.add(models.AssessmentQuestion(assessment_id=assessment.id, **payload))
            created += 1

    db.commit()
    return {"created": created, "updated": updated}
