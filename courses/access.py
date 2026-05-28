"""
courses/access.py
──────────────────────────────────────────────────────────────────────────────
Unified Access Calculator — the single source of truth for what access level
a user should have to a given category.

Public API
──────────
  recalculate_user_access(user, category)
      Evaluates all access sources (purchases, campaign slots) and writes the
      correct CategoryAccess record.  Every code path that changes a user's
      access should call this function instead of writing directly.

Priority order (highest wins):
  1. Approved purchase       → PURCHASED (120-day expiry from approval)
  2. Active campaign slot    → PURCHASED (campaign-defined expiry)
  3. Pending purchase        → PENDING
  4. Nothing                 → VISITING
"""

import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def recalculate_user_access(user, category):
    """
    Evaluate every access source for (user, category) and write the correct
    CategoryAccess row.

    Must be safe to call at any time — idempotent and side-effect-free beyond
    the CategoryAccess table.
    """
    from .models import (
        Purchase, CategoryAccess, AccessTier,
        FreeAccessCampaign, FreeAccessSlot,
    )

    access, _ = CategoryAccess.objects.get_or_create(
        user=user,
        category=category,
    )

    # ── Source 1: Approved purchases (highest priority) ──────────────────
    purchases = Purchase.objects.filter(user=user, category=category)

    if purchases.filter(status='APPROVED').exists():
        access.access_level = AccessTier.PURCHASED
        # Only set expiry if it isn't already set (preserve existing expiry)
        if not access.expires_at:
            access.expires_at = timezone.now() + timedelta(days=120)
        access.save()
        return

    # ── Source 2: Active campaign slot ───────────────────────────────────
    active_slot = FreeAccessSlot.objects.filter(
        user=user,
        campaign__is_active=True,
        campaign__included_categories=category,
    ).select_related('campaign').first()

    if active_slot:
        campaign = active_slot.campaign
        expires_at = None
        if campaign.access_duration_days:
            expires_at = active_slot.granted_at + timedelta(days=campaign.access_duration_days)
            # If the campaign access has already expired, treat as no slot
            if expires_at <= timezone.now():
                access.access_level = AccessTier.VISITING
                access.expires_at = None
                access.save()
                return
        access.access_level = AccessTier.PURCHASED
        access.expires_at = expires_at
        access.save()
        return

    # ── Source 3: Pending purchase ───────────────────────────────────────
    if purchases.filter(status='PENDING').exists():
        access.access_level = AccessTier.PENDING
        access.expires_at = None
        access.save()
        return

    # ── Source 4: No access ─────────────────────────────────────────────
    access.access_level = AccessTier.VISITING
    access.expires_at = None
    access.save()
