import csv
from typing import List, Dict
import os

try:
    import instaloader
except Exception:  # pragma: no cover
    instaloader = None


class InstagramScraper:
    def __init__(self, backup_path: str = 'backup/instagram_backup.csv'):
        self.backup_path = backup_path

    def fetch(self, hashtag: str, limit: int = 20) -> List[Dict]:
        if not instaloader:
            return self.load_backup()
        posts = []
        try:
            L = instaloader.Instaloader(download_pictures=False, save_metadata=False, download_comments=False, quiet=True)
            hashtag_obj = instaloader.Hashtag.from_name(L.context, hashtag)
            for i, post in enumerate(hashtag_obj.get_posts()):
                if i >= limit:
                    break
                posts.append({
                    'platform': 'instagram',
                    'username': post.owner_username,
                    'content': post.caption or '',
                    'link': f"https://www.instagram.com/p/{post.shortcode}/",
                    'media': [post.url] if hasattr(post, 'url') else []
                })
        except Exception:
            return self.load_backup()
        return posts or self.load_backup()

    def load_backup(self) -> List[Dict]:
        data = []
        if not os.path.exists(self.backup_path):
            return data
        with open(self.backup_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row['platform'] = 'instagram'
                row['media'] = []
                data.append(row)
        return data