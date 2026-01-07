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

ENV = os.getenv("VIKTOR_ENV", "beta")
VIKTOR_TOKEN = os.getenv("VIKTOR_TOKEN")
MAX_POLL_SECONDS = int(os.getenv("VIKTOR_MAX_POLL_SECONDS", "60"))


def parse_json_response(response: requests.Response, context: str) -> dict:
    try:
        return response.json()
    except requests.JSONDecodeError as exc:
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
    ):
        self.workspace_id = workspace_id
        self.entity_id = entity_id
        self.token = token or VIKTOR_TOKEN
        self.max_poll_seconds = max_poll_seconds or MAX_POLL_SECONDS

        api_base = f"https://{ENV}.viktor.ai/api"
        self.job_url = (
            f"{api_base}/workspaces/{self.workspace_id}/entities/{self.entity_id}/jobs/"
        )

        self.auth_headers = {"Authorization": f"Bearer {self.token}"}
        self.json_headers = {**self.auth_headers, "Content-Type": "application/json"}

    @abstractmethod
    def build_payload(self) -> dict[str, Any]:
        pass

    def _poll_job(self, job_url: str) -> dict:
        deadline = time.time() + self.max_poll_seconds
        while time.time() < deadline:
            res = requests.get(job_url, headers=self.auth_headers)
            body = parse_json_response(res, "Job polling response")
            status = body.get("status")

            if status == "success":
                logger.info("Job completed successfully!")
                return body.get("content", {})

            if status in ("error", "error_user"):
                raise RuntimeError(f"Job failed: {body.get('error_message')}")

            logger.info(f"Job status: {status}, polling again...")
            time.sleep(1)

        raise TimeoutError(f"Job did not finish within {self.max_poll_seconds} seconds")

    def run(self) -> dict:
        payload = self.build_payload()

        logger.info(f"Submitting job to {self.job_url}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(
            url=self.job_url, headers=self.json_headers, json=payload
        )

        if not response.ok:
            raise RuntimeError(
                f"Job submission failed (status={response.status_code}): {response.text[:500]}"
            )

        job_data = parse_json_response(response, "Job submission response")
        job_url = job_data.get("url")
        status = job_data.get("status")
        kind = job_data.get("kind")

        if job_url:
            logger.info(f"Job created: {job_url}")
            return self._poll_job(job_url)
        elif status == "success" and kind == "result":
            logger.info("Job completed synchronously")
            return job_data.get("content", {})
        else:
            raise RuntimeError(f"Unexpected job response: {job_data}")
