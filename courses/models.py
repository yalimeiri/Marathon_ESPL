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



class Category(models.Model):
    """
    Top-level grouping.  Examples: "Python Basics", "Advanced Django", etc.
    """

    name = models.CharField(max_length=200, unique=True, verbose_name="Category Name")
    description = models.TextField(blank=True, verbose_name="Description")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


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
      • In prod: the storage backend (S3 / Cloudinary) takes over transparently
                 when you switch STORAGES in settings.py.

    ``order`` controls the display sequence within a category (0 = first).
    """

    title = models.CharField(max_length=300, verbose_name="Title")
    file = models.FileField(
        upload_to=video_upload_path,
        verbose_name="Video File",
        help_text="Upload a small MP4 file (under 10MB), OR use the Cloudinary URL field.",
        blank=True,
        null=True,
    )
    cloudinary_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Cloudinary URL",
        help_text="Populated automatically by the Upload Manager, or paste manually.",
    )
    public_id = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Cloudinary Public ID",
        help_text="Set automatically by the Upload Manager.",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="videos",
        verbose_name="Category",
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
