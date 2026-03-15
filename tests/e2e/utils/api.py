"""
HTTP API 헬퍼 유틸.
E2E_API_BASE_URL + E2E_ACCESS_TOKEN 환경변수 필요.
"""
import time
from typing import Any, Optional

import requests

from tests.e2e.config import ACCESS_TOKEN, API_BASE_URL


class APIClient:
    """School Buddy HTTP API 클라이언트 (E2E 전용)."""

    def __init__(self, base_url: str = API_BASE_URL, token: str = ACCESS_TOKEN):
        if not base_url:
            raise RuntimeError(
                "E2E_API_BASE_URL 환경변수가 설정되지 않았습니다. "
                "dev 배포 후 API Gateway URL을 설정하세요."
            )
        self.base_url = base_url.rstrip("/")
        self.session  = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        })

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.session.get(f"{self.base_url}{path}", **kwargs)

    def post(self, path: str, json: Any = None, **kwargs) -> requests.Response:
        return self.session.post(f"{self.base_url}{path}", json=json, **kwargs)

    def put(self, path: str, json: Any = None, **kwargs) -> requests.Response:
        return self.session.put(f"{self.base_url}{path}", json=json, **kwargs)

    def timed_post(self, path: str, json: Any = None, **kwargs) -> tuple[requests.Response, float]:
        """POST 호출 + 응답 시간(초) 반환."""
        start = time.monotonic()
        resp  = self.post(path, json=json, **kwargs)
        elapsed = time.monotonic() - start
        return resp, elapsed

    def timed_get(self, path: str, **kwargs) -> tuple[requests.Response, float]:
        """GET 호출 + 응답 시간(초) 반환."""
        start = time.monotonic()
        resp  = self.get(path, **kwargs)
        elapsed = time.monotonic() - start
        return resp, elapsed

    def post_multipart(
        self,
        path: str,
        files: dict,
        data: Optional[dict] = None,
    ) -> tuple[requests.Response, float]:
        """multipart/form-data POST + 응답 시간(초) 반환."""
        headers = {k: v for k, v in self.session.headers.items() if k != "Content-Type"}
        start = time.monotonic()
        resp  = self.session.post(
            f"{self.base_url}{path}",
            files=files,
            data=data or {},
            headers=headers,
        )
        elapsed = time.monotonic() - start
        return resp, elapsed
