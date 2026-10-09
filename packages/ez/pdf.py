"""Uniform structural validation. Identity is deliberately a separate decision."""
from hashlib import sha256
from pathlib import Path


def validate_pdf_bounded(path, timeout=30):
    import json
    import sys
    from .process import run
    result = run([sys.executable, '-m', 'ez.pdf', str(Path(path).resolve())], timeout=timeout)
    if result.returncode:
        return {'status': 'invalid', 'reason': result.reason or 'validator_failed'}
    try:
        return json.loads(result.stdout)
    except ValueError:
        return {'status': 'invalid', 'reason': 'validator_output_invalid'}


def validate_pdf(path):
    from PyPDF2 import PdfReader
    path = Path(path)
    if not path.is_file():
        return {'status': 'invalid', 'reason': 'missing_file'}
    if path.stat().st_size > 100 * 1024 * 1024:
        return {'status': 'invalid', 'reason': 'file_too_large'}
    with path.open('rb') as stream:
        prefix = stream.read(1024).lstrip()
    if not prefix.startswith(b'%PDF-'):
        return {'status': 'invalid', 'reason': 'html_instead_of_pdf' if prefix[:1] == b'<' else 'invalid_pdf'}
    try:
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted:
            return {'status': 'invalid', 'reason': 'encrypted_pdf'}
        if not len(reader.pages):
            return {'status': 'invalid', 'reason': 'empty_pdf'}
        pages = len(reader.pages)
        for page in reader.pages:
            _ = page.mediabox
    except Exception:
        return {'status': 'invalid', 'reason': 'corrupt_pdf'}
    return {'status': 'valid', 'pages': pages, 'sha256': sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size, 'validator': 'PyPDF2-structural-v1'}


if __name__ == '__main__':
    import json
    import sys
    print(json.dumps(validate_pdf(sys.argv[1])))
