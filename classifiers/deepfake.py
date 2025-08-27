from typing import Optional, Dict, List
import hashlib
import random


class DeepfakeClassifier:
    """Mock deepfake detector using image URL/content hashing heuristics (demo)."""

    def __init__(self):
        self.suspect_hash_prefixes = {"00", "ff", "aa"}

    def classify(self, media_urls: List[str]) -> Optional[Dict]:
        if not media_urls:
            return None
        flagged = False
        confidence = 0.0
        for url in media_urls:
            h = hashlib.sha256(url.encode()).hexdigest()
            if h[:2] in self.suspect_hash_prefixes:
                flagged = True
                confidence = max(confidence, 0.7 + random.random()*0.25)
        # Random small probability of detection for demo diversity
        if not flagged and random.random() < 0.05:
            flagged = True
            confidence = 0.65 + random.random()*0.2
        return {"label": "deepfake", "confidence": confidence, "flagged": flagged}