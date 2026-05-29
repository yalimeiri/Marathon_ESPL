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

from .models import (
    Category, Subcategory, Video, Purchase, CategoryAccess,
    SiteConfiguration, FAQ, VideoQuestion, VideoAnswer,
    FreeAccessCampaign, FreeAccessSlot,
    ReferenceMaterial,
)

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
    fieldsets = (
        (None, {
            "fields": ("name", "description", "price"),
        }),
        ("Exam Q&A — Google Slides", {
            "fields": ("exam_slides_embed_url", "exam_slides_url"),
            "description": (
                "Paste only the src URL from Google Slides → File → Share → Publish to web → Embed. "
                "Do NOT paste the whole iframe tag. Shown on the Exam Q&A tab to paying users."
            ),
        }),
    )

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


@admin.register(FAQ)
class FAQAdmin(ModelAdmin):
    list_display = ("question", "is_published", "order", "created_at")
    list_editable = ("is_published", "order")
    list_filter = ("is_published",)
    search_fields = ("question", "answer")
    ordering_field = "order"


class VideoAnswerInline(StackedInline):
    model = VideoAnswer
    extra = 0


@admin.register(VideoQuestion)
class VideoQuestionAdmin(ModelAdmin):
    list_display = ("author", "video", "body", "created_at")
    list_filter = ("video",)
    search_fields = ("body", "author__username")
    inlines = [VideoAnswerInline]


@admin.register(VideoAnswer)
class VideoAnswerAdmin(ModelAdmin):
    list_display = ("author", "question", "body", "created_at")
    search_fields = ("body", "author__username")


# ── Free Access Campaign ────────────────────────────────────────────────

class FreeAccessSlotInline(StackedInline):
    """
    Shows all slot holders directly inside the Campaign detail page.
    """
    model = FreeAccessSlot
    extra = 0
    readonly_fields = ('user', 'granted_at')
    fields = ('user', 'granted_at', 'counts_toward_limit', 'note')
    can_delete = False
    verbose_name = "Slot Holder"
    verbose_name_plural = "Slot Holders"


@admin.register(FreeAccessCampaign)
class FreeAccessCampaignAdmin(ModelAdmin):
    """
    Admin for the Free Access Campaign.

    Key features:
      - filter_horizontal for included_categories (easy checkbox picker)
      - Computed slot progress shown in list_display
      - Inline list of all slot holders
    """
    list_display = (
        '__str__',
        'is_active',
        'slot_limit',
        'slots_used_display',
        'slots_remaining_display',
        'access_duration_days',
        'created_at',
    )
    list_filter = ('is_active',)
    filter_horizontal = ('included_categories',)
    inlines = [FreeAccessSlotInline]
    readonly_fields = ('created_at', 'slots_used_display', 'slots_remaining_display')
    save_on_top = True

    fieldsets = (
        ("Campaign Status", {
            "fields": ('is_active', 'slot_limit', 'slots_used_display', 'slots_remaining_display'),
            "description": "Enable the campaign to start granting free slots. "
                           "Disable to immediately revoke all free access granted by this campaign.",
        }),
        ("Access Settings", {
            "fields": ('included_categories', 'access_duration_days'),
            "description": "Select which categories are included. "
                           "Set duration in days (blank = never expires).",
        }),
        ("Meta", {
            "fields": ('created_at',),
            "classes": ('collapse',),
        }),
    )

    @admin.display(description="Slots Used")
    def slots_used_display(self, obj):
        used = obj.slots_used
        limit = obj.slot_limit
        pct = int((used / limit) * 100) if limit > 0 else 0
        color = "text-emerald-600" if pct < 80 else ("text-amber-500" if pct < 100 else "text-red-500")
        return format_html(
            '<span class="font-semibold {}">{}  /  {}</span> <span class="text-gray-400 text-xs">({}%)</span>',
            color, used, limit, pct
        )

    @admin.display(description="Slots Remaining")
    def slots_remaining_display(self, obj):
        remaining = obj.slots_remaining
        color = "text-emerald-600" if remaining > 0 else "text-red-500"
        label = str(remaining) if remaining > 0 else "FULL"
        return format_html('<span class="font-bold {}">{}</span>', color, label)


@admin.action(description="🔓 Grant free access (counts toward limit)")
def grant_free_access_action(modeladmin, request, queryset):
    """
    Admin action on the FreeAccessSlot list.
    Manually grants free access to selected users via the active campaign,
    consuming a slot from the limit.
    """
    from .models import FreeAccessCampaign
    from .free_access import manually_grant_free_access

    campaign = FreeAccessCampaign.objects.filter(is_active=True).first()
    if not campaign:
        modeladmin.message_user(request, "⚠️ No active campaign found. Please activate a campaign first.", level='warning')
        return

    granted, skipped = 0, 0
    for slot in queryset:
        success = manually_grant_free_access(
            slot.user, campaign, counts_toward_limit=True,
            note="Manually granted via Admin action"
        )
        if success:
            granted += 1
        else:
            skipped += 1

    if granted:
        modeladmin.message_user(request, f"✅ Granted free access to {granted} user(s).")
    if skipped:
        modeladmin.message_user(request, f"⚠️ Skipped {skipped} user(s) (already have a slot or campaign is full).", level='warning')


@admin.action(description="🎁 Grant free access (does NOT count toward limit)")
def grant_free_access_no_count_action(modeladmin, request, queryset):
    """
    Same as above but grants without consuming a slot — useful for admins,
    testers, or VIP users.
    """
    from .models import FreeAccessCampaign
    from .free_access import manually_grant_free_access

    campaign = FreeAccessCampaign.objects.filter(is_active=True).first()
    if not campaign:
        modeladmin.message_user(request, "⚠️ No active campaign found.", level='warning')
        return

    granted, skipped = 0, 0
    for slot in queryset:
        success = manually_grant_free_access(
            slot.user, campaign, counts_toward_limit=False,
            note="Manually granted (no-count) via Admin action"
        )
        if success:
            granted += 1
        else:
            skipped += 1

    if granted:
        modeladmin.message_user(request, f"✅ Granted free access (no-count) to {granted} user(s).")
    if skipped:
        modeladmin.message_user(request, f"⚠️ Skipped {skipped} user(s).", level='warning')


@admin.register(FreeAccessSlot)
class FreeAccessSlotAdmin(ModelAdmin):
    """
    Admin for individual free access slot records.

    Key features:
      - Toggle 'counts_toward_limit' directly in the list view.
      - Search by username.
      - Filter by campaign and counting status.
      - Manual-grant actions.
    """
    list_display = (
        'user',
        'campaign',
        'granted_at',
        'counts_toward_limit',
        'note',
    )
    list_filter = ('campaign', 'counts_toward_limit')
    search_fields = ('user__username', 'user__email')
    list_editable = ('counts_toward_limit',)
    readonly_fields = ('granted_at',)
    raw_id_fields = ('user',)
    actions = [grant_free_access_action, grant_free_access_no_count_action]


# ── Reference Materials (PDF / file links) ───────────────────────────────────

@admin.register(ReferenceMaterial)
class ReferenceMaterialAdmin(ModelAdmin):
    list_display = ("title", "category", "order", "is_published", "minimum_access_level")
    list_editable = ("order", "is_published")
    list_filter = ("category", "is_published", "minimum_access_level")
    search_fields = ("title", "description")
    ordering_field = "order"
    save_on_top = True
    fieldsets = (
        ("Basic Info", {
            "fields": ("category", "title", "description", "order", "is_published", "minimum_access_level"),
        }),
        ("File Link", {
            "fields": ("url",),
            "description": "Direct link to the PDF (or other file) to print/download.",
        }),
    )
