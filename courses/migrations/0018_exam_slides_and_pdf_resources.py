from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0017_add_exam_questions_and_resources"),
    ]

    operations = [
        # ── Exam Q&A is now a single Google Slides presentation per category ──
        migrations.AddField(
            model_name="category",
            name="exam_slides_embed_url",
            field=models.URLField(
                blank=True,
                help_text=(
                    "Google Slides: File → Share → Publish to web → Embed → copy the src URL only "
                    "(not the whole <iframe> tag). Shown on the Exam Q&A page to paying users."
                ),
                max_length=500,
                verbose_name="Exam Q&A — Slides Embed URL",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="exam_slides_url",
            field=models.URLField(
                blank=True,
                help_text="Optional. A normal link to the presentation for the 'open in new tab' button.",
                max_length=500,
                verbose_name="Exam Q&A — Open-in-new-tab URL",
            ),
        ),
        # ── Drop the typed exam-question model (replaced by slides) ──
        migrations.DeleteModel(
            name="ExamQuestion",
        ),
        # ── Reference Materials are now plain file/PDF links ──
        migrations.RemoveField(
            model_name="referencematerial",
            name="material_type",
        ),
        migrations.RemoveField(
            model_name="referencematerial",
            name="embed_url",
        ),
        migrations.AlterField(
            model_name="referencematerial",
            name="url",
            field=models.URLField(
                help_text="Direct link to the PDF (or other file) to print/download.",
                max_length=500,
                verbose_name="File / Link URL",
            ),
        ),
    ]
