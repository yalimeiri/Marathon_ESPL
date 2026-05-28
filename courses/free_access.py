"""
courses/free_access.py
──────────────────────────────────────────────────────────────────────────────
Utility functions for the Free Access Campaign system.

Public API
──────────
  try_grant_free_access(user)
      Called automatically at registration. Grants a free slot if an active
      campaign has slots remaining. Race-condition-safe via select_for_update.

  manually_grant_free_access(user, campaign, counts_toward_limit=True, note="")
      Called from the Django Admin. Grants a free slot to any user without
      going through the registration flow. Respects the slot limit by default;
      pass counts_toward_limit=False to grant without consuming a slot.
"""

import logging
from django.db import transaction

logger = logging.getLogger(__name__)


def try_grant_free_access(user):
    """
    Automatically called at registration.

    Checks if there is an active FreeAccessCampaign with slots remaining.
    If so, grants PURCHASED-level access to all included categories and
    records a FreeAccessSlot for the user.

    Uses select_for_update() to prevent two simultaneous registrations
    from both claiming the last slot.

    Returns True if a slot was granted, False otherwise.
    """
    from .models import FreeAccessCampaign, FreeAccessSlot

    campaign = FreeAccessCampaign.objects.filter(is_active=True).first()
    if not campaign:
        return False

    # Quick pre-check before acquiring DB lock (avoids lock contention
    # when slots are obviously full)
    if campaign.is_full:
        return False

    # Duplicate-slot guard: don't grant if user already has a slot for this campaign
    if FreeAccessSlot.objects.filter(user=user, campaign=campaign).exists():
        logger.info("User '%s' already has a slot for campaign #%s.", user.username, campaign.pk)
        return False

    with transaction.atomic():
        # Lock the campaign row to prevent concurrent over-grants
        campaign = FreeAccessCampaign.objects.select_for_update().filter(is_active=True).first()
        if not campaign or campaign.is_full:
            return False

        # Re-check inside the lock
        if FreeAccessSlot.objects.filter(user=user, campaign=campaign).exists():
            return False

        return _do_grant(user, campaign, counts_toward_limit=True)


def manually_grant_free_access(user, campaign, counts_toward_limit=True, note=""):
    """
    Admin-initiated grant. Can be used regardless of registration flow.

    Parameters
    ----------
    user                  : User instance to grant access to.
    campaign              : FreeAccessCampaign instance to use.
    counts_toward_limit   : If False, the slot is recorded but does NOT
                            decrement the remaining slots counter.
    note                  : Optional admin note stored on the FreeAccessSlot.

    Returns True if a slot was granted, False if the user already has one
    or the campaign has no slots left (when counts_toward_limit=True).
    """
    from .models import FreeAccessSlot

    # Check if user already has a slot for this campaign
    if FreeAccessSlot.objects.filter(user=user, campaign=campaign).exists():
        logger.info("User '%s' already has a free slot for campaign #%s.", user.username, campaign.pk)
        return False

    # If this counts toward the limit, enforce the cap
    if counts_toward_limit and campaign.is_full:
        logger.info(
            "Campaign #%s is full (%s/%s). Cannot grant manual slot to '%s'.",
            campaign.pk, campaign.slots_used, campaign.slot_limit, user.username
        )
        return False

    with transaction.atomic():
        return _do_grant(user, campaign, counts_toward_limit=counts_toward_limit, note=note)


def _do_grant(user, campaign, counts_toward_limit=True, note=""):
    """
    Internal: creates a FreeAccessSlot, then recalculates access via the
    unified calculator. Must be called inside an atomic block.

    Order matters: the slot record is created FIRST so that
    recalculate_user_access() can see it when it runs.
    """
    from .models import FreeAccessSlot
    from .access import recalculate_user_access

    # 1. Record the slot first
    FreeAccessSlot.objects.create(
        user=user,
        campaign=campaign,
        counts_toward_limit=counts_toward_limit,
        note=note,
    )

    # 2. Recalculate access for each included category
    for category in campaign.included_categories.all():
        recalculate_user_access(user, category)

    logger.info(
        "Free access slot granted to '%s' for campaign #%s (counts=%s).",
        user.username, campaign.pk, counts_toward_limit
    )
    return True
