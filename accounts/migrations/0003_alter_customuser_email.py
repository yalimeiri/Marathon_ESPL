from django.db import migrations, models


def _user_priority(user):
    return (
        user.is_staff,
        user.last_login.timestamp() if user.last_login else 0,
        -user.pk,
    )


def cleanup_emails(apps, schema_editor):
    """
    Clean up duplicate and blank emails without adding a DB unique constraint.

    - Blank/whitespace emails → NULL (many users may have no email)
    - Duplicate non-empty emails → keep best account, reassign others
    """
    CustomUser = apps.get_model("accounts", "CustomUser")

    CustomUser.objects.filter(email="").update(email=None)

    for user in CustomUser.objects.exclude(email__isnull=True).iterator():
        if not user.email.strip():
            user.email = None
            user.save(update_fields=["email"])

    by_email = {}
    for user in CustomUser.objects.exclude(email__isnull=True).iterator():
        key = user.email.lower()
        by_email.setdefault(key, []).append(user)

    for users in by_email.values():
        if len(users) <= 1:
            continue
        users.sort(key=_user_priority, reverse=True)
        for duplicate in users[1:]:
            duplicate.email = f"__duplicate_{duplicate.pk}@invalid.local"
            duplicate.save(update_fields=["email"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_deduplicate_emails"),
    ]

    operations = [
        migrations.RunPython(cleanup_emails, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customuser",
            name="email",
            field=models.EmailField(
                blank=True,
                max_length=254,
                null=True,
                verbose_name="email address",
            ),
        ),
    ]
