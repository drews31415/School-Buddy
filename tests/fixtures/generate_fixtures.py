"""
E2E 테스트용 픽스처 파일 생성 스크립트.

실행:
    python tests/fixtures/generate_fixtures.py

생성 파일:
    tests/fixtures/sample_notice.jpg  — 텍스트가 포함된 테스트용 가정통신문 이미지
    tests/fixtures/sample_notices.json — 공지 샘플 데이터 10건
"""
import json
import pathlib
import struct
import zlib

FIXTURES_DIR = pathlib.Path(__file__).parent


# ── 최소 유효 JPEG 생성 (PIL 없이 순수 Python) ────────────────────────────────
def _make_minimal_jpeg() -> bytes:
    """
    실제 텍스트가 있는 가정통신문 이미지를 시뮬레이션.
    CI 환경에서 PIL/Pillow 없이 실행 가능하도록
    최소한의 유효 JPEG 바이너리를 직접 생성.
    ⚠️ 실제 테스트 실행 전에 실제 가정통신문 이미지로 교체를 권장.
    """
    # 유효한 1×1 픽셀 회색 JPEG (SOI + APP0 + DQT + SOF0 + DHT + SOS + EOI)
    return bytes([
        0xFF, 0xD8,  # SOI
        0xFF, 0xE0, 0x00, 0x10,  # APP0 마커
        0x4A, 0x46, 0x49, 0x46, 0x00,  # "JFIF\0"
        0x01, 0x01,  # 버전 1.1
        0x00,        # 픽셀 비율 단위: 없음
        0x00, 0x01, 0x00, 0x01,  # 1×1 픽셀 밀도
        0x00, 0x00,  # 썸네일 없음
        # 단순화된 DQT (양자화 테이블)
        0xFF, 0xDB, 0x00, 0x43, 0x00,
        *([16] * 64),
        # SOF0 (1×1 그레이스케일)
        0xFF, 0xC0, 0x00, 0x0B, 0x08,
        0x00, 0x01, 0x00, 0x01,  # 높이=1, 너비=1
        0x01,                    # 컴포넌트=1 (그레이스케일)
        0x01, 0x11, 0x00,
        # DHT (최소 허프만 테이블)
        0xFF, 0xC4, 0x00, 0x1F, 0x00,
        0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0A, 0x0B,
        # SOS (스캔 시작)
        0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00,
        0x3F, 0x00, 0xF8,
        # EOI
        0xFF, 0xD9,
    ])


def _make_sample_notices() -> list[dict]:
    return [
        {
            "noticeId":    f"sample-notice-{i:03d}",
            "schoolId":    "sample-school-001",
            "title":       title,
            "content":     content,
            "importance":  importance,
            "publishedAt": f"2026-03-{i + 1:02d}T09:00:00Z",
            "status":      "PROCESSED",
        }
        for i, (title, content, importance) in enumerate([
            (
                "3월 현장학습 안내",
                "3월 25일 현장학습이 예정되어 있습니다. 준비물: 도시락, 물통, 운동화. 비용: 15,000원.",
                "HIGH",
            ),
            (
                "급식 메뉴 변경 안내",
                "3월 20일 급식 메뉴가 변경되었습니다. 알레르기 정보를 확인하세요.",
                "MEDIUM",
            ),
            (
                "돌봄교실 신청 안내",
                "4월 돌봄교실 신청을 받습니다. 신청 기간: 3월 15일~3월 22일.",
                "HIGH",
            ),
            (
                "학부모 공개수업 안내",
                "4월 5일 학부모 공개수업이 있습니다. 참관을 원하시는 분은 신청서를 제출해주세요.",
                "MEDIUM",
            ),
            (
                "봄 소풍 안내",
                "4월 15일 봄 소풍이 예정되어 있습니다. 목적지: 서울 어린이공원.",
                "MEDIUM",
            ),
            (
                "예방접종 안내",
                "4월 중 독감 예방접종이 실시됩니다. 동의서를 3월 28일까지 제출해주세요.",
                "HIGH",
            ),
            (
                "도서관 이용 안내",
                "학교 도서관이 리모델링 후 재개관합니다. 4월 1일부터 이용 가능합니다.",
                "LOW",
            ),
            (
                "방과후 수업 신청 안내",
                "1학기 방과후 수업 신청을 받습니다. 신청: 3월 20일~3월 25일.",
                "MEDIUM",
            ),
            (
                "학교폭력 예방 교육 안내",
                "4월 10일 학교폭력 예방 교육이 실시됩니다. 전 학년 참여 필수입니다.",
                "LOW",
            ),
            (
                "1학기 학부모 상담 안내",
                "4월 20일~4월 24일 학부모 상담 주간입니다. 신청서를 4월 10일까지 제출해주세요.",
                "MEDIUM",
            ),
        ])
    ]


def main():
    # 1. sample_notice.jpg
    jpg_path = FIXTURES_DIR / "sample_notice.jpg"
    if not jpg_path.exists():
        jpg_path.write_bytes(_make_minimal_jpeg())
        print(f"[OK] generated: {jpg_path}")
        print(
            "   NOTE: This is a minimal valid JPEG.\n"
            "   Replace with a real school notice image before E2E testing."
        )
    else:
        print(f"[SKIP] already exists: {jpg_path}")

    # 2. sample_notices.json
    json_path = FIXTURES_DIR / "sample_notices.json"
    notices   = _make_sample_notices()
    json_path.write_text(
        json.dumps(notices, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] generated: {json_path} ({len(notices)} items)")


if __name__ == "__main__":
    main()
