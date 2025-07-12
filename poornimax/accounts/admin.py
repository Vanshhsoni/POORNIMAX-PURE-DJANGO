from django.contrib import admin
from django.contrib.auth import get_user_model

# Get your custom User model
User = get_user_model()

# Register the User model to the admin panel
admin.site.register(User)
