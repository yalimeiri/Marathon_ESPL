from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Send a test email using the configured email backend (Brevo/SMTP/console)."

    def add_arguments(self, parser):
        parser.add_argument(
            "recipient",
            help="Email address to send the test message to.",
        )

    def handle(self, *args, **options):
        recipient = options["recipient"].strip()
        if not recipient:
            raise CommandError("Recipient email is required.")

        backend = settings.EMAIL_BACKEND
        from_email = settings.DEFAULT_FROM_EMAIL

        self.stdout.write(f"EMAIL_BACKEND: {backend}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL: {from_email or '(empty)'}")
        self.stdout.write(f"Sending test email to: {recipient}")

        if not from_email:
            raise CommandError(
                "DEFAULT_FROM_EMAIL is not set. Add it in Railway variables "
                "and use a sender verified in Brevo."
            )

        try:
            send_mail(
                subject="Marathon ESPL — test email",
                message="If you received this, email delivery is working.",
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False,
            )
        except Exception as exc:
            raise CommandError(f"Email send failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Test email sent successfully."))
