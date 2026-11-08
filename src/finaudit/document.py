"""Turn a 10-K HTML filing into numbered pages.

EDGAR filings mark printed page breaks with <hr style="page-break-after:always">,
so the document can be split exactly where the printed pages end.

Page numbers here count those sections from the very start of the file,
including the unnumbered cover and contents pages. They can therefore run a
couple of numbers ahead of the page number printed in the filing's footer
(in Apple's fiscal 2026 10-K, section 21 is printed page 19). To check a
citation, search the filing for the quoted figure.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# iXBRL filings start with an XML declaration but are HTML; parsing as HTML is correct.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

PAGE_BREAK = re.compile(r"<hr[^>]*page-break-(?:after|before)\s*:\s*always[^>]*>", re.I)
MIN_PAGE_CHARS = 100


@dataclass(frozen=True)
class Page:
    number: int   # 1-based position in the filing
    text: str


def html_to_pages(html: str) -> list[Page]:
    chunks = PAGE_BREAK.split(html)
    pages = []
    for i, chunk in enumerate(chunks, start=1):
        soup = BeautifulSoup(chunk, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        # hidden iXBRL header blocks repeat machine data, not readable text
        for tag in soup.select('[style*="display:none"]'):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
        if len(text) >= MIN_PAGE_CHARS:
            pages.append(Page(i, text))
    return pages


def load_pages(path: Path) -> list[Page]:
    return html_to_pages(path.read_text(encoding="utf-8", errors="ignore"))
