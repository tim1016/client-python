"""
PDF Report Generator for Three-Minute Pattern Analysis
Combines all visualizations and analysis results into a comprehensive PDF report
"""

import os
import json
import argparse
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from PIL import Image as PILImage
import pandas as pd

class PDFReportGenerator:
    def __init__(self, analysis_dir: str):
        """Initialize PDF report generator."""
        self.analysis_dir = analysis_dir
        self.symbol = self.extract_symbol_from_dir(analysis_dir)
        self.viz_dir = os.path.join(analysis_dir, "visualizations")
        self.report_file = os.path.join(analysis_dir, f"{self.symbol}_analysis_report.pdf")
        
        # Setup styles
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
        
        # Collect report elements
        self.elements = []
        
    def extract_symbol_from_dir(self, dir_path: str) -> str:
        """Extract symbol from analysis directory name."""
        dir_name = os.path.basename(dir_path)
        return dir_name.split('_')[0]
    
    def setup_custom_styles(self):
        """Setup custom paragraph styles for the report."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#34495E'),
            spaceAfter=12,
            spaceBefore=12,
            leftIndent=0,
            alignment=TA_LEFT
        ))
        
        # Subsection header style
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#7F8C8D'),
            spaceAfter=10,
            spaceBefore=10,
            leftIndent=20
        ))
        
        # Data style
        self.styles.add(ParagraphStyle(
            name='DataStyle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2C3E50'),
            alignment=TA_LEFT
        ))
    
    def add_title_page(self):
        """Add title page to the report."""
        # Title
        title = Paragraph(f"Three-Minute Pattern Analysis Report", self.styles['CustomTitle'])
        self.elements.append(title)
        
        # Symbol
        symbol_text = Paragraph(f"<b>Symbol: {self.symbol}</b>", self.styles['Title'])
        self.elements.append(symbol_text)
        
        self.elements.append(Spacer(1, 0.5*inch))
        
        # Report metadata
        metadata = [
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Analysis Directory: {os.path.basename(self.analysis_dir)}",
        ]
        
        for item in metadata:
            para = Paragraph(item, self.styles['Normal'])
            self.elements.append(para)
            self.elements.append(Spacer(1, 0.1*inch))
        
        # Load analysis summary
        summary_file = os.path.join(self.analysis_dir, 'analysis_summary.json')
        if os.path.exists(summary_file):
            with open(summary_file, 'r') as f:
                summary = json.load(f)
            
            self.elements.append(Spacer(1, 0.3*inch))
            self.elements.append(Paragraph("<b>Analysis Overview</b>", self.styles['SectionHeader']))
            
            overview_data = [
                ['Metric', 'Value'],
                ['Data File', os.path.basename(summary.get('data_file', 'N/A'))],
                ['Bars Analyzed', f"{summary.get('bars_analyzed', 0):,}"],
                ['Date Range', f"{summary['date_range']['start']} to {summary['date_range']['end']}"],
            ]
            
            # Add offset results
            for offset_result in summary.get('offset_results', []):
                offset = offset_result['offset']
                overview_data.append([f'Offset {offset} Patterns', 
                                     f"{offset_result['unique_patterns']} unique / {offset_result['total_patterns']} total"])
                overview_data.append([f'Offset {offset} Validation', 
                                     '✓' if offset_result['mathematical_consistency']['change_matches'] else '✗'])
            
            table = Table(overview_data, colWidths=[3*inch, 3*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            self.elements.append(table)
        
        self.elements.append(PageBreak())
    
    def add_validation_summary(self):
        """Add validation summary section."""
        self.elements.append(Paragraph("Mathematical Validation Summary", self.styles['SectionHeader']))
        
        validation_data = [
            ['Offset', 'Baskets', 'Price Discrepancy', 'Time Discrepancy', 'Validation Status']
        ]
        
        for offset in range(3):
            stats_file = os.path.join(self.analysis_dir, f"basket_statistics_offset_{offset}.json")
            if os.path.exists(stats_file):
                with open(stats_file, 'r') as f:
                    stats = json.load(f)
                
                price_disc = f"${stats['change_discrepancy']:.6f}"
                time_disc = f"{stats['time_discrepancy']:.3f} min"
                status = '✓ PASSED' if all(stats['mathematical_consistency'].values()) else '✗ FAILED'
                
                validation_data.append([
                    str(offset),
                    str(stats['total_baskets']),
                    price_disc,
                    time_disc,
                    status
                ])
        
        table = Table(validation_data, colWidths=[0.8*inch, 1*inch, 1.5*inch, 1.5*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        self.elements.append(table)
        self.elements.append(Spacer(1, 0.3*inch))
        
        # Add explanation
        explanation = """
        The mathematical validation verifies that the sum of all pattern changes equals the total 
        price change in the data, and that time continuity is maintained across all baskets. 
        Discrepancies less than 0.0001 for price and 0.1 minutes for time are considered valid.
        """
        self.elements.append(Paragraph(explanation, self.styles['Normal']))
        self.elements.append(PageBreak())
    
    def add_top_patterns_section(self):
        """Add top performing patterns section."""
        self.elements.append(Paragraph("Top Performing Patterns", self.styles['SectionHeader']))
        
        for offset in range(3):
            pattern_file = os.path.join(self.analysis_dir, f"pattern_summary_offset_{offset}.csv")
            if os.path.exists(pattern_file):
                df = pd.read_csv(pattern_file)
                
                self.elements.append(Paragraph(f"<b>Offset {offset}</b>", self.styles['SubsectionHeader']))
                
                # Get top 10 patterns by average change
                top_patterns = df.nlargest(10, 'avg_change')
                
                pattern_data = [['Pattern', 'Count', 'Avg Change', 'Win Rate', 'Std Dev']]
                for _, row in top_patterns.iterrows():
                    pattern_data.append([
                        row['pattern'],
                        str(row['count']),
                        f"${row['avg_change']:.6f}",
                        row['win_rate'],
                        f"${row['std_dev']:.6f}"
                    ])
                
                table = Table(pattern_data, colWidths=[1*inch, 0.8*inch, 1.2*inch, 1*inch, 1.2*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                ]))
                
                self.elements.append(table)
                self.elements.append(Spacer(1, 0.2*inch))
        
        self.elements.append(PageBreak())
    
    def add_visualization(self, image_name: str, title: str, description: str = "", width_scale=1.0):
        """Add a visualization image to the report."""
        image_path = os.path.join(self.viz_dir, image_name)
        
        if os.path.exists(image_path):
            self.elements.append(Paragraph(title, self.styles['SectionHeader']))
            
            if description:
                self.elements.append(Paragraph(description, self.styles['Normal']))
                self.elements.append(Spacer(1, 0.1*inch))
            
            # Get image dimensions and scale appropriately
            img = PILImage.open(image_path)
            img_width, img_height = img.size
            aspect_ratio = img_height / img_width
            
            # Scale to fit page width (with margins)
            max_width = 6.5 * inch * width_scale
            scaled_width = min(max_width, img_width)
            scaled_height = scaled_width * aspect_ratio
            
            # Ensure it fits on page
            max_height = 8 * inch
            if scaled_height > max_height:
                scaled_height = max_height
                scaled_width = scaled_height / aspect_ratio
            
            img_element = Image(image_path, width=scaled_width, height=scaled_height)
            self.elements.append(img_element)
            self.elements.append(PageBreak())
        else:
            print(f"Warning: Image not found: {image_path}")
    
    def generate_report(self):
        """Generate the complete PDF report."""
        print(f"\n{'='*60}")
        print("GENERATING PDF REPORT")
        print(f"{'='*60}")
        
        # Create PDF document
        doc = SimpleDocTemplate(
            self.report_file,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Add title page
        self.add_title_page()
        
        # Add validation summary
        self.add_validation_summary()
        
        # Add top patterns section
        self.add_top_patterns_section()
        
        # Add visualizations with descriptions
        visualizations = [
            ('diagnostic_summation_charts.png', 
             'Diagnostic Summation Analysis',
             'Comprehensive validation of time and price change summation across all offsets. '
             'Shows cumulative changes, remainder handling, and component breakdowns for mathematical verification.'),
            
            ('pattern_performance_analysis.png',
             'Pattern Performance Analysis',
             'Comparative analysis of pattern performance across all offsets, including top patterns, '
             'frequency distributions, win rate correlations, and risk-return profiles.'),
            
            ('basket_analysis_charts.png',
             'Contiguous Basket Analysis',
             'Analysis of consecutive three-minute patterns grouped into baskets, showing cumulative '
             'price changes and pattern type performance with validation indicators.'),
            
            ('time_series_analysis.png',
             'Time Series Analysis',
             'Temporal analysis of pattern occurrences showing cumulative returns over time, '
             'basket boundaries, and drawdown metrics.'),
            
            ('pattern_heatmaps.png',
             'Pattern Performance Heatmaps',
             'Normalized heatmap visualization of pattern metrics including average change, '
             'standard deviation, and occurrence frequency.'),
            
            ('validation_dashboard.png',
             'Mathematical Validation Dashboard',
             'Comprehensive validation metrics showing discrepancy comparisons, validation status, '
             'and correlation between accounted and actual changes.')
        ]
        
        for img_name, title, description in visualizations:
            self.add_visualization(img_name, title, description)
        
        # Build PDF
        try:
            doc.build(self.elements)
            print(f"✅ PDF report generated successfully!")
            print(f"📄 Report saved to: {self.report_file}")
            print(f"📊 Total pages: ~{len(self.elements) // 3}")  # Rough estimate
            
            return self.report_file
            
        except Exception as e:
            print(f"❌ Error generating PDF: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def add_footer(self, canvas, doc):
        """Add footer to each page."""
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawString(inch, 0.5*inch, f"Page {doc.page}")
        canvas.drawRightString(7.5*inch, 0.5*inch, 
                              f"{self.symbol} Analysis - {datetime.now().strftime('%Y-%m-%d')}")
        canvas.restoreState()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Generate PDF report for pattern analysis')
    parser.add_argument('analysis_dir', help='Path to analysis results directory')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.analysis_dir):
        print(f"Error: Analysis directory not found: {args.analysis_dir}")
        return 1
    
    # Check if visualizations exist
    viz_dir = os.path.join(args.analysis_dir, 'visualizations')
    if not os.path.isdir(viz_dir):
        print(f"Error: Visualizations not found. Please run visualize_patterns.py first.")
        return 1
    
    try:
        generator = PDFReportGenerator(args.analysis_dir)
        report_file = generator.generate_report()
        
        if report_file:
            print(f"\n✅ Success! PDF report saved to: {report_file}")
            print("\nReport includes:")
            print("  • Executive summary with validation results")
            print("  • Top performing patterns for each offset")
            print("  • Diagnostic summation charts")
            print("  • All visualization charts with descriptions")
            print("  • Mathematical validation metrics")
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())