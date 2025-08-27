import os
from datetime import datetime
from typing import Tuple
from .database import Database
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from PIL import Image, ImageDraw, ImageFont


class ReportGenerator:
    def __init__(self, db: Database, reports_dir: str = 'reports'):
        self.db = db
        self.reports_dir = reports_dir
        self.screens_dir = os.path.join(self.reports_dir, 'screenshots')
        os.makedirs(self.screens_dir, exist_ok=True)

    def save_screenshot_placeholder(self, record, post):
        # Creates a simple PNG with text summary.
        try:
            w, h = 800, 300
            img = Image.new('RGB', (w, h), color=(20, 20, 20))
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None
            lines = [
                f"Platform: {record.get('platform')}",
                f"User: {record.get('username')}",
                f"Category: {record.get('category')} ({record.get('confidence'):.2f})",
                f"Link: {record.get('link')}",
                f"Excerpt: {(post.get('content') or '')[:120]}"
            ]
            y = 10
            for line in lines:
                draw.text((10, y), line, fill=(200, 200, 200), font=font)
                y += 20
            fname = f"shot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}.png"
            img.save(os.path.join(self.screens_dir, fname))
        except Exception:
            pass  # Non-critical

    def generate(self) -> Tuple[str, str]:
        records = self.db.fetch_all()
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        os.makedirs(self.reports_dir, exist_ok=True)
        csv_path = os.path.join(self.reports_dir, f'report_{ts}.csv')
        pdf_path = os.path.join(self.reports_dir, f'report_{ts}.pdf')
        if records:
            df = pd.DataFrame(records)
        else:
            df = pd.DataFrame(columns=['id','platform','username','link','category','confidence','timestamp'])
        df.to_csv(csv_path, index=False)
        self._generate_pdf(pdf_path, df)
        return csv_path, pdf_path

    def _generate_pdf(self, pdf_path: str, df):
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        story.append(Paragraph("CyberShield Report", styles['Title']))
        story.append(Spacer(1, 12))
        summary_stats = {
            'Total Flagged': int(df.shape[0]),
        }
        cat_counts = df['category'].value_counts().to_dict() if not df.empty else {}
        for k,v in cat_counts.items():
            summary_stats[f"{k} Count"] = v
        for k,v in summary_stats.items():
            story.append(Paragraph(f"{k}: {v}", styles['Normal']))
        story.append(Spacer(1, 12))
        if not df.empty:
            data = [list(df.columns)] + df.values.tolist()
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.lightgrey])
            ]))
            story.append(table)
        else:
            story.append(Paragraph("No flagged records.", styles['Italic']))
        doc.build(story)