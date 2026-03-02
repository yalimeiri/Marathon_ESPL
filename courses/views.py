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

from .models import Category, Video


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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category"] = self.category
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
