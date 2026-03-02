"""
courses/admin.py
──────────────────────────────────────────────────────────────────────────────
Registers Category and Video in the Django Admin.

Video Admin features:
  • Inline list display with thumbnail / file link.
  • Filters by category and published state.
  • Bulk "Publish / Unpublish" actions.
  • Drag-reorder via the ``order`` field (manual ordering in list view).
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Video


class VideoInline(admin.TabularInline):
    """Shows videos directly inside the Category admin page."""

    model = Video
    extra = 1
    fields = ("title", "file", "order", "is_published")
    ordering = ("order",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "video_count", "created_at")
    search_fields = ("name",)
    inlines = [VideoInline]

    @admin.display(description="# Videos")
    def video_count(self, obj):
        return obj.videos.count()


@admin.action(description="✅ Publish selected videos")
def publish_videos(modeladmin, request, queryset):
    queryset.update(is_published=True)


@admin.action(description="🚫 Unpublish selected videos")
def unpublish_videos(modeladmin, request, queryset):
    queryset.update(is_published=False)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    actions = [publish_videos, unpublish_videos]

    list_display = (
        "title",
        "category",
        "order",
        "is_published",
        "file_link",
        "created_at",
    )
    list_display_links = ("title",)
    list_editable = ("order", "is_published")
    list_filter = ("category", "is_published")
    search_fields = ("title", "description")
    ordering = ("category", "order")

    fieldsets = (
        (None, {
            "fields": ("title", "category", "order", "is_published"),
        }),
        ("Content", {
            "fields": ("file", "cloudinary_url", "public_id", "description"),
        }),
        ("Timestamps", {
            "classes": ("collapse",),
            "fields": ("created_at", "updated_at"),
        }),
    )
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="File")
    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">▶ View</a>', obj.file.url)
        return "—"
