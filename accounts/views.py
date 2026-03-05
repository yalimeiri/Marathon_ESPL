from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth import login
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
        # Call the parent class's form_valid to handle the redirect
        return super().form_valid(form)
