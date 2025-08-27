import csv
from typing import List, Dict

try:
    import snscrape.modules.twitter as sntwitter
except Exception:  # pragma: no cover - environment fallback
    sntwitter = None

import os


class TwitterScraper:
    def __init__(self, backup_path: str = 'backup/twitter_backup.csv'):
        self.backup_path = backup_path

    def fetch(self, query: str, limit: int = 30) -> List[Dict]:
        if not sntwitter:
            return self.load_backup()
        results = []
        try:
            for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
                if i >= limit:
                    break
                results.append({
                    'platform': 'twitter',
                    'username': tweet.user.username if getattr(tweet, 'user', None) else 'unknown',
                    'content': tweet.rawContent if hasattr(tweet, 'rawContent') else getattr(tweet, 'content', ''),
                    'link': f"https://twitter.com/{tweet.user.username}/status/{tweet.id}" if getattr(tweet, 'user', None) else '',
                    'media': [m.fullUrl for m in getattr(tweet, 'media', [])] if getattr(tweet, 'media', None) else []
                })
        except Exception:
            return self.load_backup()
        return results or self.load_backup()

    def load_backup(self) -> List[Dict]:
        data = []
        if not os.path.exists(self.backup_path):
            return data
        with open(self.backup_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row['platform'] = 'twitter'
                row['media'] = []
                data.append(row)
        return data