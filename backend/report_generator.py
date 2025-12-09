from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from io import BytesIO
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate PDF and Word reports from chat session analysis data"""
    
    def generate_pdf(self, session) -> BytesIO:
        """Generate PDF report from session data"""
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4,
                                   rightMargin=72, leftMargin=72,
                                   topMargin=72, bottomMargin=18)
            
            elements = []
            styles = getSampleStyleSheet()
            
            # Custom styles
            styles.add(ParagraphStyle(name='CustomTitle',
                                     parent=styles['Heading1'],
                                     fontSize=24,
                                     spaceAfter=30,
                                     alignment=TA_CENTER))
            
            styles.add(ParagraphStyle(name='CustomHeading',
                                     parent=styles['Heading2'],
                                     fontSize=16,
                                     spaceAfter=12,
                                     spaceBefore=12))
            
            # Title
            title = Paragraph("Laporan Analisis Sensus Ekonomi Indonesia", styles['CustomTitle'])
            elements.append(title)
            elements.append(Spacer(1, 0.3*inch))
            
            # Metadata
            date_str = datetime.now().strftime("%d %B %Y, %H:%M WIB")
            meta = Paragraph(f"<b>Tanggal:</b> {date_str}", styles['Normal'])
            elements.append(meta)
            elements.append(Spacer(1, 0.3*inch))
            
            # Session title
            session_title = getattr(session, 'title', 'Analisis Sensus')
            topic = Paragraph(f"<b>Topik:</b> {session_title}", styles['CustomHeading'])
            elements.append(topic)
            elements.append(Spacer(1, 0.2*inch))
            
            # Messages
            messages = getattr(session, 'messages', [])
            for msg in messages:
                sender = "Pengguna" if getattr(msg, 'sender', 'user') == 'user' else "AI Asisten"
                sender_para = Paragraph(f"<b>{sender}:</b>", styles['CustomHeading'])
                elements.append(sender_para)
                
                content = getattr(msg, 'content', '').replace('\n', '<br/>')
                content_para = Paragraph(content, styles['BodyText'])
                elements.append(content_para)
                elements.append(Spacer(1, 0.2*inch))
            
            doc.build(elements)
            buffer.seek(0)
            return buffer
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            raise
    
    def generate_docx(self, session) -> BytesIO:
        """Generate Word document from session data"""
        try:
            doc = Document()
            
            # Title
            title = doc.add_heading('Laporan Analisis Sensus Ekonomi Indonesia', 0)
            title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            
            # Metadata
            date_str = datetime.now().strftime("%d %B %Y, %H:%M WIB")
            meta = doc.add_paragraph()
            meta.add_run('Tanggal Pembuatan: ').bold = True
            meta.add_run(date_str)
            doc.add_paragraph()
            
            # Session title
            session_title = getattr(session, 'title', 'Analisis Sensus')
            topic = doc.add_paragraph()
            topic.add_run('Topik: ').bold = True
            topic.add_run(session_title)
            doc.add_paragraph()
            
            # Messages
            messages = getattr(session, 'messages', [])
            for msg in messages:
                sender = "Pengguna" if getattr(msg, 'sender', 'user') == 'user' else "AI Asisten"
                sender_heading = doc.add_heading(sender, level=2)
                
                content = getattr(msg, 'content', '')
                doc.add_paragraph(content)
                doc.add_paragraph()
            
            # Save to buffer
            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)
            return buffer
        except Exception as e:
            logger.error(f"Error generating DOCX: {e}")
            raise
