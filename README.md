# CyberShield CLI

Terminal tool to scrape social media (Twitter via snscrape, Instagram via instaloader), run lightweight content safety classifiers, store flagged posts, and generate CSV/PDF reports.

## Features
- Twitter & Instagram scraping with graceful fallback to backup CSV datasets.
- Classifier Hub:
  - Fake News (DistilBERT sentiment heuristic + keywords fallback)
  - Bullying / Anti-India (HateBERT if available + keywords fallback)
  - Deepfake (mock hash heuristic)
- SQLite storage of flagged posts.
- Screenshot placeholder PNGs for each flagged post.
- Report generation (CSV + PDF with summary & details).

## Structure
```
main.py
scrapers/
  twitter_scraper.py
  instagram_scraper.py
classifiers/
  fake_news.py
  deepfake.py
  bullying.py
storage/
  database.py
  reports.py
backup/
  twitter_backup.csv
  instagram_backup.csv
reports/ (generated artifacts)
```

## Install
Create a virtual environment (recommended) then install requirements.
```
pip install -r requirements.txt
```

If transformers model downloads are slow or unavailable, the app will fallback to keyword heuristics automatically.

## Run
```
python main.py
```

## Notes
- Instagram scraping without login may be limited or blocked; on failure, backup dataset is used.
- Deepfake detection is a mock for demo purposes.
- Screenshots are generated as textual PNG placeholders (no actual web rendering).

## Future Enhancements
- Add YouTube / Facebook modules.
- Real deepfake image/video model integration.
- Async scraping and model inference pipelines.

---
Demo only; not for production investigative use.