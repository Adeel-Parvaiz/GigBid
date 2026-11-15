"""Bounded document loaders. Repository material is supplied exclusively by GitHub MCP."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import PurePosixPath

MAX_BYTES = 2_000_000
KINDS = {'cv', 'case_study', 'readme', 'code', 'review', 'past_proposal'}
CODE_SUFFIXES = {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rs', '.cs', '.cpp', '.c', '.h', '.sql', '.sh', '.rb', '.ipynb'}


def load_document(filename: str, content: bytes, kind: str) -> str:
    if kind not in KINDS or not content or len(content) > MAX_BYTES:
        raise ValueError('Choose a supported nonempty document of at most 2 MB')
    suffix = PurePosixPath(filename).suffix.lower()
    if kind == 'cv' and suffix == '.pdf':
        from pypdf import PdfReader
        try:
            pdf = PdfReader(BytesIO(content))
            if pdf.is_encrypted or len(pdf.pages) > 100:
                raise ValueError('Use an unencrypted PDF with at most 100 pages')
            text = '\n\n'.join(page.extract_text() or '' for page in pdf.pages)
        except Exception as error:
            raise ValueError('Cannot extract this PDF; use an unencrypted text PDF, not a scanned image') from error
    else:
        allowed = {'.md', '.markdown', '.txt', '.json'} if kind != 'code' else CODE_SUFFIXES
        if kind == 'readme':
            allowed.add('.rst')
        if suffix not in allowed and not (kind == 'readme' and PurePosixPath(filename).name.lower() == 'readme'):
            raise ValueError('Unsupported file extension for this document type')
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError as error:
            raise ValueError('Use UTF-8 text') from error
        if suffix == '.json' and kind in {'review', 'past_proposal'}:
            try:
                records = json.loads(text)
                records = records if isinstance(records, list) else [records]
                if not records or not all(isinstance(r, dict) and isinstance(r.get('text'), str) for r in records):
                    raise ValueError('Each JSON record needs a text string')
                text = '\n\n'.join(r['text'] for r in records)
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError('Use JSON objects with a text field') from error
    if not text.strip() or '\x00' in text or len(text) > 1_000_000:
        raise ValueError('No usable text found (scanned PDFs need OCR); maximum extracted text is 1 million characters')
    return text.strip().replace('\r\n', '\n')


def fixed_chunks(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    if size <= overlap or overlap < 0:
        raise ValueError('Chunk size must exceed overlap')
    result = []
    for start in range(0, len(text), size - overlap):
        chunk = text[start:start + size].strip()
        if chunk:
            result.append(chunk)
        if start + size >= len(text):
            break
    return result
