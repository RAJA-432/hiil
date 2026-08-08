from __future__ import annotations

import time
import uuid
from typing import Any

# ─── Seven dimensions from the Bhagavad Gita ──────────────────────
#
# 1.  nishkama  (2:47) – duty without attachment to results
# 2.  yoga      (2:50) – skill / precision in action
# 3.  guna_karma (4:13) – classification by quality and action
# 4.  akarma    (4:18) – seeing inaction in action, action in inaction
# 5.  uddhara   (6:5)  – self-upliftment
# 6.  shanti    (12:15) – not agitating, not agitated
# 7.  samaarpana (18:66) – surrender to higher wisdom / ethics

BHAGAVAD_GITA_VERSES = {
    "nishkama": {
        "chapter": 2,
        "verse": 47,
        "sanskrit": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन। मा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
        "translation": "You have the right to perform your prescribed duty, but you are not entitled to the fruits of action. Never consider yourself the cause of the results, nor be attached to inaction.",
    },
    "yoga": {
        "chapter": 2,
        "verse": 50,
        "sanskrit": "योगः कर्मसु कौशलम्।",
        "translation": "Yoga is skill in action.",
    },
    "guna_karma": {
        "chapter": 4,
        "verse": 13,
        "sanskrit": "चातुर्वर्ण्यं मया सृष्टं गुणकर्मविभागशः।",
        "translation": "The fourfold order was created by Me according to quality and action.",
    },
    "akarma": {
        "chapter": 4,
        "verse": 18,
        "sanskrit": "कर्मण्यकर्म यः पश्येदकर्मणि च कर्म यः। स बुद्धिमान्मनुष्येषु स युक्तः कृत्स्नकर्मकृत्॥",
        "translation": "He who sees inaction in action and action in inaction is wise among men.",
    },
    "uddhara": {
        "chapter": 6,
        "verse": 5,
        "sanskrit": "उद्धरेदात्मनात्मानं नात्मानमवसादयेत्। आत्मैव ह्यात्मनो बन्धुरात्मैव रिपुरात्मनः॥",
        "translation": "Let a man lift himself by his own self alone, and not degrade himself.",
    },
    "shanti": {
        "chapter": 12,
        "verse": 15,
        "sanskrit": "यस्मान्नोद्विजते लोको लोकान्नोद्विजते च यः। हर्षामर्षभयोद्वेगैर्मुक्तो यः स च मे प्रियः॥",
        "translation": "He by whom the world is not agitated, and who is not agitated by the world, is dear to Me.",
    },
    "samaarpana": {
        "chapter": 18,
        "verse": 66,
        "sanskrit": "सर्वधर्मान्परित्यज्य मामेकं शरणं व्रज। अहं त्वां सर्वपापेभ्यो मोक्षयिष्यामि मा शुचः॥",
        "translation": "Abandon all duties and surrender unto Me alone. Fear not.",
    },
}

REWARD_DIMENSIONS = tuple(BHAGAVAD_GITA_VERSES.keys())

DEFAULT_WEIGHTS = {
    "nishkama": 1.2,
    "yoga": 1.0,
    "guna_karma": 0.8,
    "akarma": 0.7,
    "uddhara": 0.9,
    "shanti": 1.0,
    "samaarpana": 1.1,
}


class RewardEvent:
    def __init__(
        self,
        session_id: str,
        action_type: str,
        context: dict[str, Any] | None = None,
        event_id: str | None = None,
    ):
        self.event_id = event_id or uuid.uuid4().hex[:12]
        self.session_id = session_id
        self.action_type = action_type
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.context = context or {}
        self.scores: dict[str, float] = {}
        self.total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "action_type": self.action_type,
            "timestamp": self.timestamp,
            "scores": self.scores,
            "total": round(self.total, 4),
            "context": self.context,
        }
