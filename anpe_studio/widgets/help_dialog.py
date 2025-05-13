"""
Custom QDialog to display help content from a Markdown file
using a QTextBrowser for better formatting and scrolling.
"""

import logging
import sys
import re
from pathlib import Path
from typing import Optional, Dict, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTextBrowser, QPushButton, QDialogButtonBox, QLabel, QWidget, QHBoxLayout, QFrame, QGridLayout,
    QSplitter, QTreeWidget, QTreeWidgetItem, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, QUrl, QSize, QCoreApplication
from PyQt6.QtGui import QDesktopServices, QIcon, QPixmap, QFont, QColor, QTextDocument, QGuiApplication # For opening URLs and painting
from PyQt6.QtWidgets import QMessageBox # For About box
from anpe_studio.theme import PRIMARY_COLOR, get_scroll_bar_style, LIGHT_HOVER_BLUE, LIGHT_GREY_BACKGROUND  # Import theme colors and scroll bar style
from anpe_studio.resource_manager import ResourceManager

class HelpDialog(QDialog):
    def __init__(self, help_file_path: Path, gui_version: str, core_version: str, parent=None):
        super().__init__(parent)
        self.help_file_path = help_file_path
        self.gui_version = gui_version
        self.core_version = core_version
        self.setWindowTitle("ANPE Studio Help")
        self.setMinimumSize(800, 700)  # Reduced minimum width
        self.resize(800, 700)  # Reduced default width
        
        # Store sections for navigation
        self.sections = {}  # Will hold section name -> anchor mapping
        self.section_levels = {}  # Will track heading levels
        self.html_content = ""  # Will store the final HTML content
        
        # Store heading positions for direct navigation
        self.heading_positions = {}  # Will store heading text -> cursor position mapping

        self.setup_ui()
        self.load_help_content()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)  # Reduce spacing between elements
        layout.setContentsMargins(0, 0, 0, 0)  # No margins for main layout
        
        # Create a splitter as the main container
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setChildrenCollapsible(False)  # Prevent collapsing sections
        content_splitter.setHandleWidth(0)  # Remove the visible resize handle
        
        # Left side: Navigation tree
        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(10, 10, 0, 10)
        nav_layout.setSpacing(5)
        
        # Add a simple header for the navigation
        nav_header = QLabel("Contents")
        nav_header.setStyleSheet(f"""
            QLabel {{
                color: {PRIMARY_COLOR};
                font-size: 20px;
                font-weight: bold;
                padding-bottom: 5px;
                border-bottom: 1px solid #ddd;
            }}
        """)
        nav_layout.addWidget(nav_header)
        
        # Tree widget for navigation
        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setFixedWidth(250)  # Increased width from 230 to 250
        
        # Use specific SVG files for branch indicators
        expand_close_url = ResourceManager.get_style_url("expand_close.svg")
        expand_open_url = ResourceManager.get_style_url("expand_open.svg")
        
        self.nav_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: #F7F7F7;
                border: none;
                font-size: 10pt;
                padding: 5px;
            }}
            QTreeWidget::item {{
                padding: 4px 2px; /* vertical padding = 4px, horizontal padding = 2px */
                min-height: 22px; /* Set minimum height to prevent crowding */
                border-bottom: 1px solid #EEEEEE;
                border: none; /* Remove border */
                outline: none; /* Remove outline */
            }}
            QTreeWidget::item:hover:!selected {{
                background-color: {LIGHT_HOVER_BLUE}; /* Light blue background on hover */
                color: {PRIMARY_COLOR}; /* Use primary color teaxt on hover */
            }}
            QTreeWidget::item:selected {{
                background-color: {PRIMARY_COLOR};
                color: white; 
                border: none; 
                outline: none; 
                border-radius: 0px;
            }}
            QTreeWidget:focus {{
                outline: none; /* Remove focus outline */
            }}
            /* Use specific SVG files for branch indicators */
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: url("{expand_close_url}");
                margin-right: 3px; /* Add some space */
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{
                image: url("{expand_open_url}"); 
                margin-right: 3px; /* Add some space */
            }}
            {get_scroll_bar_style(vertical_width=8, horizontal_height=8, handle_min_size=30, border_radius=4)}
        """)
        self.nav_tree.itemClicked.connect(self.on_nav_item_clicked)
        nav_layout.addWidget(self.nav_tree)
        content_splitter.addWidget(nav_container)
        
        # Right side: Content
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 10, 20, 10)  # Increased horizontal margins
        content_layout.setSpacing(10)
        
        # Text browser for content
        self.text_browser = QTextBrowser()
        self.text_browser.setReadOnly(True)
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.anchorClicked.connect(self.handle_anchor_click)
        
        # Style the text browser
        self.text_browser.setStyleSheet(f"""
            QTextBrowser {{
                border: none;
                padding: 15px 25px;  /* Increased padding to create narrower text column */
                font-size: 13px;
                line-height: 170%;
                background-color: white;
            }}
            {get_scroll_bar_style(vertical_width=10, horizontal_height=10, handle_min_size=30, border_radius=5)}
        """)
        
        # Set document margins for better readability
        document = self.text_browser.document()
        document.setDocumentMargin(20)  # Increased document margin
        
        content_layout.addWidget(self.text_browser)
        
        # Add buttons at the bottom
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 5, 0, 0)
        button_layout.setSpacing(10)
        
        self.project_page_button = QPushButton("Project Page")
        self.ok_button = QPushButton("OK")
        
        button_style = """
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
        """
        self.project_page_button.setStyleSheet(button_style)
        self.ok_button.setStyleSheet(button_style)
        
        button_layout.addStretch()
        button_layout.addWidget(self.project_page_button)
        button_layout.addWidget(self.ok_button)
        
        self.ok_button.clicked.connect(self.accept)
        self.project_page_button.clicked.connect(self.go_to_project_page)
        
        content_layout.addWidget(button_container)
        content_splitter.addWidget(content_container)
        
        # Set fixed sizes for the splitter (navigation panel fixed, content panel takes the rest)
        content_splitter.setSizes([250, 550])  # Adjusted to match the new navigation width
        content_splitter.setStretchFactor(0, 0)  # Don't allow navigation panel to stretch
        content_splitter.setStretchFactor(1, 1)  # Allow content panel to stretch
        layout.addWidget(content_splitter)

    def load_help_content(self):
        """Load and display the help content from the markdown file."""
        try:
            with open(self.help_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
                # First, extract headings for navigation
                self.process_content(content)
                
                # Pre-process the markdown content for better readability
                content = self.preprocess_markdown(content)
                
                # Convert markdown to HTML using our custom converter
                html_content = self.markdown_to_html(content)
                
                # Apply styling to HTML content
                styled_html = self.apply_styling(html_content)
                
                # Set HTML content in the text browser
                self.text_browser.setHtml(styled_html)
                
                # Find and store positions of all headings for navigation
                self.find_heading_positions()
                
                # Populate the navigation tree
                self.populate_navigation_tree()
                
        except Exception as e:
            self.text_browser.setPlainText(f"Error loading help content: {str(e)}")
            logging.error(f"Error loading help content: {str(e)}")

    def process_content(self, content):
        """Process markdown content to extract sections for navigation."""
        self.sections = {}
        self.section_levels = {}
        
        # Regular expression to find headings
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        for match in heading_pattern.finditer(content):
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            # Create anchor ID - simple and consistent
            anchor_id = heading_text.lower().replace(' ', '-')
            anchor_id = re.sub(r'[^\w\-]', '', anchor_id)
            
            # Store section information
            self.sections[heading_text] = anchor_id
            self.section_levels[heading_text] = level

    def find_heading_positions(self):
        """Find and store the positions of all headings in the document."""
        self.heading_positions = {}
        
        # Get the document and search through all blocks
        doc = self.text_browser.document()
        
        # Loop through all blocks in the document
        for i in range(doc.blockCount()):
            block = doc.findBlockByNumber(i)
            text = block.text().strip()
            
            # For each heading in our sections, try to find it in the text
            for heading in self.sections.keys():
                # Strip any HTML tags from the text for comparison
                plain_text = re.sub(r'<[^>]+>', '', text)
                
                # Check if this block contains our heading
                if heading in plain_text:
                    self.heading_positions[heading] = block.position()
                    break
        
        # Debug logging
        if len(self.heading_positions) != len(self.sections):
            logging.warning(f"Only found positions for {len(self.heading_positions)} out of {len(self.sections)} headings")

    def populate_navigation_tree(self):
        """Populate the navigation tree with sections."""
        if not self.sections:
            return
            
        # Create parent-child relationships based on heading levels
        current_parents = {0: None, 1: None, 2: None, 3: None, 4: None, 5: None, 6: None}
        
        # Process all sections
        for heading, anchor in self.sections.items():
            level = self.section_levels[heading]
            
            # Create tree item
            item = QTreeWidgetItem([heading])
            item.setData(0, Qt.ItemDataRole.UserRole, anchor)
            
            # Style based on level
            font = item.font(0)
            if level == 1:
                font.setBold(True)
                font.setPointSize(11)
            elif level == 2:
                font.setBold(True)
            item.setFont(0, font)
            
            # Update current parent for this level
            current_parents[level] = item
            
            # Find parent based on heading level
            if level == 1:
                # Top-level heading
                self.nav_tree.addTopLevelItem(item)
            else:
                # Find the closest parent level
                parent_level = level - 1
                while parent_level > 0:
                    if current_parents[parent_level] is not None:
                        current_parents[parent_level].addChild(item)
                        break
                    parent_level -= 1
                if parent_level == 0:
                    # No parent found, add as top-level
                    self.nav_tree.addTopLevelItem(item)
        
        # Expand all tree items by default
        self.nav_tree.expandAll()

    def on_nav_item_clicked(self, item, column):
        """Handle navigation tree item click."""
        heading = item.text(0)  # Get the heading text
        
        # Method 1: Use stored position for direct navigation
        if heading in self.heading_positions:
            position = self.heading_positions[heading]
            
            # First ensure cursor is at the heading position
            cursor = self.text_browser.textCursor()
            cursor.setPosition(position)
            self.text_browser.setTextCursor(cursor)
            
            # Force the heading to appear at the top by doing the following:
            # 1. Get the current block position (y-coordinate)
            current_block = cursor.block()
            document = self.text_browser.document()
            layout = document.documentLayout()
            block_position = layout.blockBoundingRect(current_block).y()
            
            # 2. Set the vertical scroll bar position to match this y-coordinate
            scroll_bar = self.text_browser.verticalScrollBar()
            scroll_bar.setValue(int(block_position))
            
            # Force UI update
            QCoreApplication.processEvents()
            return
            
        # Method 2: Fallback to anchor-based navigation
        anchor = item.data(0, Qt.ItemDataRole.UserRole)
        if anchor:
            # Try to scroll to the anchor as fallback
            self.text_browser.scrollToAnchor(anchor)
            QCoreApplication.processEvents()

    def handle_anchor_click(self, url):
        """Handle clicked links."""
        if url.scheme() in ('http', 'https'):
            # External URL - open in browser
            QDesktopServices.openUrl(url)
            return True
        else:
            # Internal link - try to scroll to anchor
            fragment = url.fragment()
            if fragment:
                self.text_browser.scrollToAnchor(fragment)
                return True
        return False

    def go_to_project_page(self):
        """Open the project page in a browser."""
        QDesktopServices.openUrl(QUrl("https://github.com/rcverse/anpe-studio"))

    def preprocess_markdown(self, content):
        """Pre-process markdown content to improve readability."""
        # Add extra newlines before headings for better spacing
        content = re.sub(r'(\n#{1,6}\s+)', r'\n\n\1', content)
        
        # Add extra newlines after headings
        content = re.sub(r'(#{1,6}\s+.+)(\n)', r'\1\n\2', content)
        
        # Add extra newlines before lists for better spacing
        content = re.sub(r'(\n\s*[-*]\s+)', r'\n\1', content)
        
        # Reduce indentation in lists - replace multiple spaces with just 2
        content = re.sub(r'(\n)( {4,})([*-])', r'\1  \3', content)
        
        # Add extra spacing between list items
        content = re.sub(r'(\n\s*[-*]\s+[^\n]+)(\n\s*[-*]\s+)', r'\1\n\2', content)
        
        # Add horizontal line before major section headings (##)
        content = re.sub(r'(\n## )', r'\n\n---\n\n\1', content)
        
        # Add extra spacing after paragraphs
        content = re.sub(r'(\n[^\s#>*-][^\n]+)(\n[^\s#>*-])', r'\1\n\2', content)
        
        return content

    def markdown_to_html(self, markdown_text):
        """Basic markdown to HTML conversion using explicit tags."""
        html = markdown_text

        # Convert custom tags first
        html = re.sub(r'<button>(.*?)</button>', r'<span class="custom-button">\1</span>', html)
        html = re.sub(r'<option>(.*?)</option>', r'<span class="custom-option">\1</span>', html)
        html = re.sub(r'<format>(.*?)</format>', r'<span class="custom-format">\1</span>', html)
        
        # Add similar handling for <q> and <kbd> tags to parse them into spans
        # This will also respect the spaces inside them as per the markdown file
        html = re.sub(r'<q>(.*?)</q>', r'<span class="custom-q">\1</span>', html)
        html = re.sub(r'<kbd>(.*?)</kbd>', r'<span class="custom-kbd">\1</span>', html)

        # Convert standard markdown headings (e.g., # Heading -> <h1>Heading</h1>)
        for i in range(6, 0, -1):
            pattern = r'^{0}\s+(.+?)$'.format('#' * i)
            replacement = r'<h{0}>\1</h{0}>'.format(i)
            html = re.sub(pattern, replacement, html, flags=re.MULTILINE)

        # Convert bold (e.g., **text** -> <strong>text</strong>)
        html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)

        # Convert code (e.g., `text` -> <code>text</code>)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

        # Convert horizontal rule (e.g., --- -> <hr>)
        html = re.sub(r'^---+$', r'<hr>', html, flags=re.MULTILINE)

        # Convert unordered lists
        # First, detect list items and wrap with <li> tags
        html = re.sub(r'^\s*[-*]\s+(.+?)$', r'<li>\1</li>', html, flags=re.MULTILINE)

        # Then, group consecutive <li> items into <ul> lists
        html = re.sub(r'(?:<li>.*?</li>\s*)+', lambda m: f'<ul>{m.group(0)}</ul>', html, flags=re.DOTALL)

        # Convert links (e.g., [text](url) -> <a href="url">text</a>)
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)

        # Convert paragraphs (blocks of text not otherwise formatted)
        # First, split into blocks separated by blank lines
        blocks = re.split(r'\n\s*\n', html)
        for i, block in enumerate(blocks):
            # Skip blocks that are already wrapped with HTML tags (headings, lists, hr, etc.)
            stripped_block = block.strip()
            if not stripped_block or re.match(r'^\s*<(h[1-6]|ul|li|hr|p|code|strong|a|span)', stripped_block.lower()):
                continue
            # Wrap other blocks with <p> tags
            blocks[i] = f'<p>{stripped_block}</p>'
        html = '\n\n'.join(blocks)

        return html

    def apply_styling(self, html_content):
        """Apply custom styling to HTML content."""
        # Get the primary color from the theme
        from anpe_studio.theme import PRIMARY_COLOR, LIGHT_HOVER_BLUE, LIGHT_GREY_BACKGROUND
        
        # Add CSS styles (restored to full version, with correct single braces for CSS syntax)
        css = f"""
        <style>
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                line-height: 1.6; /* Slightly reduced line height */
                margin: 0;
                padding: 0;
                color: #333; /* Default text color */
                background-color: white; /* Ensure background is white */
                font-size: 15px; /* Slightly increased base font size */
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: {PRIMARY_COLOR}; /* Use theme primary color for headings */
                margin-top: 1.5em; /* More space above headings */
                margin-bottom: 0.7em; /* Space below headings */
                line-height: 1.4; /* Tighter line height for headings */
                font-weight: bold; /* Changed from 600 to bold for stronger emphasis */
            }}
            h1 {{ font-size: 2.2em; border-bottom: 2px solid #eee; padding-bottom: 0.3em; }}
            h2 {{ font-size: 1.8em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
            h3 {{ font-size: 1.5em; }}
            h4 {{ font-size: 1.2em; color: #444; margin-top: 1.2em; margin-bottom: 0.5em; }}
            h5, h6 {{ font-size: 1.1em; color: #555; }}

            p {{ 
                margin: 0.8em 0 1em 0; /* Adjusted paragraph margins */
                font-size: 15px; /* Ensure paragraphs use the new larger size */
            }}
            ul, ol {{
                margin: 0.8em 0;
                padding-left: 1.8em; /* Slightly increased list indentation */
                font-size: 15px; /* Consistent with new paragraph size */
            }}
            li {{
                margin: 0.4em 0; /* More space between list items */
                list-style-position: outside;
            }}
            hr {{
                height: 1px; /* Thinner horizontal rule */
                padding: 0;
                margin: 2em 0; /* More vertical space around hr */
                background-color: #ddd; /* Lighter color for hr */
                border: 0;
            }}
            code {{
                font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
                background-color: {LIGHT_GREY_BACKGROUND};
                color: #2d2d2d;
                padding: 3px 6px;
                border-radius: 5px;
                font-size: 0.9em;
                border: 1px solid #e0e0e0;
            }}
            strong {{
                font-weight: 600;
            }}
            a {{
                color: {PRIMARY_COLOR};
                text-decoration: none;
                font-weight: 500;
            }}
            a:hover {{
                text-decoration: underline;
                color: #003f7f;
            }}
            
            .custom-button, .custom-option, .custom-format {{
                display: inline-block;
                padding: 3px 10px;
                border-radius: 12px;
                white-space: nowrap;
                font-style: normal;
                font-size: 0.92em;
                line-height: 1.4;
                margin: 0 2px;
                vertical-align: baseline;
                border: 1px solid transparent;
            }}

            .custom-button {{
                background-color: #e7f3ff;
                color: {PRIMARY_COLOR};
                font-weight: 500;
                border-color: #cce4ff;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }}

            .custom-option {{
                background-color: #f5f5f5;
                color: #333;
                font-weight: 500;
                border-color: #e0e0e0;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }}

            .custom-format {{
                background-color: #f0f0f0;
                color: #555;
                font-style: italic;
                font-weight: normal;
                border-color: #e5e5e5;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            }}

            .custom-q {{
                /* Inherits body font and styles by default */
            }}

            .custom-kbd {{
                display: inline-block;
                padding: 2px 6px;
                border-radius: 4px;
                white-space: nowrap;
                font-style: normal;
                font-size: 0.9em;
                line-height: 1.4;
                margin: 0 2px;
                vertical-align: baseline;
                background-color: {LIGHT_GREY_BACKGROUND};
                color: #2d2d2d;
                border: 1px solid #e0e0e0;
                font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
            }}
        </style>
        """

        # Wrap in HTML structure
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            {css}
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """ 