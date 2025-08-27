import sys
import os
import time
from datetime import datetime
from tabulate import tabulate

from scrapers.twitter_scraper import TwitterScraper
from scrapers.instagram_scraper import InstagramScraper
from classifiers.fake_news import FakeNewsClassifier
from classifiers.deepfake import DeepfakeClassifier
from classifiers.bullying import BullyingClassifier
from storage.database import Database
from storage.reports import ReportGenerator


def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def pause():
    input("\nPress Enter to continue...")


class CyberShieldCLI:
    def __init__(self):
        self.twitter_scraper = TwitterScraper()
        self.instagram_scraper = InstagramScraper()
        self.fake_news_classifier = FakeNewsClassifier()
        self.deepfake_classifier = DeepfakeClassifier()
        self.bullying_classifier = BullyingClassifier()
        self.db = Database(db_path='cybershield.db')
        self.reporter = ReportGenerator(self.db)
        self.flagged_session = []  # in-memory for current run

    def run(self):
        while True:
            clear()
            print("=" * 50)
            print(" CyberShield CLI")
            print("=" * 50)
            print("1) Twitter Analysis")
            print("2) Instagram Analysis")
            print("3) Generate Report")
            print("4) Exit")
            choice = input("\nSelect option: ").strip()
            if choice == '1':
                self.process_platform('twitter')
            elif choice == '2':
                self.process_platform('instagram')
            elif choice == '3':
                self.generate_report()
            elif choice == '4':
                print("Goodbye.")
                break
            else:
                print("Invalid selection. Try again.\n")
                time.sleep(1.2)

    def process_platform(self, platform: str):
        clear()
        print(f"[+] Starting {platform.title()} analysis...")
        try:
            if platform == 'twitter':
                query = input("Enter Twitter search query (default: india): ").strip() or 'india'
                posts = self.twitter_scraper.fetch(query=query, limit=30)
            else:
                hashtag = input("Enter Instagram hashtag without #: (default: india): ").strip() or 'india'
                posts = self.instagram_scraper.fetch(hashtag=hashtag, limit=20)
        except Exception as e:
            print(f"[!] Error during scraping: {e}. Using backup dataset.")
            posts = self.twitter_scraper.load_backup() if platform == 'twitter' else self.instagram_scraper.load_backup()

        if not posts:
            print("No posts retrieved.")
            pause()
            return

        flagged_rows = []
        for post in posts:
            text = post.get('content','')
            # Run classifiers
            results = []
            for clf in (self.fake_news_classifier, self.bullying_classifier):
                res = clf.classify(text)
                if res and res['flagged']:
                    results.append(res)
            # Deepfake (if images present)
            if post.get('media'):
                dres = self.deepfake_classifier.classify(post['media'])
                if dres and dres['flagged']:
                    results.append(dres)
            for res in results:
                record = {
                    'platform': platform,
                    'username': post.get('username'),
                    'link': post.get('link'),
                    'category': res['label'],
                    'confidence': res['confidence'],
                    'timestamp': datetime.utcnow().isoformat(timespec='seconds')
                }
                self.db.insert_flagged(record)
                self.reporter.save_screenshot_placeholder(record, post)
                flagged_rows.append([
                    record['platform'], record['username'], record['link'], record['category'], f"{record['confidence']:.2f}"
                ])
                self.flagged_session.append(record)

        clear()
        print(f"Scan complete. Retrieved {len(posts)} posts. Flagged {len(flagged_rows)}")
        if flagged_rows:
            print("\nFlagged Posts:")
            print(tabulate(flagged_rows, headers=["Platform","User","Link","Category","Conf"], tablefmt='grid'))
        else:
            print("No content flagged.")
        pause()

    def generate_report(self):
        clear()
        print("Generating report...")
        csv_path, pdf_path = self.reporter.generate()
        print(f"Report generated:\n CSV: {csv_path}\n PDF: {pdf_path}")
        pause()


if __name__ == '__main__':
    try:
        app = CyberShieldCLI()
        app.run()
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting.")
        sys.exit(0)