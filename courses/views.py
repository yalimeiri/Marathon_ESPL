"""
courses/views.py
──────────────────────────────────────────────────────────────────────────────
Views for the learner-facing side of MarathonLMS.

All views require the user to be logged in (enforced via LoginRequiredMixin).
The device-lock middleware adds an additional layer: if the user's cookie does
not match the DB UUID, they are already logged out before reaching these views.

Views
─────
  CategoryListView  — landing page; shows all categories.
  VideoListView     — shows all published videos in a category.
  VideoDetailView   — shows a single video player page.
  upload_video_page — superuser-only page with Cloudinary Upload Widget.
  save_video        — POST endpoint that saves Cloudinary result to DB.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_POST
from django.contrib import messages
import requests
import json
from django.utils import timezone

from .models import Category, Video, Purchase, CategoryAccess, AccessTier


def get_effective_access_level(user, category):
    if not user.is_authenticated:
        return AccessTier.VISITING
    
    access = CategoryAccess.objects.filter(user=user, category=category).first()
    if access:
        if access.expires_at and access.expires_at <= timezone.now():
            return AccessTier.VISITING
        return access.access_level
    return AccessTier.VISITING


class CategoryListView(LoginRequiredMixin, ListView):
    """
    GET /courses/
    Lists all categories for the logged-in learner.
    """

    model = Category
    template_name = "courses/category_list.html"
    context_object_name = "categories"
    ordering = ["name"]


class VideoListView(LoginRequiredMixin, ListView):
    """
    GET /courses/<category_id>/
    Lists published videos in ascending order for a single category.
    """

    model = Video
    template_name = "courses/video_list.html"
    context_object_name = "videos"

    def get_queryset(self):
        self.category = get_object_or_404(Category, pk=self.kwargs["pk"])
        return (
            Video.objects.filter(category=self.category, is_published=True)
            .order_by("order", "title")
        )

    def dispatch(self, request, *args, **kwargs):
        self.category = get_object_or_404(Category, pk=self.kwargs["pk"])
        # Anyone authenticated can view the video list curriculum
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category"] = self.category
        
        user_level = get_effective_access_level(self.request.user, self.category)
        ctx["user_access_level"] = user_level
        
        # Attach boolean flags to avoid `==` in templates (due to aggressive auto-formatter breaking tags)
        for video in ctx["videos"]:
            video.is_pending = (user_level < video.minimum_access_level) and (user_level == AccessTier.PENDING) and (video.minimum_access_level == AccessTier.PURCHASED)
            video.is_premium = (user_level < video.minimum_access_level) and not video.is_pending
            video.is_free_preview = (user_level >= video.minimum_access_level) and (video.minimum_access_level == AccessTier.VISITING)
            
        return ctx


class VideoDetailView(LoginRequiredMixin, DetailView):
    """
    GET /courses/video/<video_id>/
    Renders a single video player page.
    Only published videos are accessible to learners.
    """

    model = Video
    template_name = "courses/video_detail.html"
    context_object_name = "video"

    def get_queryset(self):
        # Staff can preview unpublished videos; regular users cannot.
        if self.request.user.is_staff:
            return Video.objects.all()
        return Video.objects.filter(is_published=True)

    def dispatch(self, request, *args, **kwargs):
        # We need the video to find the category
        video = self.get_object()
        if not request.user.is_staff:
            user_level = get_effective_access_level(request.user, video.category)
            if user_level < video.minimum_access_level:
                if user_level == AccessTier.PENDING:
                    messages.info(request, "Your Bit payment is currently being reviewed. Please wait for approval to unlock this chapter.")
                    return redirect('courses:video-list', pk=video.category.pk)
                else:
                    return redirect('courses:payment', pk=video.category.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        video = self.get_object()
        
        # Get all videos in the same category (published only for learners)
        if self.request.user.is_staff:
            playlist = Video.objects.filter(category=video.category).order_by("order", "title")
        else:
            playlist = Video.objects.filter(category=video.category, is_published=True).order_by("order", "title")
            
        user_level = get_effective_access_level(self.request.user, video.category)
        
        # Attach boolean flags to avoid `==` in templates (due to aggressive auto-formatter breaking tags)
        for item in playlist:
            item.is_pending = (user_level < item.minimum_access_level) and (user_level == AccessTier.PENDING) and (item.minimum_access_level == AccessTier.PURCHASED)
            item.is_premium = (user_level < item.minimum_access_level) and not item.is_pending
            item.is_free_preview = (user_level >= item.minimum_access_level) and (item.minimum_access_level == AccessTier.VISITING)
            
        context['playlist'] = playlist
        context['user_access_level'] = user_level
        
        # Find the next video in the list
        playlist_list = list(playlist)
        try:
            current_idx = playlist_list.index(video)
            if current_idx + 1 < len(playlist_list):
                context['next_video'] = playlist_list[current_idx + 1]
                from django.urls import reverse
                context['next_video_url'] = reverse('courses:video-detail', args=[context['next_video'].pk])
        except ValueError:
            pass
            
        return context


class PaymentView(LoginRequiredMixin, DetailView):
    """
    GET /courses/category/<pk>/payment/
    POST /courses/category/<pk>/payment/
    """
    model = Category
    template_name = "courses/payment.html"
    context_object_name = "category"

    def post(self, request, *args, **kwargs):
        category = self.get_object()
        phone_number = request.POST.get('phone_number', '').strip()
        payer_name = request.POST.get('payer_name', '').strip()

        if not phone_number or not payer_name:
            messages.error(request, "Please provide your name and phone number.")
            return redirect('courses:payment', pk=category.pk)

        # Create or update Purchase
        purchase, created = Purchase.objects.get_or_create(
            user=request.user,
            category=category,
            defaults={'phone_number': phone_number, 'payer_name': payer_name, 'status': 'PENDING'}
        )
        
        # Sync to CategoryAccess
        access, access_created = CategoryAccess.objects.get_or_create(
            user=request.user,
            category=category,
            defaults={'access_level': AccessTier.PENDING}
        )
        
        if not created:
            if purchase.status == 'PENDING':
                purchase.phone_number = phone_number
                purchase.payer_name = payer_name
                purchase.save()
            elif purchase.status == 'APPROVED':
                # Check actual effective access
                eff_level = get_effective_access_level(request.user, category)
                if eff_level >= AccessTier.PURCHASED:
                    messages.info(request, "You already have access to this course.")
                    return redirect('courses:video-list', pk=category.pk)
                else:
                    # Access expired or was revoked. Re-submit!
                    purchase.status = 'PENDING'
                    purchase.save()
                    access.access_level = AccessTier.PENDING
                    access.save()

        # Send Telegram Message
        bot_token = '8227368106:AAEbSmIdTFRwy1QUoiuGMJGo8SM_Nfh5-BA'
        chat_id = '-5199045814'
        text_message = f"New Pending User: {payer_name} ({phone_number}) claims he paid 100 NIS.\nCourse: {category.name}"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text_message,
            "reply_markup": json.dumps({
                "inline_keyboard": [[
                    {"text": "✅ APPROVE", "callback_data": f"approve_{purchase.id}"},
                    {"text": "❌ REJECT", "callback_data": f"reject_{purchase.id}"}
                ]]
            })
        }
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Telegram Error:", e)

        messages.success(request, "Thank you! We received your payment request. You will be granted access shortly.")
        return redirect('courses:category-list')


# ── Upload Manager (superuser only) ─────────────────────────────────────────

_superuser_only = user_passes_test(lambda u: u.is_active and u.is_superuser)


@login_required
@_superuser_only
def upload_video_page(request):
    """
    GET /courses/manager/upload/
    Renders the Cloudinary Upload Widget page for the admin.
    """
    categories = Category.objects.order_by("name")
    context = {
        "categories": categories,
        "cloudinary_cloud_name": settings.CLOUDINARY_CLOUD_NAME,
    }
    return render(request, "courses/upload_video.html", context)


@login_required
@_superuser_only
@require_POST
def save_video(request):
    """
    POST /courses/manager/save-video/
    Receives the Cloudinary upload result (JSON fields) and saves a Video record.
    """
    title = request.POST.get("title", "").strip()
    cloudinary_url = request.POST.get("cloudinary_url", "").strip()
    public_id = request.POST.get("public_id", "").strip()
    category_id = request.POST.get("category_id", "").strip()
    description = request.POST.get("description", "").strip()
    order = request.POST.get("order", "0").strip()
    is_published = request.POST.get("is_published") == "on"

    if not title or not cloudinary_url:
        messages.error(request, "Title and Cloudinary URL are required.")
        return redirect("courses:upload-video")

    category = None
    if category_id:
        category = get_object_or_404(Category, pk=category_id)

    Video.objects.create(
        title=title,
        cloudinary_url=cloudinary_url,
        public_id=public_id,
        category=category,
        description=description,
        order=int(order) if order.isdigit() else 0,
        is_published=is_published,
    )

    messages.success(request, f'✅ Video "{title}" saved successfully!')
    return redirect("courses:upload-video")
