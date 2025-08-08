"""
Forms for the 'accounts' application, handling user registration and other account-related tasks.
"""

# Django Imports
from django import forms
from django.core.exceptions import ValidationError

# Local Imports
from .models import User


# ==============================================================================
# ACCOUNT FORMS
# ==============================================================================

class SignupForm(forms.ModelForm):
    """
    A form for user registration that includes password confirmation, custom validation for
    username and email, and ensures secure password hashing upon saving.
    """
    # Explicitly define password fields for better control and widget assignment
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Choose a strong password'}),
        label="Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm your password'}),
        label="Confirm Password"
    )

    class Meta:
        model = User
        # List all fields from the model that the form should handle.
        # 'password' is included here, but 'confirm_password' is not, as it doesn't exist on the model.
        fields = [
            'full_name',
            'username',
            'college_email',
            'password',
            'dob',
            'college',
            'department',
            'gender',
            'bio',
            'profile_picture',
        ]
        
        # Define widgets and labels for a better user experience
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'e.g., Rohan Kumar'}),
            'username': forms.TextInput(attrs={'placeholder': 'Create a unique username'}),
            'college_email': forms.EmailInput(attrs={'placeholder': 'your.name.22@poornima.org'}),
            'dob': forms.DateInput(attrs={'type': 'date'}), # Use HTML5 date picker
            'bio': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Tell us a little about yourself...',
            }),
        }
        labels = {
            'dob': 'Date of Birth',
            'profile_picture': 'Upload a Profile Picture',
        }

    def clean_username(self):
        """Validate that the username is unique."""
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with this username already exists.")
        return username

    def clean_college_email(self):
        """Validate the college email domain and its uniqueness."""
        email = self.cleaned_data.get('college_email')
        if not email.endswith('@poornima.org'):
            raise ValidationError("Please use your official @poornima.org college email.")
        if User.objects.filter(college_email__iexact=email).exists():
            raise ValidationError("This email address is already registered.")
        return email

    def clean(self):
        """
        Verify that the two password fields match.
        This method is called after all individual field cleaning methods.
        """
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        
        return cleaned_data

    def save(self, commit=True):
        """
        Override the default save method to handle password hashing.
        """
        # Get the user instance but don't save it to the DB yet (commit=False)
        user = super().save(commit=False)
        # Set the password securely using the built-in method, which handles hashing
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user