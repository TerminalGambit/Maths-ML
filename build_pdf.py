"""Build a print-ready PDF from the d2l.ai Multivariable Calculus HTML.

Steps:
  1. Load the extracted HTML page.
  2. Strip headers / sidebars / scripts / discuss embeds.
  3. Convert each LaTeX math span/div to inline/block MathML so WeasyPrint
     can render it without JavaScript.
  4. Keep only the active code-tab (pytorch); drop the alternatives.
  5. Inline a clean print stylesheet and run WeasyPrint.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import latex2mathml.converter as l2m
from bs4 import BeautifulSoup, NavigableString
from weasyprint import HTML, CSS

ROOT = Path('/home/user/Maths-ML')
SRC = ROOT / 'extracted/chapter_appendix-mathematics-for-deep-learning/multivariable-calculus.html'
OUT_HTML = ROOT / 'multivariable-calculus.print.html'
OUT_PDF = ROOT / 'Multivariable-Calculus-d2l.pdf'
BASE_DIR = ROOT / 'extracted/chapter_appendix-mathematics-for-deep-learning'


INLINE_RE = re.compile(r'\\\((.*?)\\\)', re.DOTALL)
DISPLAY_RE = re.compile(r'\\\[(.*?)\\\]', re.DOTALL)


def latex_to_mathml(latex: str, display: str = 'inline') -> str:
    try:
        return l2m.convert(latex, display=display)
    except Exception:
        # Fall back to a code-styled span so nothing is silently dropped.
        safe = (latex.replace('&', '&amp;')
                     .replace('<', '&lt;')
                     .replace('>', '&gt;'))
        return f'<code class="math-fallback">{safe}</code>'


def convert_inline_math(soup: BeautifulSoup) -> None:
    for span in list(soup.find_all('span', class_='math')):
        text = span.get_text()
        m = INLINE_RE.search(text)
        if not m:
            continue
        mathml = latex_to_mathml(m.group(1), display='inline')
        new = BeautifulSoup(mathml, 'html.parser')
        span.replace_with(new)


def convert_display_math(soup: BeautifulSoup) -> None:
    for div in list(soup.find_all('div', class_='math')):
        # Equation number, if present
        eqno = div.find('span', class_='eqno')
        eqno_html = ''
        if eqno:
            num = eqno.get_text(strip=True).split('¶')[0]
            eqno_html = f'<span class="eqno">{num}</span>'

        full_text = div.get_text()
        m = DISPLAY_RE.search(full_text)
        if not m:
            continue
        mathml = latex_to_mathml(m.group(1), display='block')
        wrapper = BeautifulSoup(
            f'<div class="math-display">{mathml}{eqno_html}</div>',
            'html.parser',
        )
        div.replace_with(wrapper)


def keep_only_pytorch_tab(soup: BeautifulSoup) -> None:
    for tabs in list(soup.find_all('div', class_='mdl-tabs')):
        bar = tabs.find('div', class_='mdl-tabs__tab-bar')
        panels = tabs.find_all('div', class_='mdl-tabs__panel')
        # Prefer pytorch panel; fall back to the first "is-active" panel.
        chosen = None
        for p in panels:
            if 'pytorch' in (p.get('id', '') or '').lower():
                chosen = p
                break
        if chosen is None:
            for p in panels:
                cls = p.get('class', []) or []
                if 'is-active' in cls:
                    chosen = p
                    break
        if chosen is None and panels:
            chosen = panels[0]
        if chosen is None:
            continue
        # Replace whole tabs widget with the chosen panel content.
        wrapper = soup.new_tag('div', **{'class': 'code-block-section'})
        for child in list(chosen.contents):
            wrapper.append(child)
        tabs.replace_with(wrapper)
        if bar:
            bar.decompose()


def strip_chrome(soup: BeautifulSoup) -> None:
    selectors_to_remove = [
        ('header', None),
        ('nav', None),
        ('footer', None),
        ('script', None),
        ('noscript', None),
        ('aside', None),
    ]
    for name, _ in selectors_to_remove:
        for el in soup.find_all(name):
            el.decompose()

    for cls in [
        'mdl-layout__drawer',
        'mdl-layout__header',
        'mdl-layout__obfuscator',
        'globaltoc-container',
        'side-doc-outline',
        'related',
        'sidebar',
        'sphinxsidebar',
        'rightsidebar',
        'discuss-shortcut',
        'fab',
        'colab',
        'sagemaker',
        'discuss',
        # d2l notebook-launcher tabs (Colab / SageMaker buttons at the top)
        'd2l-tabs',
        'd2l-tabs__tab-bar',
        'd2l-tabs__tab',
        'd2l-tabs__panel',
        'mdl-tooltip',
    ]:
        for el in soup.find_all(class_=cls):
            el.decompose()

    # Remove discuss embed iframes/divs by id pattern
    for el in soup.find_all(id=re.compile(r'^(discourse|comments|disqus).*', re.I)):
        el.decompose()

    # Permalink anchors (¶)
    for el in soup.find_all('a', class_='headerlink'):
        el.decompose()

    # The notebook-launch banner (Colab / SageMaker etc.)
    for el in soup.find_all(class_=re.compile(r'(notebook-launch|launchbar|launch-buttons)', re.I)):
        el.decompose()

    # Strip any remaining buttons (e.g. copy-button)
    for el in soup.find_all('button'):
        el.decompose()


def fix_image_paths(soup: BeautifulSoup) -> None:
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src.startswith('../_images/'):
            img['src'] = f'../extracted/_images/{src.split("../_images/")[-1]}'
        elif src.startswith('../_static/'):
            img['src'] = f'../extracted/_static/{src.split("../_static/")[-1]}'


def remove_top_logo(soup: BeautifulSoup) -> None:
    # Remove logo img blocks at the top of the document (they appear in chrome).
    for img in soup.find_all('img', src=re.compile(r'logo-with-text', re.I)):
        # Walk up to a reasonable container to remove
        container = img
        for _ in range(3):
            if container.parent is None:
                break
            container = container.parent
        container.decompose()


def remove_intro_widgets(soup: BeautifulSoup) -> None:
    """Remove 'Open the notebook in Colab', SageMaker, etc. links at the top."""
    # These appear as dt/dl pairs or simple <a> with text starting with "Open the notebook"
    for a in list(soup.find_all('a')):
        txt = a.get_text(strip=True).lower()
        if txt.startswith('open the notebook') or txt in {'colab', 'sagemaker studio lab'}:
            a.decompose()
    # Cleanup obvious wrapper divs that became empty
    for div in soup.find_all('div'):
        if not div.get_text(strip=True) and not div.find('img'):
            div.decompose()


def build_print_html(soup: BeautifulSoup, body_html: str) -> str:
    """Wrap the cleaned body in a minimal print-ready HTML document."""
    title = (soup.title.string or 'Multivariable Calculus').strip()
    css = """
    @page { size: A4; margin: 1.6cm 1.4cm; }
    @page :first { margin-top: 2cm; }
    html { font-family: 'DejaVu Serif', Georgia, serif; font-size: 11pt; line-height: 1.5; color: #111; }
    body { max-width: 100%; margin: 0; }
    h1, h2, h3, h4, h5 { font-family: 'DejaVu Sans', Arial, sans-serif; color: #0b3a66; line-height: 1.25; }
    h1 { font-size: 24pt; border-bottom: 2px solid #0b3a66; padding-bottom: 0.3em; }
    h2 { font-size: 18pt; margin-top: 1.2em; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; }
    h3 { font-size: 14pt; margin-top: 1em; color: #1a5298; }
    h4 { font-size: 12pt; color: #1a5298; }
    p { text-align: justify; orphans: 3; widows: 3; }
    a { color: #1a5298; text-decoration: none; }

    /* Code blocks */
    pre, .highlight pre {
      font-family: 'DejaVu Sans Mono', 'Menlo', monospace;
      font-size: 9pt;
      background: #f6f8fa;
      border: 1px solid #e1e4e8;
      border-radius: 4px;
      padding: 8px 10px;
      white-space: pre-wrap;
      word-wrap: break-word;
      page-break-inside: avoid;
    }
    code { font-family: 'DejaVu Sans Mono', 'Menlo', monospace; font-size: 90%; background: #f3f4f6; padding: 1px 4px; border-radius: 3px; }
    pre code { background: transparent; padding: 0; }

    /* Pygments token colours (approximation) */
    .highlight .k, .highlight .kn, .highlight .kc { color: #d33682; font-weight: bold; }
    .highlight .nb, .highlight .nf { color: #268bd2; }
    .highlight .s, .highlight .s1, .highlight .s2, .highlight .sa { color: #2aa198; }
    .highlight .c, .highlight .c1 { color: #93a1a1; font-style: italic; }
    .highlight .o { color: #586e75; }
    .highlight .n { color: #073642; }
    .highlight .mi, .highlight .mf { color: #b58900; }

    /* Math */
    math { font-family: 'STIX Two Math', 'Latin Modern Math', 'DejaVu Serif', serif; }
    .math-display { display: block; margin: 0.8em 0; text-align: center; page-break-inside: avoid; }
    .math-display .eqno { float: right; color: #666; font-size: 0.9em; }
    .math-fallback { color: #b00; }

    /* Images and figures */
    img, svg { max-width: 100%; height: auto; }
    figure { margin: 1em 0; text-align: center; page-break-inside: avoid; }
    figcaption { font-size: 9pt; color: #555; }

    /* Tables */
    table { border-collapse: collapse; margin: 0.8em 0; font-size: 10pt; }
    th, td { border: 1px solid #d0d7de; padding: 4px 8px; }
    th { background: #f6f8fa; }

    /* Sphinx admonitions */
    .admonition { border-left: 4px solid #1a5298; background: #eef4fa; padding: 8px 12px; margin: 1em 0; page-break-inside: avoid; }
    .admonition-title { font-weight: bold; color: #1a5298; margin-bottom: 4px; }

    /* Output cells from notebooks */
    .output, .output_area, .stderr, .stdout {
      background: #fafafa;
      border-left: 3px solid #ccc;
      padding: 6px 10px;
      margin: 0.4em 0;
      font-family: 'DejaVu Sans Mono', monospace;
      font-size: 9pt;
      white-space: pre-wrap;
    }

    /* Keep code with its preceding paragraph when possible */
    .code-block-section { page-break-inside: avoid; margin: 0.6em 0; }

    /* Hide Sphinx UI bits we missed */
    .topic, .toctree-wrapper { display: none; }
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{title}</title>
<style>{css}</style>
</head>
<body>
{body_html}
</body>
</html>
"""


def main() -> None:
    print('Reading source HTML...')
    html = SRC.read_text(encoding='utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    print('Stripping chrome...')
    strip_chrome(soup)
    remove_top_logo(soup)

    print('Converting math to MathML...')
    convert_inline_math(soup)
    convert_display_math(soup)

    print('Selecting active code tab (pytorch)...')
    keep_only_pytorch_tab(soup)

    print('Cleaning up notebook launch widgets...')
    remove_intro_widgets(soup)

    main_el = soup.find('main') or soup.find('div', {'role': 'main'}) or soup.body
    body_html = main_el.decode_contents() if main_el else soup.body.decode_contents()

    print_html = build_print_html(soup, body_html)
    OUT_HTML.write_text(print_html, encoding='utf-8')
    print(f'Wrote {OUT_HTML}')

    print('Rendering PDF with WeasyPrint...')
    HTML(string=print_html, base_url=str(BASE_DIR)).write_pdf(str(OUT_PDF))
    print(f'Wrote {OUT_PDF} ({OUT_PDF.stat().st_size / 1024:.1f} KB)')


if __name__ == '__main__':
    main()
