from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        # We only need the username and password fields which are included by default in UserCreationForm,
        # but we explicitly define the fields here for clarity.
        fields = ('username',)
