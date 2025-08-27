from typing import Optional, Dict
import random

try:
    from transformers import pipeline
except Exception:  # pragma: no cover
    pipeline = None


class FakeNewsClassifier:
    """Lightweight fake news heuristic using sentiment as proxy with fallback keywords."""

    def __init__(self):
        self._pipe = None
        self.keywords = {"hoax","fake","propaganda","fabricated","debunked"}

    def _load(self):  # lazy
        if pipeline and not self._pipe:
            try:
                self._pipe = pipeline('text-classification', model='distilbert-base-uncased-finetuned-sst-2-english')
            except Exception:
                self._pipe = None

    def classify(self, text: str) -> Optional[Dict]:
        if not text:
            return None
        self._load()
        score = 0.0
        label = 'fake_news'
        flagged = False
        if self._pipe:
            try:
                res = self._pipe(text[:400])[0]
                # Interpret very negative sentiment on long text as potential fake news indicator (demo purpose)
                if res['label'] == 'NEGATIVE' and res['score'] > 0.85 and len(text) > 80:
                    score = res['score']
                    flagged = True
                else:
                    # fallback heuristic using keywords
                    if any(k in text.lower() for k in self.keywords):
                        score = 0.75 + random.random()*0.2
                        flagged = True
            except Exception:
                pass
        if not self._pipe:  # keyword fallback only
            if any(k in text.lower() for k in self.keywords):
                score = 0.6 + random.random()*0.3
                flagged = True
        if flagged:
            return {"label": label, "confidence": float(score), "flagged": True}
        return {"label": label, "confidence": float(score), "flagged": False}