from django.db import migrations, models


def _user_priority(user):
    return (
        user.is_staff,
        user.last_login.timestamp() if user.last_login else 0,
        -user.pk,
    )


def ensure_unique_emails(apps, schema_editor):
    """
    Resolve all email duplicates before adding a unique constraint.

    Handles blank/whitespace emails (PostgreSQL treats '' as a duplicate key)
    and any remaining duplicate non-empty addresses.
    """
    CustomUser = apps.get_model("accounts", "CustomUser")

    blank_users = [
        user
        for user in CustomUser.objects.iterator()
        if not user.email or not user.email.strip()
    ]
    blank_users.sort(key=_user_priority, reverse=True)
    for user in blank_users[1:]:
        user.email = f"__noemail_{user.pk}@invalid.local"
        user.save(update_fields=["email"])

    by_email = {}
    for user in CustomUser.objects.exclude(email="").iterator():
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
        migrations.RunPython(ensure_unique_emails, migrations.RunPython.noop),
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
