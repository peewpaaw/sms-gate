from typing import Any
from ..base.provider import (
    ProviderBatch,
    ProviderOneMessageSendResponse,
    ProviderOneMessageStatusResponse,
    ProviderSendResponse,
    ProviderStatusResponse,
    ProviderTemporaryError,
)
from .client import BeltelecomClient


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
                "name": "",  # TODO: в описании есть понятие "Заголовок сообщения". У А1 - нет.
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
            result = ProviderOneMessageStatusResponse(
                message_id=None,
                msisdn=msisdn.get("phoneNumber"),
                code=msisdn.get("status"),
                name=msisdn.get("statusName"),
            )
            results.append(result)
        return ProviderStatusResponse(
            status=response.get("status"), messages_status=results
        )
