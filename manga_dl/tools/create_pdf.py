import io
from PyPDF2 import PdfReader, PdfWriter
import datetime
import os
import img2pdf
import re
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Spacer
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph
import json
import os
from PIL import Image


class PDFChapter:
    def __init__(self, title:str, imgs:list[str]):
        """
        Create a chapter for the PDF.
        title: str
            The title of the chapter.
        images: list[str]
            The list of image paths.
        
        """
        
        self.title = title
        self.images = imgs
        self.temp_dir = os.environ.get("TEMP_DIR", "tmp")
        self._packet = None
    
    @property
    def packet(self):
        if self._packet is None:
            self._packet = self.images_to_pdf()
        return self._packet  
    
    
    def images_to_pdf(self):
        packet = io.BytesIO()
        
        packet.write(img2pdf.convert(self.images)) # type: ignore
        
        packet.seek(0)
        
        packet2 = io.BytesIO()
        c = canvas.Canvas(packet2)
        w, _ = A4
        c.setFont("Helvetica", 20)
        c.setPageSize((w, 100))
        c.drawCentredString(w/2, 50, self.title)
        c.save()
        
        packet2.seek(0)
        
        pdf = PdfWriter()
        pdf.append(packet2)
        pdf.append(packet)
        
        packet3 = io.BytesIO()
        pdf.write(packet3)
        
        return packet3
    
    
    def _images_to_pdf(self):
        packet = io.BytesIO()
        c = canvas.Canvas(packet)
        page_width, _ = A4

        total_height = 0
        img_path_size = {}

        for image_path in self.images:
            img = Image.open(image_path)
            w, h = img.size
            if w > page_width:
                img.thumbnail((page_width, h), Image.LANCZOS) # type: ignore
                w, h = img.size
            
            img_path_size[image_path] = (w, h)

            total_height += h
            img.close()

        # resize images to fit the page width
        total_height += 50
        c.setPageSize((page_width, total_height))
        
        # draw title
        c.setFont("Helvetica", 20)
        x = 10
        y = total_height - 30
        c.drawString(x, y, self.title)
        

        # draw images on one page
        y = total_height - 50
        for image_path in self.images:
            w, h = img_path_size[image_path]
            c.drawImage(image_path, 0, y - h, w, h)
            y -= h
        
        c.save()
        packet.seek(0)
        return packet
        

    def __str__(self) -> str:
        return json.dumps(self.__dict__)
    
    def __repr__(self) -> str:
        return self.__str__()


class PDF:
    """
    Create a PDF file from a list of images.

    Methods:
        set_title(title: str) Set the title of the PDF.
        
        set_author(author: str) Set the author of the PDF.
        
        set_cover(cover_image: str) Set the cover of the PDF.
        
        create_chapter(title: str, images: list[str]) Create a chapter.
        
        add_chapter(chapter: Chapter) Add a chapter.
        
        set_toc(chapter_titles: list[str]) Set the table of contents.
        
        set_page_data(data: list[dict]) Set the page data.
        
        write_pdf(output_path: str) Write the PDF to the specified path.
        
    """
    def __init__(self):
        self.title: str = None # type: ignore
        self.author = None # type: ignore
        self.cover_page: io.BytesIO = None # type: ignore
        self.temp_dir = os.environ.get("TEMP_DIR", "tmp")
        self.chapters: list[PDFChapter] = []
        self.page_size = A4
        self.toc: io.BytesIO = None # type: ignore
        self.intro: io.BytesIO = None # type: ignore
        self.size = 0

    def set_title(self, title):
        self.title = title

    def set_author(self, author):
        self.author = author

    def set_cover(self, cover_image):
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=self.page_size)
        x, y = 0, 0
        w, h = self.page_size
        c.drawImage(cover_image, x, y, w, h)
        c.save()
        packet.seek(0)
        self.cover_page = packet

    def _safe_filename(self, filename):
        return re.sub(r"[^a-zA-Z0-9]", "_", filename)

    def _create_temp_dir(self):
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def create_chapter(self, chapter_title, images):
        pdf_chapter = PDFChapter(chapter_title, imgs=images)
        pdf_chapter.packet
        return pdf_chapter
        
    def add_chapter(self, chapter: PDFChapter):
        self.chapters.append(chapter)

    def set_toc(self, chapters: list[PDFChapter]):
        packet = io.BytesIO()
        doc = SimpleDocTemplate(packet, pagesize=self.page_size)
        
        styles = getSampleStyleSheet()
        story = []
        toc = Paragraph("<b>Table of Contents</b>", styles["Heading1"])
        story.append(toc)
        
        page_width, page_height = self.page_size
        dots_counts = int(page_width / 4.5) // 2
        
        section = "{} " + ". " * dots_counts + " {}"
        spacer = Spacer(1, 0.1 * inch)
        i = 5
        for chapter in chapters:
            story.append(Paragraph(section.format(chapter.title, i), styles["Normal"]))
            story.append(spacer)
            
            i += len(chapter.images) + 1
        
        doc.build(story)
        packet.seek(0)
        self.toc = packet
    
        
    def set_page_data(self, data):
        # Create a canvas with the specified output file
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=self.page_size)

        # Set up styles for the labels and values
        # Set up styles for the labels and values
        style_sheet = getSampleStyleSheet()

        # Calculate the coordinates for the labels and values
        x = 1 * inch
        y = 10 * inch

        # Add the labels and values to the canvas
        for entry in data:
            label = entry["label"]
            value = entry["value"]
            

            label_style = style_sheet["Heading4"]
            value_style = style_sheet["Normal"]
            

            label_paragraph = Paragraph(label, label_style)
            value_paragraph = Paragraph(str(value), value_style)

            label_paragraph.wrapOn(c, 6 * inch, 10 * inch)
            value_paragraph.wrapOn(c, 4.5 * inch, 10 * inch)  # Adjusted width for value

            max_height = max(label_paragraph.height, value_paragraph.height)

            # Adjust y-coordinate for the next line
            y -= max_height

            label_paragraph.drawOn(c, x, y)
            value_paragraph.drawOn(c, x + 2 * inch, y)

            y -= max_height

        # Save the canvas
        c.save()

        packet.seek(0)
        self.intro = packet

    def write(self, save_path):
        self._create_temp_dir()
        
        
        merger = PdfWriter()
        if self.cover_page:
            merger.append(self.cover_page)

        if self.intro:
            merger.append(self.intro)
            
        if self.toc:
            merger.append(self.toc)

        for chapter in self.chapters:
            merger.append(chapter.packet)

        if self.title is None or self.author is None:
            raise Exception("Title and Author must be set")

        merger.add_metadata(
            {
                "/Title": self.title,
                "/Author": self.author,
                "/Producer": "Python PDF Manipulation",
                "/CreationDate": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        merger.write(save_path)
