"""Bilingual copy for seller-facing status payloads."""

STATUS_MESSAGES = {
    'incomplete': (
        'Usajili haujakamilika bado.',
        'Onboarding is not complete yet.',
    ),
    'pending_id': (
        'Tafadhali pakia nyaraka za utambulisho.',
        'Please upload your identity documents.',
    ),
    'under_review': (
        'Nyaraka zako zinapitiwa. Subiri hadi masaa 24.',
        'Your documents are under review. Please wait up to 24 hours.',
    ),
    'verified': (
        'Akaunti yako imeidhinishwa.',
        'Your identity is verified.',
    ),
    'rejected': (
        'Nyaraka zako hazikuidhinishwa. Tafadhali sasisha na utume tena.',
        'Your documents were not approved. Please update and resubmit.',
    ),
    'suspended': (
        'Duka lako limefungwa kwa muda. Wasiliana na usaidizi.',
        'Your store has been suspended. Please contact support.',
    ),
}


def bilingual_status(status: str) -> dict:
    sw, en = STATUS_MESSAGES.get(
        status,
        ('Hali haijulikani.', 'Unknown status.'),
    )
    return {'message_sw': sw, 'message_en': en}


IDENTITY_DOCS_SUBMITTED = (
    'Nyaraka zimepokewa. Tutakagua ndani ya masaa 24.',
    'Documents submitted successfully. We will review within 24 hours.',
)


def bilingual_identity_submitted() -> dict:
    sw, en = IDENTITY_DOCS_SUBMITTED
    return {'message_sw': sw, 'message_en': en, 'message': en}
