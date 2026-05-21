from django.db import migrations


def deduplicate_emails(apps, schema_editor):
    """
    Resolve duplicate email addresses before adding a unique constraint.

    Keeps the most relevant account per email (staff first, then most recent
    login, then lowest pk). Other accounts get a non-routable placeholder email.
    """
    CustomUser = apps.get_model("accounts", "CustomUser")

    by_email = {}
    for user in CustomUser.objects.exclude(email="").iterator():
        key = user.email.lower()
        by_email.setdefault(key, []).append(user)

    for users in by_email.values():
        if len(users) <= 1:
            continue

        users.sort(
            key=lambda u: (
                u.is_staff,
                u.last_login.timestamp() if u.last_login else 0,
                -u.pk,
            ),
            reverse=True,
        )

        for duplicate in users[1:]:
            duplicate.email = f"__duplicate_{duplicate.pk}@invalid.local"
            duplicate.save(update_fields=["email"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(deduplicate_emails, migrations.RunPython.noop),
    ]
