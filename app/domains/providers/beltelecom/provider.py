from collections import defaultdict
from typing import Any
import logging

from app.domains.providers.beltelecom.mapping import (
    map_provider_status_to_mailing_status,
)
from app.domains.providers.base.exceptions import ProviderTemporaryError
from ..base.provider import (
    ProviderBatch,
    ProviderMessage,
    ProviderOneMessageSendResponse,
    ProviderOneMessageStatusResponse,
    ProviderSendResponse,
    ProviderStatusResponse,
)
from .client import BeltelecomClient


logger = logging.getLogger(__name__)


class BeltelecomProvider:
    code = "beltelecom"
    max_batch_size = 10

    def __init__(
        self, base_url: str, username: str, password: str, timeout_sec: float = 15.0
    ) -> None:
        self._client = BeltelecomClient(
            base_url=base_url,
            username=username,
            password=password,
            timeout_sec=timeout_sec,
        )

    async def send(self, batch: ProviderBatch) -> ProviderSendResponse:
        if not batch.messages:
            raise ProviderTemporaryError("Batch is empty")

        results: list[ProviderOneMessageSendResponse] = []
        pending: list[ProviderMessage] = []

        for message in batch.messages:
            if message.external_id:
                results.append(
                    ProviderOneMessageSendResponse(
                        message_id=message.message_id,
                        external_id=message.external_id,
                    )
                )
                continue
            pending.append(message)

        if not pending:
            return ProviderSendResponse(status=True, messages=results)

        csrf_token = await self._client.get_csrf_token()

        groups: dict[str, list[ProviderMessage]] = defaultdict(list)
        for message in pending:
            groups[message.text].append(message)

        for text, messages in groups.items():
            payload = {
                "webform_id": "sms_rassylka",
                "name": batch.name,
                "text": text,
                "date_time": batch.send_on.isoformat(),
                "ukazhite_nomera_telefonov_do_10_nomerov": [
                    message.msisdn for message in messages
                ],
            }

            response = await self._client.submit_sms(payload, csrf_token)
            sid = response.get("sid")
            if not sid:
                raise ProviderTemporaryError("Beltelecom returned empty SID")

            for message in messages:
                results.append(
                    ProviderOneMessageSendResponse(
                        message_id=message.message_id,
                        external_id=sid,
                    )
                )

        return ProviderSendResponse(status=True, messages=results)

    async def get_status(self, external_id: str) -> ProviderStatusResponse:
        response = await self._client.get_sms_status(sid=external_id)
        phone_list: list[dict[str, Any]] = response.get("phoneList", [])

        results: list[ProviderOneMessageStatusResponse] = []
        for item in phone_list:
            logger.info(
                "Beltelecom msisdn status",
                extra={
                    "msisdn": item,
                    "status": item.get("status"),
                    "status_name": item.get("statusName"),
                },
            )
            results.append(
                ProviderOneMessageStatusResponse(
                    message_id=None,
                    msisdn=item.get("phoneNumber"),
                    status=map_provider_status_to_mailing_status(item.get("status")),
                )
            )

        return ProviderStatusResponse(
            status=response.get("status"),
            messages_status=results,
        )
