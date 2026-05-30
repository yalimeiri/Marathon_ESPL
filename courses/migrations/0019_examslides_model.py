from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0018_exam_slides_and_pdf_resources"),
    ]

    operations = [
        # ── New standalone model for Exam Q&A slides ──
        migrations.CreateModel(
            name="ExamSlides",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=300, verbose_name="Title")),
                ("description", models.TextField(blank=True, verbose_name="Description")),
                (
                    "embed_url",
                    models.URLField(
                        help_text=(
                            "Google Slides → File → Share → Publish to web → Embed → "
                            "copy only the src URL (not the whole <iframe> tag)."
                        ),
                        max_length=500,
                        verbose_name="Slides Embed URL",
                    ),
                ),
                (
                    "url",
                    models.URLField(
                        blank=True,
                        help_text="Optional. Regular link for the 'open in full screen' button.",
                        max_length=500,
                        verbose_name="Open-in-new-tab URL",
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Order")),
                ("is_published", models.BooleanField(default=True, verbose_name="Published")),
                (
                    "minimum_access_level",
                    models.IntegerField(
                        choices=[(0, "Visiting"), (1, "Pending"), (2, "Purchased")],
                        default=2,
                        verbose_name="Minimum Access Level",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_slides",
                        to="courses.category",
                        verbose_name="Category",
                    ),
                ),
            ],
            options={
                "verbose_name": "Exam Q&A Slides",
                "verbose_name_plural": "Exam Q&A Slides",
                "ordering": ["order", "title"],
            },
        ),
        # ── Remove the old single-embed fields from Category ──
        migrations.RemoveField(
            model_name="category",
            name="exam_slides_embed_url",
        ),
        migrations.RemoveField(
            model_name="category",
            name="exam_slides_url",
        ),
    ]
