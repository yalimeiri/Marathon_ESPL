from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth import login
from django.core.mail import send_mail
from django.conf import settings
from .forms import CustomUserCreationForm

class RegisterView(CreateView):
    """
    Handles user registration.
    On successful form submission, the user is saved to the database,
    automatically logged in (which triggers the SingleDeviceLoginMiddleware 
    to assign them a device_uuid), and redirected to the course list.
    """
    form_class = CustomUserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('courses:category-list')

    def form_valid(self, form):
        # Save the user first
        user = form.save()
        # Log the user in immediately after registering
        login(self.request, user)

        # Send a welcome email
        try:
            site_url = self.request.build_absolute_uri('/courses/')
            send_mail(
                subject="ברוך הבא ל-MarathonLMS!",
                message=(
                    f"שלום {user.username},\n\n"
                    f"ההרשמה שלך הסתיימה בהצלחה!\n\n"
                    f"שם משתמש: {user.username}\n\n"
                    f"כדי להיכנס לאתר: {site_url}\n\n"
                    f"שים לב: החשבון שלך נעול למחשב/דפדפן שבו נרשמת.\n\n"
                    f"בברכה,\nצוות MarathonLMS"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,  # Don't crash if email fails
            )
        except Exception:
            pass  # Never let email failure block registration

        # Call the parent class's form_valid to handle the redirect
        return super().form_valid(form)

