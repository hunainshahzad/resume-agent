"""Resume Agent - CLI entry point."""

import asyncio
import sys
import logging

import click

# Add project root to path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

from agents.orchestrator import Orchestrator


@click.command()
@click.option("--url", help="Process a single job URL")
@click.option("--batch", is_flag=True, help="Process all pending URLs from sheet")
@click.option("--dry-run", is_flag=True, help="Extract JD only, no resume generation")
@click.option("--verbose", is_flag=True, help="Enable debug logging")
def main(url, batch, dry_run, verbose):
    """Multi-Agent Resume Automation Pipeline.
    
    Reads job URLs, extracts JDs (Gemini), tailors resumes (Claude),
    reviews (GPT-5.4 Nano), refines (Claude), and compiles PDFs.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S"
    )

    orchestrator = Orchestrator()

    if url:
        asyncio.run(orchestrator.process_single(url))
    elif batch:
        asyncio.run(orchestrator.run_batch())  # Hybrid parallel/sequential
    elif dry_run:
        click.echo("Dry-run mode: extract JDs only (not implemented yet)")
    else:
        click.echo("Usage: python main.py --url <URL> or --batch")
        click.echo("       python main.py --batch --verbose")


if __name__ == "__main__":
    main()
