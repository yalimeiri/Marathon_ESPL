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
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView
from django.shortcuts import get_object_or_404

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
