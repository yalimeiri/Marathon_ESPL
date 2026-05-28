"""
courses/tests.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Unified Access Calculator and Free Access Campaign system.

Covers:
  - recalculate_user_access() priority logic
  - Purchase signal → access sync
  - Campaign grant and deactivation
  - FreeAccessSlot duplicate guards
  - Edge cases: campaign + purchase overlap, expiry, multi-campaign
"""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    Category, Purchase, CategoryAccess, AccessTier,
    FreeAccessCampaign, FreeAccessSlot,
)
from .access import recalculate_user_access
from .free_access import try_grant_free_access, manually_grant_free_access

User = get_user_model()


class AccessCalculatorTestBase(TestCase):
    """Shared setup for access calculator tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123'
        )
        self.category = Category.objects.create(
            name='Test Course', price=100
        )


class RecalculateUserAccessTest(AccessCalculatorTestBase):
    """Tests for the recalculate_user_access() function."""

    def test_no_purchase_no_slot_returns_visiting(self):
        """User with no purchase and no campaign slot gets VISITING."""
        recalculate_user_access(self.user, self.category)
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.VISITING)

    def test_pending_purchase_returns_pending(self):
        """User with a pending purchase gets PENDING."""
        Purchase.objects.create(
            user=self.user, category=self.category,
            phone_number='0501234567', payer_name='Test',
            status='PENDING'
        )
        # Signal already called recalculate_user_access
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.PENDING)

    def test_approved_purchase_returns_purchased(self):
        """User with an approved purchase gets PURCHASED."""
        Purchase.objects.create(
            user=self.user, category=self.category,
            phone_number='0501234567', payer_name='Test',
            status='APPROVED'
        )
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.PURCHASED)
        self.assertIsNotNone(access.expires_at)

    def test_rejected_purchase_returns_visiting(self):
        """User with only a rejected purchase gets VISITING."""
        Purchase.objects.create(
            user=self.user, category=self.category,
            phone_number='0501234567', payer_name='Test',
            status='REJECTED'
        )
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.VISITING)

    def test_approved_purchase_sets_expiry_once(self):
        """Expiry is set on first approval but not overwritten on recalculate."""
        purchase = Purchase.objects.create(
            user=self.user, category=self.category,
            phone_number='0501234567', payer_name='Test',
            status='APPROVED'
        )
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        original_expiry = access.expires_at

        # Recalculate again — expiry should NOT change
        recalculate_user_access(self.user, self.category)
        access.refresh_from_db()
        self.assertEqual(access.expires_at, original_expiry)


class PurchaseSignalTest(AccessCalculatorTestBase):
    """Tests that Purchase save/delete signals trigger recalculation."""

    def test_purchase_save_triggers_recalculation(self):
        """Creating a purchase triggers access recalculation via signal."""
        purchase = Purchase.objects.create(
            user=self.user, category=self.category,
            phone_number='0501234567', payer_name='Test',
            status='PENDING'
        )
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.PENDING)

        # Approve the purchase
        purchase.status = 'APPROVED'
        purchase.save()

        access.refresh_from_db()
        self.assertEqual(access.access_level, AccessTier.PURCHASED)

    def test_purchase_delete_triggers_recalculation(self):
        """Deleting a purchase triggers access recalculation via signal."""
        purchase = Purchase.objects.create(
            user=self.user, category=self.category,
            phone_number='0501234567', payer_name='Test',
            status='APPROVED'
        )
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.PURCHASED)

        # Delete the purchase
        purchase.delete()

        access.refresh_from_db()
        self.assertEqual(access.access_level, AccessTier.VISITING)


class CampaignGrantTest(AccessCalculatorTestBase):
    """Tests for the Free Access Campaign grant system."""

    def setUp(self):
        super().setUp()
        self.campaign = FreeAccessCampaign.objects.create(
            is_active=True, slot_limit=10
        )
        self.campaign.included_categories.add(self.category)

    def test_try_grant_free_access_succeeds(self):
        """try_grant_free_access grants access when campaign is active."""
        result = try_grant_free_access(self.user)
        self.assertTrue(result)

        # Check slot was created
        self.assertTrue(
            FreeAccessSlot.objects.filter(user=self.user, campaign=self.campaign).exists()
        )
        # Check access level
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.PURCHASED)

    def test_try_grant_no_active_campaign(self):
        """try_grant_free_access returns False when no campaign is active."""
        self.campaign.is_active = False
        self.campaign.save()

        result = try_grant_free_access(self.user)
        self.assertFalse(result)
        self.assertFalse(FreeAccessSlot.objects.filter(user=self.user).exists())

    def test_try_grant_campaign_full(self):
        """try_grant_free_access returns False when campaign is full."""
        self.campaign.slot_limit = 0
        self.campaign.save()

        result = try_grant_free_access(self.user)
        self.assertFalse(result)

    def test_duplicate_grant_prevented(self):
        """Same user cannot get two slots in the same campaign."""
        result1 = try_grant_free_access(self.user)
        result2 = try_grant_free_access(self.user)

        self.assertTrue(result1)
        self.assertFalse(result2)
        self.assertEqual(FreeAccessSlot.objects.filter(user=self.user).count(), 1)

    def test_campaign_with_duration(self):
        """Campaign with access_duration_days sets correct expiry."""
        self.campaign.access_duration_days = 30
        self.campaign.save()

        try_grant_free_access(self.user)
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertIsNotNone(access.expires_at)

    def test_campaign_without_duration_no_expiry(self):
        """Campaign without access_duration_days sets no expiry."""
        self.campaign.access_duration_days = None
        self.campaign.save()

        try_grant_free_access(self.user)
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertIsNone(access.expires_at)

    def test_manually_grant_free_access(self):
        """manually_grant_free_access works for admin-initiated grants."""
        result = manually_grant_free_access(
            self.user, self.campaign,
            counts_toward_limit=True, note="Test grant"
        )
        self.assertTrue(result)

        slot = FreeAccessSlot.objects.get(user=self.user, campaign=self.campaign)
        self.assertEqual(slot.note, "Test grant")
        self.assertTrue(slot.counts_toward_limit)

    def test_manually_grant_no_count(self):
        """No-count grant doesn't consume a slot from the limit."""
        manually_grant_free_access(
            self.user, self.campaign, counts_toward_limit=False
        )
        self.assertEqual(self.campaign.slots_used, 0)
        self.assertEqual(self.campaign.slots_remaining, 10)


class CampaignDeactivationTest(AccessCalculatorTestBase):
    """Tests for campaign deactivation behavior."""

    def setUp(self):
        super().setUp()
        self.campaign = FreeAccessCampaign.objects.create(
            is_active=True, slot_limit=10
        )
        self.campaign.included_categories.add(self.category)
        # Grant the user a free slot
        try_grant_free_access(self.user)

    def test_deactivation_revokes_access(self):
        """Deactivating campaign revokes access for slot holders."""
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.PURCHASED)

        # Deactivate
        self.campaign.is_active = False
        self.campaign.save()

        access.refresh_from_db()
        self.assertEqual(access.access_level, AccessTier.VISITING)

    def test_deactivation_protects_paid_users(self):
        """Deactivating campaign does NOT revoke access for users with approved purchases."""
        # Give user an approved purchase too
        Purchase.objects.create(
            user=self.user, category=self.category,
            phone_number='0501234567', payer_name='Test',
            status='APPROVED'
        )
        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.PURCHASED)

        # Deactivate campaign
        self.campaign.is_active = False
        self.campaign.save()

        # Access should STILL be PURCHASED because of the approved purchase
        access.refresh_from_db()
        self.assertEqual(access.access_level, AccessTier.PURCHASED)


class CampaignPurchaseOverlapTest(AccessCalculatorTestBase):
    """Tests for the critical scenario: user has BOTH campaign slot AND purchase."""

    def setUp(self):
        super().setUp()
        self.campaign = FreeAccessCampaign.objects.create(
            is_active=True, slot_limit=10
        )
        self.campaign.included_categories.add(self.category)

    def test_campaign_user_submits_pending_purchase_stays_purchased(self):
        """User with campaign access who submits a purchase stays PURCHASED (not downgraded to PENDING)."""
        try_grant_free_access(self.user)

        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.PURCHASED)

        # Submit a PENDING purchase
        Purchase.objects.create(
            user=self.user, category=self.category,
            phone_number='0501234567', payer_name='Test',
            status='PENDING'
        )

        # Access should still be PURCHASED (campaign slot takes priority over pending purchase)
        access.refresh_from_db()
        self.assertEqual(access.access_level, AccessTier.PURCHASED)

    def test_campaign_user_purchase_rejected_stays_purchased(self):
        """User with campaign access whose purchase is rejected stays PURCHASED."""
        try_grant_free_access(self.user)

        purchase = Purchase.objects.create(
            user=self.user, category=self.category,
            phone_number='0501234567', payer_name='Test',
            status='PENDING'
        )

        # Reject the purchase
        purchase.status = 'REJECTED'
        purchase.save()

        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.PURCHASED)

    def test_campaign_deactivated_then_purchase_deleted(self):
        """After campaign deactivation, if user has no purchase, access is VISITING."""
        try_grant_free_access(self.user)

        self.campaign.is_active = False
        self.campaign.save()

        access = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access.access_level, AccessTier.VISITING)


class MultiCampaignTest(AccessCalculatorTestBase):
    """Tests for users participating in multiple campaigns."""

    def test_user_can_join_multiple_campaigns(self):
        """A user can have slots in different campaigns."""
        campaign1 = FreeAccessCampaign.objects.create(
            is_active=True, slot_limit=10
        )
        campaign1.included_categories.add(self.category)

        campaign2 = FreeAccessCampaign.objects.create(
            is_active=True, slot_limit=10
        )
        category2 = Category.objects.create(name='Course 2', price=200)
        campaign2.included_categories.add(category2)

        # Grant slots from different campaigns
        manually_grant_free_access(self.user, campaign1)
        manually_grant_free_access(self.user, campaign2)

        self.assertEqual(
            FreeAccessSlot.objects.filter(user=self.user).count(), 2
        )

    def test_deactivating_one_campaign_doesnt_affect_other(self):
        """Deactivating campaign1 doesn't affect access from campaign2."""
        campaign1 = FreeAccessCampaign.objects.create(
            is_active=True, slot_limit=10
        )
        campaign1.included_categories.add(self.category)

        category2 = Category.objects.create(name='Course 2', price=200)
        campaign2 = FreeAccessCampaign.objects.create(
            is_active=True, slot_limit=10
        )
        campaign2.included_categories.add(category2)

        manually_grant_free_access(self.user, campaign1)
        manually_grant_free_access(self.user, campaign2)

        # Deactivate campaign1
        campaign1.is_active = False
        campaign1.save()

        # Course 1 access revoked
        access1 = CategoryAccess.objects.get(user=self.user, category=self.category)
        self.assertEqual(access1.access_level, AccessTier.VISITING)

        # Course 2 access preserved
        access2 = CategoryAccess.objects.get(user=self.user, category=category2)
        self.assertEqual(access2.access_level, AccessTier.PURCHASED)
