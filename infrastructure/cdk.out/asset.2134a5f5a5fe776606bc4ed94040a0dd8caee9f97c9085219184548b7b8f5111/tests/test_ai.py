"""
processor/ai.py 단위 테스트.
invoke_model()을 mock하여 Bedrock 호출 없이 AI 파이프라인 로직을 검증한다.
"""
import json
from unittest.mock import patch

import pytest

from processor.ai import summarize, judge_importance, translate, run_full_pipeline, _fill, _load_prompt
from processor.models import SummaryResult, ImportanceResult, TranslationResult
from bedrock import BedrockResponseError  # shared-utils (conftest에서 sys.path 설정됨)


# ── _fill 유틸 ────────────────────────────────────────────────

class TestFill:
    def test_simple_substitution(self):
        assert _fill("Hello {name}!", name="World") == "Hello World!"

    def test_json_braces_untouched(self):
        """JSON 예시의 중괄호는 치환되지 않아야 함."""
        template = 'Output: {"key": "value"} input={notice_text}'
        result = _fill(template, notice_text="test")
        assert '{"key": "value"}' in result
        assert "test" in result

    def test_missing_placeholder_unchanged(self):
        result = _fill("{a} and {b}", a="A")
        assert "{b}" in result  # 치환 대상 없으면 그대로


# ── _load_prompt ──────────────────────────────────────────────

class TestLoadPrompt:
    def test_returns_system_and_user(self):
        sys_p, usr_p = _load_prompt("notice_summary.txt")
        assert len(sys_p) > 10
        assert "{notice_text}" in usr_p

    def test_verification_section_excluded(self):
        """[VERIFICATION] 이후 주석이 user 프롬프트에 포함되지 않아야 함."""
        _, usr = _load_prompt("notice_summary.txt")
        assert "[VERIFICATION]" not in usr
        assert "# ──" not in usr

    def test_translate_prompt_has_placeholders(self):
        _, usr = _load_prompt("notice_translate.txt")
        assert "{summary_text}" in usr
        assert "{target_language}" in usr
        assert "{language_name}" in usr


# ── summarize ─────────────────────────────────────────────────

class TestSummarize:
    def _bedrock_response(self, summary, keywords):
        return json.dumps({"summary": summary, "keywords": keywords})

    def test_returns_summary_result(self):
        with patch("processor.ai.invoke_model", return_value=self._bedrock_response("요약문", ["키워드1"])):
            result = summarize("공지 원문 텍스트", "제목")
        assert isinstance(result, SummaryResult)
        assert result.summary == "요약문"
        assert result.keywords == ["키워드1"]

    def test_empty_original_uses_title(self):
        """원문 없으면 제목을 원문으로 사용."""
        captured_args = {}
        def mock_invoke(system, user, **kwargs):
            captured_args["user"] = user
            return self._bedrock_response("요약", [])

        with patch("processor.ai.invoke_model", side_effect=mock_invoke):
            summarize("", title="제목만 있는 공지")

        assert "제목만 있는 공지" in captured_args["user"]

    def test_both_empty_uses_fallback(self):
        """원문·제목 모두 없으면 fallback 텍스트 사용."""
        captured_args = {}
        def mock_invoke(system, user, **kwargs):
            captured_args["user"] = user
            return self._bedrock_response("요약", [])

        with patch("processor.ai.invoke_model", side_effect=mock_invoke):
            summarize("", "")

        assert "(원문 없음)" in captured_args["user"]

    def test_missing_keywords_defaults_empty(self):
        with patch("processor.ai.invoke_model", return_value='{"summary": "s"}'):
            result = summarize("텍스트")
        assert result.keywords == []

    def test_bedrock_response_error_propagates(self):
        """BedrockResponseError는 재발생."""
        with patch("processor.ai.invoke_model", side_effect=BedrockResponseError("JSON 오류")):
            with pytest.raises(BedrockResponseError):
                summarize("텍스트")


# ── judge_importance ──────────────────────────────────────────

class TestJudgeImportance:
    def test_high_importance(self):
        resp = json.dumps({"importance": "HIGH", "reason": "납부 필요"})
        with patch("processor.ai.invoke_model", return_value=resp):
            result = judge_importance("납부 안내 요약")
        assert result.importance == "HIGH"
        assert result.reason == "납부 필요"

    def test_medium_importance(self):
        resp = json.dumps({"importance": "MEDIUM", "reason": "일정 변경"})
        with patch("processor.ai.invoke_model", return_value=resp):
            result = judge_importance("행사 안내")
        assert result.importance == "MEDIUM"

    def test_low_importance(self):
        resp = json.dumps({"importance": "LOW", "reason": "참고용"})
        with patch("processor.ai.invoke_model", return_value=resp):
            result = judge_importance("수상 소식")
        assert result.importance == "LOW"

    def test_invalid_importance_falls_back_to_medium(self):
        """비정상 importance 값 → MEDIUM으로 대체."""
        resp = json.dumps({"importance": "CRITICAL", "reason": "이유"})
        with patch("processor.ai.invoke_model", return_value=resp):
            result = judge_importance("공지")
        assert result.importance == "MEDIUM"

    def test_missing_importance_defaults_medium(self):
        with patch("processor.ai.invoke_model", return_value='{"reason": "이유"}'):
            result = judge_importance("공지")
        assert result.importance == "MEDIUM"


# ── translate ─────────────────────────────────────────────────

class TestTranslate:
    def _resp(self, translation="번역문", tip="팁", items=None):
        return json.dumps({
            "translation": translation,
            "culturalTip": tip,
            "checklistItems": items or [],
        })

    def test_returns_translation_result(self):
        with patch("processor.ai.invoke_model", return_value=self._resp()):
            result = translate("요약문", "vi")
        assert isinstance(result, TranslationResult)
        assert result.translation == "번역문"
        assert result.culturalTip == "팁"

    def test_language_name_injected(self):
        """번역 프롬프트에 언어명이 올바르게 주입되는지 확인."""
        captured = {}
        def mock_invoke(system, user, **kwargs):
            captured["user"] = user
            return self._resp()

        with patch("processor.ai.invoke_model", side_effect=mock_invoke):
            translate("요약문", "zh-CN")

        assert "简体中文" in captured["user"]
        assert "zh-CN" in captured["user"]

    def test_unknown_lang_uses_code_as_name(self):
        """등록되지 않은 언어 코드 → 코드 자체를 언어명으로 사용."""
        with patch("processor.ai.invoke_model", return_value=self._resp()):
            result = translate("요약문", "xx")
        assert isinstance(result, TranslationResult)

    def test_checklist_items_included(self):
        with patch("processor.ai.invoke_model", return_value=self._resp(items=["항목1", "항목2"])):
            result = translate("요약문", "en")
        assert len(result.checklistItems) == 2


# ── run_full_pipeline ─────────────────────────────────────────

class TestRunFullPipeline:
    def test_returns_all_three_results(self):
        summary_resp    = json.dumps({"summary": "요약", "keywords": []})
        importance_resp = json.dumps({"importance": "HIGH", "reason": "이유"})
        translate_resp  = json.dumps({"translation": "번역", "culturalTip": "", "checklistItems": []})

        call_count = [0]
        def mock_invoke(system, user, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return summary_resp
            elif call_count[0] == 2:
                return importance_resp
            return translate_resp

        with patch("processor.ai.invoke_model", side_effect=mock_invoke):
            summary, importance, translations = run_full_pipeline(
                "원문", "제목", ("vi", "en")
            )

        assert isinstance(summary, SummaryResult)
        assert isinstance(importance, ImportanceResult)
        assert "vi" in translations
        assert "en" in translations

    def test_translation_error_fills_empty(self):
        """번역 실패 시 빈값으로 채우고 계속 진행."""
        summary_resp    = json.dumps({"summary": "요약", "keywords": []})
        importance_resp = json.dumps({"importance": "LOW", "reason": "이유"})

        call_count = [0]
        def mock_invoke(system, user, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return summary_resp
            elif call_count[0] == 2:
                return importance_resp
            raise BedrockResponseError("번역 실패")

        with patch("processor.ai.invoke_model", side_effect=mock_invoke):
            _, _, translations = run_full_pipeline("원문", "제목", ("vi",))

        assert translations["vi"]["translation"] == ""
