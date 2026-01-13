import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

VIKTOR_TOKEN = os.getenv("TOKEN_VK_APP")
MAX_POLL_SECONDS = int(os.getenv("VIKTOR_MAX_POLL_SECONDS", "120"))

API_BASE = os.getenv("VIKTOR_API_BASE", "https://beta.viktor.ai/api").rstrip("/")

HTTP_CONNECT_TIMEOUT = float(os.getenv("VIKTOR_HTTP_CONNECT_TIMEOUT", "5"))
HTTP_READ_TIMEOUT = float(os.getenv("VIKTOR_HTTP_READ_TIMEOUT", "120"))


def parse_json_response(response: requests.Response, context: str) -> dict:
    try:
        return response.json()
    except ValueError as exc:
        snippet = response.text[:500]
        raise RuntimeError(
            f"{context} returned non-JSON (status={response.status_code}): {snippet}"
        ) from exc


class ViktorTool(ABC):
    def __init__(
        self,
        workspace_id: int,
        entity_id: int,
        token: str | None = None,
        max_poll_seconds: int | None = None,
        api_base: str = API_BASE,
    ):
        self.workspace_id = workspace_id
        self.entity_id = entity_id
        self.token = token or VIKTOR_TOKEN
        if not self.token:
            raise ValueError("Missing VIKTOR token (TOKEN_VK_APP).")

        self.max_poll_seconds = max_poll_seconds or MAX_POLL_SECONDS
        self.api_base = api_base.rstrip("/")

        self.job_url = f"{self.api_base}/workspaces/{self.workspace_id}/entities/{self.entity_id}/jobs/"

        self.auth_headers = {"Authorization": f"Bearer {self.token}"}
        self.json_headers = {**self.auth_headers, "Content-Type": "application/json"}

    @abstractmethod
    def build_payload(self) -> dict[str, Any]:
        raise NotImplementedError

    def extract_success_payload(self, body: dict) -> dict:
        # Jobs "success" payload is in `result` per docs.
        if isinstance(body.get("result"), dict):
            return body["result"]
        # Fallback for older shapes
        if isinstance(body.get("content"), dict):
            return body["content"]
        return body

    def extract_error_message(self, body: dict) -> str:
        # Failed jobs fill `error`
        if isinstance(body.get("error"), dict):
            msg = body["error"].get("message")
            if msg:
                return str(msg)
        for k in ("error_message", "message"):
            if body.get(k):
                return str(body[k])
        return json.dumps(body)[:500]

    def poll_job(self, job_url: str) -> dict:
        deadline = time.monotonic() + self.max_poll_seconds
        sleep_s = 0.8

        while time.monotonic() < deadline:
            res = requests.get(
                job_url,
                headers=self.auth_headers,
                timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
            )
            body = parse_json_response(res, "Job polling response")
            status = body.get("status")

            if status == "success":
                logger.info("Job completed successfully!")
                return self.extract_success_payload(body)

            if status in (
                "failed",
                "cancelled",
                "error",
                "error_user",
                "error_timeout",
            ):
                raise RuntimeError(
                    f"Job failed (status={status}): {self.extract_error_message(body)}"
                )

            logger.info(f"Job status: {status}, polling again...")
            time.sleep(sleep_s)
            sleep_s = min(sleep_s * 1.5, 5.0)

        raise TimeoutError(f"Job did not finish within {self.max_poll_seconds} seconds")

    def run(self) -> dict:
        payload = self.build_payload()

        # Force all tools to run async + we poll ourselves
        payload["poll_result"] = False

        logger.info(f"Submitting job to {self.job_url}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(
            url=self.job_url,
            headers=self.json_headers,
            json=payload,
            timeout=(HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT),
        )

        if not response.ok:
            raise RuntimeError(
                f"Job submission failed (status={response.status_code}): {response.text[:500]}"
            )

        job_data = parse_json_response(response, "Job submission response")

        # When job is still running you get a `url` to poll.
        job_url = job_data.get("url")
        if job_url:
            logger.info(f"Job created: {job_url}")
            return self.poll_job(job_url)

        # In case the platform returns a completed job payload anyway
        status = job_data.get("status")
        if status == "success":
            logger.info("Job completed synchronously")
            return self.extract_success_payload(job_data)

        raise RuntimeError(f"Unexpected job response: {job_data}")
