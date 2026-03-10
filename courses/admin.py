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
from unfold.admin import ModelAdmin, StackedInline
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q

from .models import Category, Subcategory, Video, Purchase, CategoryAccess, SiteConfiguration

@admin.register(Subcategory)
class SubcategoryAdmin(ModelAdmin):
    list_display = ("title", "category", "videos_link")
    list_filter = ("category",)
    search_fields = ("title", "description", "category__name")
    ordering_field = "order"
    save_on_top = True

    @admin.display(description="Videos")
    def videos_link(self, obj):
        count = obj.videos.count()
        url = reverse("admin:courses_video_changelist") + f"?subcategory__id__exact={obj.id}"
        return format_html('<a href="{}" class="font-semibold text-primary-600">{} Videos &rarr;</a>', url, count)

@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(ModelAdmin):
    list_display = ('__str__', 'telegram_bot_token', 'telegram_chat_id')
    
    def has_add_permission(self, request):
        if self.model.objects.count() > 0:
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False



@admin.register(Purchase)
class PurchaseAdmin(ModelAdmin):
    list_display = ('user', 'category', 'price_paid', 'status', 'phone_number', 'payer_name', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('user__username', 'phone_number', 'payer_name')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description="Price Paid")
    def price_paid(self, obj):
        return format_html('₪{}', obj.category.price)

    def changelist_view(self, request, extra_context=None):
        # Calculate the total for the currently visible queryset
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            qs = response.context_data['cl'].queryset
            total = sum(p.category.price for p in qs.select_related('category'))
            response.context_data['purchases_total'] = total
        except (AttributeError, KeyError):
            pass
        return response


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
class CategoryAccessAdmin(ModelAdmin):
    list_display = ('user', 'category', 'access_level', 'expires_at', 'is_expired')
    list_filter = ('access_level', 'category', IsExpiredFilter)
    search_fields = ('user__username', 'category__name')
    actions = [extend_access_30_days]
    
    @admin.display(boolean=True, ordering='expires_at', description='Expired')
    def is_expired(self, obj):
        if obj.expires_at:
            return obj.expires_at <= timezone.now()
        return False


class VideoInline(StackedInline):
    """Shows videos directly inside the Subcategory admin page."""

    model = Video
    extra = 0
    ordering_field = "order"

class SubcategoryInline(StackedInline):
    """Shows subcategories directly inside the Category admin page."""

    model = Subcategory
    extra = 0
    ordering_field = "order"


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "price", "subcategories_link", "video_count", "created_at")
    search_fields = ("name",)
    inlines = [SubcategoryInline]
    ordering_field = "order"
    save_on_top = True

    @admin.display(description="Subcategories")
    def subcategories_link(self, obj):
        count = obj.subcategories.count()
        url = reverse("admin:courses_subcategory_changelist") + f"?category__id__exact={obj.id}"
        return format_html('<a href="{}" class="font-semibold text-primary-600">{} Subcats &rarr;</a>', url, count)

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
class VideoAdmin(ModelAdmin):
    # Unfold automatically handles styling, but we might keep our custom template or adapt it.
    # For now, let's keep it to see if it still injects what we need without breaking Unfold.
    # Actually, Unfold uses its own change_form template. Better to do it Unfold way if needed later, but let's try.
    change_form_template = "admin/courses/video/change_form.html"
    actions = [publish_videos, unpublish_videos]
    ordering_field = "order"

    list_display = (
        "title",
        "category",
        "subcategory",
        "minimum_access_level",
        "is_published",
        "file_link",
        "created_at",
    )
    list_display_links = ("title",)
    list_editable = ("minimum_access_level", "is_published")
    list_filter = ("category", "subcategory", "minimum_access_level", "is_published")
    search_fields = ("title", "description")

    fieldsets = (
        (None, {
            "fields": ("title", "category", "subcategory", "minimum_access_level", "is_published"),
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
