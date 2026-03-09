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

from .models import Category, Subcategory, Video, Purchase, CategoryAccess, AccessTier, SiteConfiguration


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

    model = Subcategory
    template_name = "courses/video_list.html"
    context_object_name = "subcategories"

    def get_queryset(self):
        from django.db.models import Prefetch
        self.category = get_object_or_404(Category, pk=self.kwargs["pk"])
        
        # Prefetch only published videos to attach to each subcategory
        published_videos = Video.objects.filter(is_published=True).order_by("order", "title")
        
        return (
            Subcategory.objects.filter(category=self.category)
            .prefetch_related(Prefetch("videos", queryset=published_videos))
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
        
        # Attach explicit boolean states to nested videos
        for subcategory in ctx["subcategories"]:
            for video in subcategory.videos.all():
                video.is_free_preview = (user_level >= video.minimum_access_level) and (video.minimum_access_level == AccessTier.VISITING)
                video.is_temp_access = (user_level >= video.minimum_access_level) and (video.minimum_access_level == AccessTier.PENDING)
                video.is_premium_access = (user_level >= video.minimum_access_level) and (video.minimum_access_level == AccessTier.PURCHASED)
                video.is_waiting_admin = (user_level < video.minimum_access_level) and (user_level == AccessTier.PENDING)
                video.is_locked = (user_level < video.minimum_access_level) and (user_level != AccessTier.PENDING)
            
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
                # If they are totally unauthorized (not pending), redirect to payment
                if user_level != AccessTier.PENDING:
                    return redirect('courses:payment', pk=video.category.pk)
                # If they ARE pending, we let dispatch continue so the template can render the modal
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Grab the exact instance Django already prepared for the template
        video = context['video']
        
        # Get all videos in the same category (published only for learners)
        from django.db.models import Prefetch
        if self.request.user.is_staff:
            published_videos = Video.objects.filter(category=video.category).order_by("order", "title")
        else:
            published_videos = Video.objects.filter(category=video.category, is_published=True).order_by("order", "title")
            
        subcategories = Subcategory.objects.filter(category=video.category).prefetch_related(Prefetch("videos", queryset=published_videos)).order_by("order", "title")
            
        user_level = get_effective_access_level(self.request.user, video.category)
        
        # Attach explicit boolean states and build flat list for prev/next calculation
        playlist_list = []
        for subcategory in subcategories:
            for item in subcategory.videos.all():
                item.is_free_preview = (user_level >= item.minimum_access_level) and (item.minimum_access_level == AccessTier.VISITING)
                item.is_temp_access = (user_level >= item.minimum_access_level) and (item.minimum_access_level == AccessTier.PENDING)
                item.is_premium_access = (user_level >= item.minimum_access_level) and (item.minimum_access_level == AccessTier.PURCHASED)
                item.is_waiting_admin = (user_level < item.minimum_access_level) and (user_level == AccessTier.PENDING)
                item.is_locked = (user_level < item.minimum_access_level) and (user_level != AccessTier.PENDING)
                playlist_list.append(item)
            
        video.is_waiting_admin = (user_level < video.minimum_access_level) and (user_level == AccessTier.PENDING)
        video.is_locked = (user_level < video.minimum_access_level) and (user_level != AccessTier.PENDING)
            
        context['subcategories'] = subcategories
        context['user_access_level'] = user_level
        
        # Find the next video in the list
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
        config = SiteConfiguration.get_solo()
        bot_token = config.telegram_bot_token or settings.TELEGRAM_BOT_TOKEN
        chat_id = config.telegram_chat_id or settings.TELEGRAM_CHAT_ID
        text_message = f"New Pending User: {payer_name} ({phone_number}) claims he paid {category.price} NIS.\nCourse: {category.name}"
        
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


from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta

@csrf_exempt
def telegram_webhook(request, bot_token):
    """
    POST /courses/webhook/telegram/<bot_token>/
    Receives callback queries from Telegram inline keyboards (Approve/Reject).
    """
    # Verify the incoming bot token matches our secret to prevent unauthorized requests
    config = SiteConfiguration.get_solo()
    configured_token = config.telegram_bot_token or settings.TELEGRAM_BOT_TOKEN
    if bot_token != configured_token:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            
            # We only care about button clicks: 'callback_query'
            if 'callback_query' in payload:
                callback_query = payload['callback_query']
                callback_id = callback_query.get('id')
                data = callback_query.get('data', '')
                message = callback_query.get('message', {})
                chat_id = message.get('chat', {}).get('id') or config.telegram_chat_id or settings.TELEGRAM_CHAT_ID
                message_id = message.get('message_id')
                
                # Check for our action prefixes
                if data.startswith('approve_') or data.startswith('reject_'):
                    action, purchase_id_str = data.split('_', 1)
                    
                    try:
                        purchase = Purchase.objects.filter(id=int(purchase_id_str)).first()
                        if not purchase:
                            requests.post(f"https://api.telegram.org/bot{configured_token}/sendMessage", json={"chat_id": chat_id, "text": f"Error: Purchase #{purchase_id_str} not found in database!"})
                            requests.post(f"https://api.telegram.org/bot{configured_token}/answerCallbackQuery", json={"callback_query_id": callback_id, "text": "Failed."})
                            return JsonResponse({"status": "ok"})
                            
                        category_access = CategoryAccess.objects.filter(user=purchase.user, category=purchase.category).first()
                        if not category_access:
                            requests.post(f"https://api.telegram.org/bot{configured_token}/sendMessage", json={"chat_id": chat_id, "text": f"Error: No CategoryAccess found for Purchase #{purchase_id_str} (User: {purchase.user})."})
                            requests.post(f"https://api.telegram.org/bot{configured_token}/answerCallbackQuery", json={"callback_query_id": callback_id, "text": "Failed."})
                            return JsonResponse({"status": "ok"})
                        
                        action_text = ""
                        
                        if action == 'approve':
                            purchase.status = 'APPROVED'
                            purchase.save()
                            
                            category_access.access_level = AccessTier.PURCHASED
                            category_access.expires_at = timezone.now() + timedelta(days=120)  # 4 months
                            category_access.save()
                            action_text = "✅ Approved "
                            
                        elif action == 'reject':
                            purchase.status = 'REJECTED'
                            purchase.save()
                            
                            category_access.access_level = AccessTier.VISITING
                            category_access.expires_at = None
                            category_access.save()
                            action_text = "❌ Rejected "
                            
                        # Answer the callback query to stop the loading animation on the Telegram button
                        answer_url = f"https://api.telegram.org/bot{configured_token}/answerCallbackQuery"
                        requests.post(answer_url, json={"callback_query_id": callback_id, "text": f"Status updated to {purchase.status}"})
                        
                        # Edit the original message to reflect the new state and remove buttons
                        if chat_id and message_id:
                            edit_url = f"https://api.telegram.org/bot{configured_token}/editMessageText"
                            new_text = f"{message.get('text', '')}\n\n{action_text}by Admin."
                            requests.post(edit_url, json={
                                "chat_id": chat_id,
                                "message_id": message_id,
                                "text": new_text
                            })
                            
                    except Exception as e:
                        # Send detailed error log to telegram directly
                        err_msg = f"Webhook Error on {action}_{purchase_id_str}: {str(e)}"
                        requests.post(f"https://api.telegram.org/bot{configured_token}/sendMessage", json={"chat_id": chat_id, "text": err_msg})
                        requests.post(f"https://api.telegram.org/bot{configured_token}/answerCallbackQuery", json={"callback_query_id": callback_id, "text": "Internal error occurred."})

        except Exception as e:
            # Broadest exception sent to telegram chat
             requests.post(f"https://api.telegram.org/bot{configured_token}/sendMessage", json={"chat_id": '-5199045814', "text": f"Major Webhook Parsing Error: {str(e)}"})

    return JsonResponse({"status": "ok"})


def debug_purchases(request):
    """Temporary endpoint to check production purchases"""
    if request.GET.get('token') != 'abcd123':
        return JsonResponse({"error": "Unauthorized"}, status=403)
    purchases = Purchase.objects.all().order_by('-created_at')[:5]
    return JsonResponse({
        "purchases": [
            {"id": p.id, "user": p.user.username, "status": p.status, "date": str(p.created_at)} 
            for p in purchases
        ]
    })


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
        "bunny_library_id": getattr(settings, "BUNNY_LIBRARY_ID", ""),
        "bunny_api_key": getattr(settings, "BUNNY_API_KEY", ""),
        "bunny_pull_zone": getattr(settings, "BUNNY_PULL_ZONE", ""),
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
    video_url = request.POST.get("video_url", "").strip()
    bunny_video_id = request.POST.get("bunny_video_id", "").strip()
    category_id = request.POST.get("category_id", "").strip()
    description = request.POST.get("description", "").strip()
    order = request.POST.get("order", "0").strip()
    is_published = request.POST.get("is_published") == "on"

    if not title or not video_url:
        messages.error(request, "Title and Video URL are required.")
        return redirect("courses:upload-video")

    category = None
    if category_id:
        category = get_object_or_404(Category, pk=category_id)

    Video.objects.create(
        title=title,
        video_url=video_url,
        bunny_video_id=bunny_video_id,
        category=category,
        description=description,
        order=int(order) if order.isdigit() else 0,
        is_published=is_published,
    )

    messages.success(request, f'✅ Video "{title}" saved successfully!')
    return redirect("courses:upload-video")
