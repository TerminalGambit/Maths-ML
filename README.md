# Maths-ML — d2l.ai HAR → PDF export

This repo turns a captured HAR file of [d2l.ai's *Multivariable Calculus*
appendix](https://d2l.ai/chapter_appendix-mathematics-for-deep-learning/multivariable-calculus.html)
into a clean, print-ready PDF that preserves the prose, code, equations and
figures.

## Output

- `Multivariable-Calculus-d2l.pdf` — final PDF (~16 pages).
- `multivariable-calculus.print.html` — the cleaned, print-styled HTML used
  to render the PDF.
- `extracted/` — every HTML/CSS/SVG/PNG asset pulled out of the HAR archive,
  laid out under its original path so the renderer can resolve relative
  references (e.g. `../_images/chain-net1.svg`).
- `build_pdf.py` — the build script (see below).

## How it works

1. **Extract HAR payloads.** Each entry's response body is decoded (base64
   for binary assets, plain text otherwise) and written to disk under
   `extracted/<host-relative-path>`.
2. **Clean the HTML.** Header/sidebar/footer chrome, scripts, comment
   widgets, Colab/SageMaker launch tabs and permalink anchors are removed.
3. **Render math without JavaScript.** WeasyPrint can't run MathJax, so every
   `\(...\)` and `\[...\]` block is converted to MathML via
   [`latex2mathml`](https://pypi.org/project/latex2mathml/) and inlined.
4. **Pick one code tab.** The page ships PyTorch / MXNet / TensorFlow tabs
   side by side; the PDF keeps just the active PyTorch panel to match what a
   reader would see in the browser.
5. **Style for print.** A single embedded stylesheet sets up A4 pages,
   serif body text, sans-serif headings, monospaced code with light
   syntax-coloured Pygments tokens, and `page-break-inside: avoid` on code
   and equation blocks.
6. **Render with WeasyPrint** using `extracted/chapter_appendix-mathematics-for-deep-learning/`
   as the base URL so relative `<img>` paths resolve to the SVGs from the
   HAR.

## Reproduce

```bash
pip install weasyprint beautifulsoup4 lxml latex2mathml
python build_pdf.py
```

The script reads from
`/root/.claude/uploads/.../b2d06880-d2l.ai.har`-derived `extracted/` tree and
writes the PDF + intermediate HTML next to itself.
