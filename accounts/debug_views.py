"""
Temporary email debug view — accessible to superusers only.
Visit /accounts/email-test/ to test SMTP and see the exact error.
Remove this after email is confirmed working.
"""
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.conf import settings
import traceback


@staff_member_required
def email_test(request):
    results = []
    results.append(f"<b>EMAIL_BACKEND:</b> {settings.EMAIL_BACKEND}")
    results.append(f"<b>EMAIL_HOST:</b> {getattr(settings, 'EMAIL_HOST', 'NOT SET')}")
    results.append(f"<b>EMAIL_PORT:</b> {getattr(settings, 'EMAIL_PORT', 'NOT SET')}")
    results.append(f"<b>EMAIL_HOST_USER:</b> {getattr(settings, 'EMAIL_HOST_USER', 'NOT SET')}")
    pw = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
    results.append(f"<b>EMAIL_HOST_PASSWORD:</b> {'SET (' + str(len(pw)) + ' chars)' if pw else 'NOT SET'}")
    results.append(f"<b>EMAIL_USE_TLS:</b> {getattr(settings, 'EMAIL_USE_TLS', 'NOT SET')}")
    results.append(f"<b>DEFAULT_FROM_EMAIL:</b> {settings.DEFAULT_FROM_EMAIL}")
    results.append("<hr>")

    to_email = request.GET.get("to", settings.DEFAULT_FROM_EMAIL)
    results.append(f"<b>Sending test email to:</b> {to_email}")
    results.append("<hr>")

    try:
        send_mail(
            subject="MarathonLMS — Test Email",
            message="This is a test email sent from the MarathonLMS debug view.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
        results.append('<b style="color:green">✅ SUCCESS! Email sent successfully.</b>')
    except Exception as e:
        results.append(f'<b style="color:red">❌ FAILED: {type(e).__name__}</b>')
        results.append(f'<pre>{traceback.format_exc()}</pre>')

    html = "<br>".join(results)
    return HttpResponse(f"""
    <html><body style="font-family:monospace;padding:20px;background:#1a1d27;color:#e8e8e8;">
    <h2>📧 Email Debug</h2>
    {html}
    <br><br>
    <a href="?to=meiriyali002@gmail.com" style="color:#6366f1">Send test to meiriyali002@gmail.com</a>
    </body></html>
    """)
