from typing import Any
import logging

from app.domains.providers.beltelecom.mapping import (
    map_provider_status_to_mailing_status,
)
from app.domains.providers.base.exceptions import ProviderTemporaryError
from ..base.provider import (
    ProviderBatch,
    ProviderOneMessageSendResponse,
    ProviderOneMessageStatusResponse,
    ProviderSendResponse,
    ProviderStatusResponse,
)
from .client import BeltelecomClient


logger = logging.getLogger(__name__)


class BeltelecomProvider:
    code = "beltelecom"
    max_batch_size = 1

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

        csrf_token = await self._client.get_csrf_token()
        results: list[ProviderOneMessageSendResponse] = []

        for message in batch.messages:
            if message.external_id:
                result = ProviderOneMessageSendResponse(
                    message_id=message.message_id, external_id=message.external_id
                )
                results.append(result)
                continue

            payload = {
                "webform_id": "sms_rassylka",
                "name": batch.name,
                "text": message.text,
                "msisdn": message.msisdn,
                "date_time": message.send_on.isoformat(),
                "ukazhite_nomera_telefonov_do_10_nomerov": [message.msisdn],
            }

            response = await self._client.submit_sms(payload, csrf_token)
            sid = response.get("sid")

            if not sid:
                raise ProviderTemporaryError("Beltelecom returned empty SID")

            result = ProviderOneMessageSendResponse(
                message_id=message.message_id, external_id=sid
            )
            results.append(result)

        return ProviderSendResponse(status=True, messages=results)

    async def get_status(self, external_id: str) -> ProviderStatusResponse:
        response = await self._client.get_sms_status(sid=external_id)
        phone_list: list[dict[str, Any]] = response.get("phoneList", [])

        results: list[ProviderOneMessageStatusResponse] = []
        for msisdn in phone_list:
            logger.info(
                "Beltelecom msisdn status",
                extra={
                    "msisdn": msisdn,
                    "status": msisdn.get("status"),
                    "status_name": msisdn.get("statusName"),
                },
            )
            result = ProviderOneMessageStatusResponse(
                message_id=None,
                msisdn=msisdn.get("phoneNumber"),
                status=map_provider_status_to_mailing_status(msisdn.get("status")),
                # code=msisdn.get("status"),
                # name=msisdn.get("statusName"),
            )
            results.append(result)
        return ProviderStatusResponse(
            status=response.get("status"), messages_status=results
        )
