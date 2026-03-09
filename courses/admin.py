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
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

from .models import Category, Subcategory, Video, Purchase, CategoryAccess

@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "order")
    list_filter = ("category",)
    search_fields = ("title", "description", "category__name")
    ordering = ("category", "order", "title")


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'status', 'phone_number', 'payer_name', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('user__username', 'phone_number', 'payer_name')
    readonly_fields = ('created_at', 'updated_at')


class IsExpiredFilter(admin.SimpleListFilter):
    title = 'Is Expired'
    parameter_name = 'is_expired'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(expires_at__lte=timezone.now())
        if self.value() == 'no':
            return queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))

@admin.action(description="Extend access by 30 days")
def extend_access_30_days(modeladmin, request, queryset):
    for obj in queryset:
        if obj.expires_at:
            obj.expires_at += timedelta(days=30)
        else:
            obj.expires_at = timezone.now() + timedelta(days=30)
        obj.save()

@admin.register(CategoryAccess)
class CategoryAccessAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'access_level', 'expires_at', 'is_expired')
    list_filter = ('access_level', 'category', IsExpiredFilter)
    search_fields = ('user__username', 'category__name')
    actions = [extend_access_30_days]
    
    @admin.display(boolean=True, ordering='expires_at', description='Expired')
    def is_expired(self, obj):
        if obj.expires_at:
            return obj.expires_at <= timezone.now()
        return False


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
    change_form_template = "admin/courses/video/change_form.html"
    actions = [publish_videos, unpublish_videos]

    list_display = (
        "title",
        "category",
        "order",
        "minimum_access_level",
        "is_published",
        "file_link",
        "created_at",
    )
    list_display_links = ("title",)
    list_editable = ("order", "minimum_access_level", "is_published")
    list_filter = ("category", "minimum_access_level", "is_published")
    search_fields = ("title", "description")
    ordering = ("category", "order")

    fieldsets = (
        (None, {
            "fields": ("title", "category", "subcategory", "order", "minimum_access_level", "is_published"),
        }),
        ("Content", {
            "fields": ("file", "video_url", "bunny_video_id", "description"),
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

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        """
        Inject the Cloudinary cloud name into the admin form context 
        so the custom JS upload widget can initialize properly.
        """
        from django.conf import settings
        context.update({
            'bunny_library_id': getattr(settings, 'BUNNY_LIBRARY_ID', ''),
            'bunny_api_key': getattr(settings, 'BUNNY_API_KEY', ''),
            'bunny_pull_zone': getattr(settings, 'BUNNY_PULL_ZONE', ''),
        })
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)
