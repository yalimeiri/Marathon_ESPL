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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

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
    order = models.IntegerField(default=0, verbose_name="Order")

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
        ordering = ["category", "order", "title"]

    def __str__(self):
        return f"{self.title} [{self.category}]"

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
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
