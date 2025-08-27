from typing import Optional, Dict
import random

try:
    from transformers import pipeline
except Exception:  # pragma: no cover
    pipeline = None


class BullyingClassifier:
    """Detects bullying / anti-India sentiment via model or keyword fallback."""

    def __init__(self):
        self._pipe = None
        self.hate_keywords = {"hate","idiot","stupid","loser","terrorist","traitor","anti-india","anti india"}

    def _load(self):
        if pipeline and not self._pipe:
            try:
                self._pipe = pipeline('text-classification', model='Hate-speech-CNERG/dehatebert-mono-english')
            except Exception:
                self._pipe = None

    def classify(self, text: str) -> Optional[Dict]:
        if not text:
            return None
        self._load()
        flagged = False
        score = 0.0
        label = 'bullying_or_hate'
        if self._pipe:
            try:
                res = self._pipe(text[:400])[0]
                # Some models output labels like 'LABEL_0'; we simulate threshold
                raw_label = res.get('label','').lower()
                model_score = res.get('score',0.0)
                if ('hate' in raw_label or 'toxic' in raw_label or 'offensive' in raw_label) and model_score > 0.6:
                    flagged = True
                    score = model_score
            except Exception:
                pass
        if not flagged:
            if any(k in text.lower() for k in self.hate_keywords):
                flagged = True
                score = 0.6 + random.random()*0.3
        return {"label": label, "confidence": float(score), "flagged": flagged}