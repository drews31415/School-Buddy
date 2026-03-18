"""
Amazon Textract를 이용한 PDF 텍스트 추출
"""
import os

import boto3

_REGION   = os.environ.get("REGION", "us-east-1")
_textract = boto3.client("textract", region_name=_REGION)

# 페이지당 최대 처리 문자 수 (Bedrock 토큰 제한 대비)
_MAX_CHARS = 8_000


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Textract DetectDocumentText로 PDF 바이트에서 텍스트를 추출한다.
    - Textract는 동기 API로 최대 10MB, 최대 1페이지 (detect_document_text 제한)
    - 다중 페이지 PDF는 start_document_text_detection (비동기) 필요.
      현재는 단일 페이지 가정통신문 기준으로 동기 API 사용.
    """
    response = _textract.detect_document_text(
        Document={"Bytes": pdf_bytes}
    )

    lines: list[str] = []
    for block in response.get("Blocks", []):
        if block.get("BlockType") == "LINE":
            text = block.get("Text", "").strip()
            if text:
                lines.append(text)

    extracted = "\n".join(lines)

    # 너무 긴 경우 앞부분만 사용 (Bedrock 입력 토큰 절감)
    if len(extracted) > _MAX_CHARS:
        extracted = extracted[:_MAX_CHARS] + "\n...(이하 생략)"

    return extracted or "(텍스트를 추출할 수 없었습니다)"
