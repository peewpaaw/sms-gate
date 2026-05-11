from sqlalchemy import select

from app.models.enums import MailingStatus, SmsMessageStatus, UserRole
from app.models.provider import Provider
from app.models.sms_batch import SmsBatch
from app.models.sms_message import SmsMessage
from app.models.user import User
from app.schemas.mailing import MailingCreate, SmsMessageCreate
from app.services.mailing import create_mailing, generate_provider_custom_id
from app.services.security import hash_api_key
from app.services.statuses import aggregate_mailing_status


async def test_single_sms_is_created_as_mailing(session):
    user = User(email="ui@example.com", api_key_hash=hash_api_key("key"), role=UserRole.UI)
    provider = Provider(
        code="fake",
        name="Fake",
        is_active=True,
        max_batch_size=500,
        capabilities={"custom_id": True},
    )
    session.add_all([user, provider])
    await session.flush()

    response = await create_mailing(
        session,
        user,
        MailingCreate(
            provider_code="fake",
            sender="ACME",
            messages=[SmsMessageCreate(msisdn="+375447222120", text="hello")],
        ),
        publish=False,
    )

    assert response.status == MailingStatus.QUEUED
    assert len(response.messages) == 1

    messages = (await session.scalars(select(SmsMessage))).all()
    batches = (await session.scalars(select(SmsBatch))).all()
    assert len(messages) == 1
    assert len(batches) == 1


async def test_batch_splitting_respects_provider_limit(session):
    user = User(email="ui@example.com", api_key_hash=hash_api_key("key"), role=UserRole.UI)
    provider = Provider(
        code="fake",
        name="Fake",
        is_active=True,
        max_batch_size=2,
        capabilities={"custom_id": True},
    )
    session.add_all([user, provider])
    await session.flush()

    await create_mailing(
        session,
        user,
        MailingCreate(
            provider_code="fake",
            sender="ACME",
            messages=[
                SmsMessageCreate(msisdn="375447222120", text="one"),
                SmsMessageCreate(msisdn="375447222121", text="two"),
                SmsMessageCreate(msisdn="375447222122", text="three"),
            ],
        ),
        publish=False,
    )

    batches = (await session.scalars(select(SmsBatch).order_by(SmsBatch.created_at))).all()
    assert [batch.message_count for batch in batches] == [2, 1]


def test_provider_custom_id_fits_first_provider_limit():
    assert len(generate_provider_custom_id()) <= 20


def test_aggregate_mailing_status():
    assert aggregate_mailing_status([SmsMessageStatus.DELIVERED]) == MailingStatus.DELIVERED
    assert (
        aggregate_mailing_status([SmsMessageStatus.DELIVERED, SmsMessageStatus.FAILED])
        == MailingStatus.PARTIALLY_DELIVERED
    )
