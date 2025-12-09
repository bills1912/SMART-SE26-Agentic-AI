from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from io import BytesIO
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate PDF and Word reports from analysis data"""
    
    def generate_pdf(self, session_data: dict) -> BytesIO:
        """Generate PDF report from session data"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=18)
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='CustomTitle',
                                 parent=styles['Heading1'],
                                 fontSize=24,
                                 textColor='#DC2626',
                                 spaceAfter=30,
                                 alignment=TA_CENTER))
        
        styles.add(ParagraphStyle(name='CustomHeading',
                                 parent=styles['Heading2'],
                                 fontSize=16,
                                 textColor='#EA580C',
                                 spaceAfter=12,
                                 spaceBefore=12))
        
        # Title
        title = Paragraph("Laporan Analisis Sensus Ekonomi Indonesia", styles['CustomTitle'])
        elements.append(title)
        elements.append(Spacer(1, 0.2*inch))
        
        # Metadata
        date_str = datetime.now().strftime("%d %B %Y, %H:%M WIB")
        meta = Paragraph(f"<b>Tanggal Pembuatan:</b> {date_str}", styles['Normal'])
        elements.append(meta)
        elements.append(Spacer(1, 0.3*inch))
        
        # Session Title
        session_title = session_data.get('title', 'Analisis Sensus')
        title_para = Paragraph(f"<b>Topik:</b> {session_title}", styles['CustomHeading'])
        elements.append(title_para)
        elements.append(Spacer(1, 0.2*inch))
        
        # Messages
        messages = session_data.get('messages', [])
        for msg in messages:
            sender = "Pengguna" if msg.get('sender') == 'user' else "AI Asisten"
            
            # Sender header
            sender_para = Paragraph(f"<b>{sender}:</b>", styles['CustomHeading'])
            elements.append(sender_para)
            
            # Message content
            content = msg.get('content', '').replace('\n', '<br/>')
            content_para = Paragraph(content, styles['BodyText'])
            elements.append(content_para)
            elements.append(Spacer(1, 0.2*inch))
            
            # Add insights if available
            if msg.get('insights'):
                insights_title = Paragraph("<b>Key Insights:</b>", styles['Heading3'])
                elements.append(insights_title)
                for insight in msg['insights']:
                    insight_para = Paragraph(f"• {insight}", styles['Normal'])
                    elements.append(insight_para)
                elements.append(Spacer(1, 0.2*inch))
            
            # Add policies if available
            if msg.get('policies'):
                policies_title = Paragraph("<b>Rekomendasi Kebijakan:</b>", styles['Heading3'])
                elements.append(policies_title)
                for policy in msg['policies']:
                    policy_title = Paragraph(f"<b>{policy.get('title')}</b>", styles['Normal'])
                    elements.append(policy_title)
                    policy_desc = Paragraph(policy.get('description', ''), styles['Normal'])
                    elements.append(policy_desc)
                    elements.append(Spacer(1, 0.1*inch))
                elements.append(Spacer(1, 0.2*inch))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    def generate_docx(self, session_data: dict) -> BytesIO:
        """Generate Word document from session data"""
        doc = Document()
        
        # Title
        title = doc.add_heading('Laporan Analisis Sensus Ekonomi Indonesia', 0)
        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        title.runs[0].font.color.rgb = RGBColor(220, 38, 38)
        
        # Metadata
        date_str = datetime.now().strftime("%d %B %Y, %H:%M WIB")
        meta = doc.add_paragraph()
        meta.add_run('Tanggal Pembuatan: ').bold = True
        meta.add_run(date_str)
        doc.add_paragraph()
        
        # Session Title
        session_title = session_data.get('title', 'Analisis Sensus')
        topic = doc.add_paragraph()
        topic.add_run('Topik: ').bold = True
        topic.add_run(session_title)
        topic.runs[0].font.color.rgb = RGBColor(234, 88, 12)
        doc.add_paragraph()
        
        # Messages
        messages = session_data.get('messages', [])
        for msg in messages:
            sender = "Pengguna" if msg.get('sender') == 'user' else "AI Asisten"
            
            # Sender header
            sender_heading = doc.add_heading(sender, level=2)
            sender_heading.runs[0].font.color.rgb = RGBColor(234, 88, 12)
            
            # Message content
            content = msg.get('content', '')
            doc.add_paragraph(content)
            
            # Add insights
            if msg.get('insights'):
                insights_heading = doc.add_heading('Key Insights:', level=3)
                for insight in msg['insights']:
                    p = doc.add_paragraph(insight, style='List Bullet')
            
            # Add policies
            if msg.get('policies'):
                policies_heading = doc.add_heading('Rekomendasi Kebijakan:', level=3)
                for policy in msg['policies']:
                    doc.add_paragraph(policy.get('title', ''), style='List Number')
                    doc.add_paragraph(policy.get('description', ''))
                    doc.add_paragraph()
            
            doc.add_paragraph()
        
        # Save to buffer
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer
