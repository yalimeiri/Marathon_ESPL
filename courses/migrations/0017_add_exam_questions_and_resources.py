from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0016_free_access_campaign"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExamQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question", models.TextField(verbose_name="Question")),
                ("answer", models.TextField(verbose_name="Answer")),
                ("explanation", models.TextField(blank=True, help_text="Optional deeper explanation shown below the answer.", verbose_name="Explanation")),
                ("order", models.PositiveIntegerField(default=0, help_text="Display order (lower = first).", verbose_name="Order")),
                ("is_published", models.BooleanField(default=True, verbose_name="Published")),
                ("minimum_access_level", models.IntegerField(choices=[(0, "Visiting"), (1, "Pending"), (2, "Purchased")], default=2, verbose_name="Minimum Access Level")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="exam_questions",
                        to="courses.category",
                        verbose_name="Category",
                    ),
                ),
            ],
            options={
                "verbose_name": "Exam Question",
                "verbose_name_plural": "Exam Questions",
                "ordering": ["order"],
            },
        ),
        migrations.CreateModel(
            name="ReferenceMaterial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=300, verbose_name="Title")),
                ("description", models.TextField(blank=True, verbose_name="Description")),
                ("material_type", models.CharField(choices=[("link", "External Link"), ("slides", "Google Slides Embed")], default="link", max_length=20, verbose_name="Type")),
                ("url", models.URLField(blank=True, help_text="External link (for links) or 'open in new tab' URL (for slides).", max_length=500, verbose_name="URL")),
                ("embed_url", models.URLField(blank=True, help_text="Google Slides: File → Share → Publish to web → Embed → copy src URL.", max_length=500, verbose_name="Embed URL")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Order")),
                ("is_published", models.BooleanField(default=True, verbose_name="Published")),
                ("minimum_access_level", models.IntegerField(choices=[(0, "Visiting"), (1, "Pending"), (2, "Purchased")], default=2, verbose_name="Minimum Access Level")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resources",
                        to="courses.category",
                        verbose_name="Category",
                    ),
                ),
            ],
            options={
                "verbose_name": "Reference Material",
                "verbose_name_plural": "Reference Materials",
                "ordering": ["order", "title"],
            },
        ),
    ]
