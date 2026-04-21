"""LaTeX to PDF compilation with clickable hyperlinks (zero token cost)."""

import subprocess
import os
import re
import logging

from config import settings

logger = logging.getLogger("resume_agent")


def compile_latex_to_pdf(tex_content: str, company: str,
                         job_title: str, output_dir: str = None) -> tuple[str, int]:
    """Compile LaTeX to PDF with clickable hyperlinks. Returns (pdf_path, page_count).

    Filename format: 'Hunain Shahzad Company Name Job Title.pdf'
    Runs pdflatex twice to resolve cross-references (hyperlinks).
    """
    if output_dir is None:
        output_dir = str(settings.OUTPUT_DIR)

    # Sanitize filename (collapse multiple spaces left by removed special chars like &)
    safe_company = re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', company)).strip()
    safe_title = re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', job_title)).strip()
    filename = f"Hunain Shahzad {safe_company} {safe_title}"

    tex_path = os.path.join(output_dir, f"{filename}.tex")
    pdf_path = os.path.join(output_dir, f"{filename}.pdf")

    # Write .tex file
    os.makedirs(output_dir, exist_ok=True)
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    logger.info(f"  📝 Wrote: {tex_path}")

    # Compile with pdflatex (hyperref already in template = clickable links)
    # Run twice to resolve references
    result = None
    for pass_num in range(2):
        result = subprocess.run(
            [settings.PDFLATEX_PATH,
             "-interaction=nonstopmode",
             "-output-directory", output_dir, tex_path],
            capture_output=True, text=True, timeout=60,
            cwd=output_dir
        )
        if result.returncode != 0:
            logger.error(f"  pdflatex pass {pass_num + 1} failed: {result.stderr[-500:]}")

    if not os.path.exists(pdf_path):
        raise RuntimeError(
            f"PDF compilation failed for '{filename}'. "
            f"Last error: {result.stderr[-500:] if result else 'unknown'}"
        )

    # Parse page count from pdflatex stdout: "Output written on ... (N pages, ...)"
    page_count = 1
    if result and result.stdout:
        match = re.search(r'\((\d+) page', result.stdout)
        if match:
            page_count = int(match.group(1))

    # Clean up auxiliary files
    for ext in [".aux", ".log", ".out"]:
        aux = os.path.join(output_dir, f"{filename}{ext}")
        if os.path.exists(aux):
            os.remove(aux)

    logger.info(f"  📄 PDF created: {pdf_path} ({page_count} page{'s' if page_count != 1 else ''})")
    return pdf_path, page_count
