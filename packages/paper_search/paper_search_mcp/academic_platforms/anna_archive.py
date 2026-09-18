"""Compatibility acquisition adapter: explicit source consent, no challenge routes.

New runs record consent with ez rescue --allow-anna. Legacy callers must supply
EZRESEARCH_ANNA_CONSENT_FILE pointing to an expiring source-specific receipt.
No mirror rotation, browser challenge handling or SciDB routes are implemented.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AnnaArchiveFetcher:
    def __init__(self, output_dir: str = "./downloads", base_url: str = ""):
        self.output_dir = Path(output_dir)
        self.base_url = base_url  # retained API shape; consent selects the exact URL

    def download_pdf(self, identifier: str) -> Optional[str]:
        receipt_path = os.environ.get("EZRESEARCH_ANNA_CONSENT_FILE")
        if not receipt_path:
            logger.warning("Anna disabled: a source-specific consent receipt is required.")
            return None
        from ez.acquisition import Retriever
        from ez.consent import validate_anna
        from ez.state import atomic_json, read_json
        try:
            receipt = read_json(receipt_path)
            if receipt.get("identifier") != identifier:
                raise ValueError("Consent does not match the requested identifier")
            source = {"source_id": receipt["source_id"], "anna_consent": receipt}
            source["doi" if identifier.startswith("10.") else "title"] = identifier
            validate_anna(receipt, source)
            result = Retriever(self.output_dir, source["source_id"], seconds=120, attempts=1).acquire(source, candidates=[])
            if result.get("pdf_source") != "anna_archive" or result.get("validation_status") != "valid":
                return None
            path = result["pdf_path"]
            atomic_json(Path(path + ".provenance.json"), result)
            return path
        except (ValueError, OSError, KeyError) as exc:
            logger.warning("Anna acquisition paused: %s", type(exc).__name__)
            return None


def main():
    parser = argparse.ArgumentParser(description="Acquire an explicitly consented Anna source")
    parser.add_argument("--doi", required=True)
    parser.add_argument("--output", default="./downloads")
    args = parser.parse_args()
    path = AnnaArchiveFetcher(args.output).download_pdf(args.doi)
    if not path:
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
