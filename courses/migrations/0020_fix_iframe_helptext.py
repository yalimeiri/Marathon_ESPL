from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0019_examslides_model"),
    ]

    operations = [
        migrations.AlterField(
            model_name="examslides",
            name="embed_url",
            field=models.URLField(
                help_text=(
                    "Google Slides → File → Share → Publish to web → Embed → "
                    "copy only the src URL (not the whole embed code)."
                ),
                max_length=500,
                verbose_name="Slides Embed URL",
            ),
        ),
    ]
