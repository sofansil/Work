# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a Python learning and practice repository containing examples covering:
- Python basics (functions, classes, OOP, control flow)
- PyQt5 GUI applications with Qt Designer (.ui files)
- SQLite database operations
- Web scraping (BeautifulSoup, Selenium, requests)
- Excel file manipulation (openpyxl)
- Data analysis (pandas)
- Simple games (pygame)
- HTML/CSS demos (in `html-css-demo/` subdirectory)

## Running Python Files

```bash
python <filename>.py
```

VS Code is configured for Python debugging with the integrated terminal.

## Key Dependencies

- **PyQt5**: GUI applications - load .ui files with `uic.loadUiType()`
- **sqlite3**: Database operations (built-in)
- **BeautifulSoup4**: Web scraping with `from bs4 import BeautifulSoup`
- **requests/urllib**: HTTP requests
- **selenium**: Browser automation
- **openpyxl**: Excel file operations
- **pandas**: Data analysis
- **pygame**: Game development

## PyQt5 Patterns

- UI files (.ui) are designed in Qt Designer and loaded via `uic.loadUiType("file.ui")[0]`
- Main window classes inherit from both `QMainWindow` and the loaded form class
- Signal-slot connections use `widget.signal.connect(self.handler)`
- Application entry point pattern:
```python
app = QApplication(sys.argv)
window = MyWindow()
window.show()
app.exec_()
```

## Database Pattern

SQLite databases are created on first run if they don't exist:
```python
if os.path.exists("mydb.db"):
    con = sqlite3.connect("mydb.db")
else:
    con = sqlite3.connect("mydb.db")
    cur = con.cursor()
    cur.execute("CREATE TABLE ...")
```

## Web Scraping Notes

- User-Agent headers are typically set to avoid blocking
- Korean content uses `utf-8` encoding with `errors='ignore'`
- Sites scraped include Clien, Naver Finance, and news sites
