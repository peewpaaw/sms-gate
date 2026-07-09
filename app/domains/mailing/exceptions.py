class MailingNotFoundError(Exception):
    """Mailing id does not exist."""


class MailingStatusUpdateForbiddenError(Exception):
    """Mailing cannot be updated unless status is CREATED."""


class MailingStatusDeleteForbiddenError(Exception):
    """Mailing cannot be deleted unless status is CREATED."""


class MessageNotFoundError(Exception):
    """Message id does not exist for the given mailing."""


class MessageStatusMutationForbiddenError(Exception):
    """Message cannot be updated or deleted unless status is CREATED."""


class MailingStatusPublishForbiddenError(Exception):
    """Mailing cannot be published unless status is CREATED."""


class MailingBatchesNotEmptyError(Exception):
    """Mailing batches are not empty."""


class MailingMessagesEmptyError(Exception):
    """Mailing messages are empty."""
