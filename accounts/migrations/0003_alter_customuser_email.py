from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_deduplicate_emails"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="email",
            field=models.EmailField(
                blank=True,
                max_length=254,
                unique=True,
                verbose_name="email address",
            ),
        ),
    ]
