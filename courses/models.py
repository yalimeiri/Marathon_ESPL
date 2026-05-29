"""
courses/models.py
──────────────────────────────────────────────────────────────────────────────
Defines the core content structure of MarathonLMS:

  Category  — A top-level grouping for courses / topics.
  Video     — A single uploadable video file linked to a Category.

Video files are stored under MEDIA_ROOT/videos/ (local dev) or in the
configured cloud bucket (S3 / Cloudinary) when storage backends are
activated in settings.py.
"""

from django.db import models
from django.conf import settings

class SiteConfiguration(models.Model):
    """
    Singleton model to hold global site settings.
    Access via SiteConfiguration.get_solo()
    """
    telegram_bot_token = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="Telegram Bot Token",
        help_text="The token from BotFather (e.g. 12345:ABCDEF)"
    )
    telegram_chat_id = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="Telegram Chat ID",
        help_text="The Chat ID to send payment notifications to."
    )

    class Meta:
        verbose_name = "Site Configuration"
        verbose_name_plural = "Site Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SiteConfiguration, self).save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class FreeAccessCampaign(models.Model):
    """
    Defines a free-access campaign that grants PURCHASED-level access to a
    configurable set of categories for the first N registered users.

    Only one campaign should be active at a time.
    Deactivating a campaign (is_active=False) immediately revokes all
    CategoryAccess records that were granted by this campaign.
    """

    is_active = models.BooleanField(
        default=False,
        verbose_name="Active",
        help_text="Enable to start granting free slots. Disable to immediately revoke all free access granted by this campaign."
    )
    slot_limit = models.PositiveIntegerField(
        default=100,
        verbose_name="Slot Limit",
        help_text="Maximum number of users who can claim a free slot (e.g. 50, 100)."
    )
    included_categories = models.ManyToManyField(
        'Category',
        blank=True,
        verbose_name="Included Categories",
        help_text="Users will get free PURCHASED access ONLY to the categories selected here."
    )
    access_duration_days = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Access Duration (days)",
        help_text="How many days the free access lasts. Leave blank for access that never expires."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Free Access Campaign"
        verbose_name_plural = "Free Access Campaigns"

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"Campaign #{self.pk} — {status} (limit={self.slot_limit})"

    @property
    def slots_used(self):
        """Number of slots consumed (only counting those marked as counting)."""
        return self.slots.filter(counts_toward_limit=True).count()

    @property
    def slots_remaining(self):
        """Slots still available for new registrations."""
        return max(0, self.slot_limit - self.slots_used)

    @property
    def is_full(self):
        """True when no more slots are available."""
        return self.slots_remaining == 0


class FreeAccessSlot(models.Model):
    """
    Records that a specific user received a free slot from a campaign.
    Admins can:
      - View all slot holders.
      - Toggle counts_toward_limit to free up a slot without revoking access.
      - Add notes (e.g. "manually added", "test user").
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='free_access_slot',
        verbose_name="User"
    )
    campaign = models.ForeignKey(
        FreeAccessCampaign,
        on_delete=models.CASCADE,
        related_name='slots',
        verbose_name="Campaign"
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    counts_toward_limit = models.BooleanField(
        default=True,
        verbose_name="Counts Toward Limit",
        help_text="Uncheck to exclude this user from the slot counter, freeing up a slot for someone else."
    )
    note = models.TextField(
        blank=True,
        verbose_name="Admin Note",
        help_text="Optional note (e.g. 'manually granted', 'test account')."
    )

    class Meta:
        verbose_name = "Free Access Slot"
        verbose_name_plural = "Free Access Slots"
        ordering = ['-granted_at']

    def __str__(self):
        return f"{self.user.username} → {self.campaign}"


class AccessTier(models.IntegerChoices):

    VISITING = 0, 'Visiting'
    PENDING = 1, 'Pending'
    PURCHASED = 2, 'Purchased'

class Purchase(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='purchases',
        verbose_name="User"
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
        related_name='purchases',
        verbose_name="Category"
    )
    phone_number = models.CharField(max_length=20, verbose_name="Bit Phone Number")
    payer_name = models.CharField(max_length=150, verbose_name="Payer Name")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Purchase"
        verbose_name_plural = "Purchases"
        unique_together = ('user', 'category')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} -> {self.category} ({self.status})"


class CategoryAccess(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='category_accesses',
        verbose_name="User"
    )
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
        related_name='accesses',
        verbose_name="Category"
    )
    access_level = models.IntegerField(
        choices=AccessTier.choices,
        default=AccessTier.VISITING,
        verbose_name="Access Level"
    )
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Expires At")

    class Meta:
        verbose_name = "Category Access"
        verbose_name_plural = "Category Accesses"
        unique_together = ('user', 'category')

    def __str__(self):
        return f"{self.user} -> {self.category} ({self.get_access_level_display()})"


class Category(models.Model):
    """
    Top-level grouping.  Examples: "Python Basics", "Advanced Django", etc.
    """

    name = models.CharField(max_length=200, unique=True, verbose_name="Category Name")
    description = models.TextField(blank=True, verbose_name="Description")
    price = models.IntegerField(default=100, verbose_name="Price (NIS)", help_text="Set the price in NIS for this course.")
    order = models.PositiveIntegerField(default=0, blank=False, null=False, verbose_name="Order", help_text="Display order (drag-and-drop in Admin).")
    exam_slides_embed_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Exam Q&A — Slides Embed URL",
        help_text="Google Slides: File → Share → Publish to web → Embed → copy the src URL only "
                  "(not the whole <iframe> tag). Shown on the Exam Q&A page to paying users.",
    )
    exam_slides_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Exam Q&A — Open-in-new-tab URL",
        help_text="Optional. A normal link to the presentation for the 'open in new tab' button.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Subcategory(models.Model):
    """
    A sub-grouping under a Category (e.g., "Chapter 1").
    Videos belong to a Subcategory.
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="subcategories",
        verbose_name="Course"
    )
    title = models.CharField(max_length=200, verbose_name="Subcategory Title")
    description = models.TextField(blank=True, verbose_name="Description")
    order = models.PositiveIntegerField(default=0, blank=False, null=False, verbose_name="Order")

    class Meta:
        verbose_name = "Subcategory"
        verbose_name_plural = "Subcategories"
        ordering = ["order", "title"]

    def __str__(self):
        return f"{self.category.name} - {self.title}"


def video_upload_path(instance, filename):
    """
    Store videos in: media/videos/<category_id>/<filename>
    This keeps uploads organized by category.
    """
    category_id = instance.category_id or "uncategorized"
    return f"videos/{category_id}/{filename}"


class Video(models.Model):
    """
    A single video lesson.

    ``file`` uses Django's FileField so that:
      • In dev:  files land in MEDIA_ROOT/videos/
      • In prod: the storage backend takes over transparently
                 when you switch STORAGES in settings.py.

    ``order`` controls the display sequence within a category (0 = first).
    """

    title = models.CharField(max_length=300, verbose_name="Title")
    minimum_access_level = models.IntegerField(
        choices=AccessTier.choices,
        default=AccessTier.VISITING,
        verbose_name="Minimum Access Level",
        help_text="Required access level to watch this video."
    )
    file = models.FileField(
        upload_to=video_upload_path,
        verbose_name="Video File",
        help_text="Upload a small MP4 file (under 10MB), OR use the Cloudinary URL field.",
        blank=True,
        null=True,
    )
    video_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Video URL",
        help_text="Populated automatically by the Upload Manager, or paste external URL manually.",
    )
    bunny_video_id = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Bunny Video ID",
        help_text="Set automatically by the Upload Manager to track API status.",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="videos",
        verbose_name="Category",
    )
    subcategory = models.ForeignKey(
        Subcategory,
        on_delete=models.CASCADE,
        related_name="videos",
        verbose_name="Subcategory",
        blank=True,
        null=True
    )
    description = models.TextField(blank=True, verbose_name="Description")
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Order / Index",
        help_text="Display order within the category (0 = first).",
    )
    is_published = models.BooleanField(
        default=False,
        verbose_name="Published",
        help_text="Only published videos are visible to learners.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Video"
        verbose_name_plural = "Videos"
        ordering = ["order", "title"]

    def __str__(self):
        return f"{self.title} [{self.category}]"

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone


@receiver(post_save, sender=FreeAccessCampaign)
def on_campaign_save(sender, instance, **kwargs):
    """
    When a campaign is deactivated (is_active flips to False), immediately
    revoke PURCHASED-level CategoryAccess for every user who received a free
    slot through this campaign, resetting them to VISITING.

    If the campaign is activated again, existing slot holders are NOT
    automatically re-granted (admin must re-enable manually or the user
    must register a new slot).
    """
    if not instance.is_active:
        slot_user_ids = instance.slots.values_list('user_id', flat=True)
        included_category_ids = instance.included_categories.values_list('id', flat=True)
        # Only revoke accesses that are still at PURCHASED level
        CategoryAccess.objects.filter(
            user_id__in=slot_user_ids,
            category_id__in=included_category_ids,
            access_level=AccessTier.PURCHASED,
        ).update(access_level=AccessTier.VISITING, expires_at=None)
from datetime import timedelta

@receiver(post_save, sender=Purchase)
def sync_purchase_to_access(sender, instance, created, **kwargs):
    """
    Ensure CategoryAccess stays mirrored to the Purchase status.
    This handles changes made manually via Django Admin.
    """
    access, _ = CategoryAccess.objects.get_or_create(
        user=instance.user,
        category=instance.category
    )
    
    # Check highest ranking purchase status for this course
    purchases = Purchase.objects.filter(user=instance.user, category=instance.category)
    
    if purchases.filter(status='APPROVED').exists():
        access.access_level = AccessTier.PURCHASED
        if not access.expires_at:
            access.expires_at = timezone.now() + timedelta(days=120)
    elif purchases.filter(status='PENDING').exists():
        access.access_level = AccessTier.PENDING
        access.expires_at = None
    else:
        access.access_level = AccessTier.VISITING
        access.expires_at = None
        
    access.save()


@receiver(post_delete, sender=Purchase)
def cleanup_access_on_purchase_delete(sender, instance, **kwargs):
    """
    If a purchase is deleted (e.g. via Admin), recalculate their access.
    """
    purchases = Purchase.objects.filter(user=instance.user, category=instance.category)
    
    access = CategoryAccess.objects.filter(user=instance.user, category=instance.category).first()
    if access:
        if purchases.filter(status='APPROVED').exists():
            access.access_level = AccessTier.PURCHASED
        elif purchases.filter(status='PENDING').exists():
            access.access_level = AccessTier.PENDING
            access.expires_at = None
        else:
            access.access_level = AccessTier.VISITING
            access.expires_at = None
        access.save()


class FAQ(models.Model):
    """
    Frequently Asked Questions for the platform.
    """
    question = models.CharField(max_length=500, verbose_name="Question")
    answer = models.TextField(verbose_name="Answer")
    order = models.PositiveIntegerField(
        default=0, 
        verbose_name="Order", 
        help_text="Display order (drag-and-drop in Admin)."
    )
    is_published = models.BooleanField(
        default=True, 
        verbose_name="Published",
        help_text="Uncheck to hide this question from the site."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        ordering = ["order", "-created_at"]

    def __str__(self):
        return self.question


class VideoQuestion(models.Model):
    """
    A question posted by a user under a specific video.
    """
    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name="Video"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_questions',
        verbose_name="Author"
    )
    body = models.TextField(verbose_name="Question")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Video Question"
        verbose_name_plural = "Video Questions"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author.username}: {self.body[:60]}"


class VideoAnswer(models.Model):
    """
    An answer to a VideoQuestion, posted by any logged-in user.
    """
    question = models.ForeignKey(
        VideoQuestion,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name="Question"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_answers',
        verbose_name="Author"
    )
    body = models.TextField(verbose_name="Answer")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Video Answer"
        verbose_name_plural = "Video Answers"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username} → {self.question.body[:40]}"


class ReferenceMaterial(models.Model):
    """
    A reference item for exam prep — a link to a downloadable/printable file
    (PDF, doc, etc.) shown on the Reference Materials page.
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="resources",
        verbose_name="Category",
    )
    title = models.CharField(max_length=300, verbose_name="Title")
    description = models.TextField(blank=True, verbose_name="Description")
    url = models.URLField(
        max_length=500,
        verbose_name="File / Link URL",
        help_text="Direct link to the PDF (or other file) to print/download.",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Order")
    is_published = models.BooleanField(default=True, verbose_name="Published")
    minimum_access_level = models.IntegerField(
        choices=AccessTier.choices,
        default=AccessTier.PURCHASED,
        verbose_name="Minimum Access Level",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reference Material"
        verbose_name_plural = "Reference Materials"
        ordering = ["order", "title"]

    def __str__(self):
        return self.title

