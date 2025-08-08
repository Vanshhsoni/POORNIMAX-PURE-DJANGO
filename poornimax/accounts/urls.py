

# Django Imports
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

# Local Imports
from . import views

# Define the application namespace for URL reversing
app_name = 'accounts'


urlpatterns = [
    # ==============================================================================
    # AUTHENTICATION & SESSION MANAGEMENT
    # ==============================================================================
    # Renders the initial page with options to sign up or log in
    path('signup_or_login/', views.load_signup, name='load_signup'),

    # Renders the main signup form page
    path('signup/', views.login_signup, name='login_signup'),
    
    # Handles the submission from the signup form
    path('signup_access/', views.signup_access, name='signup_access'),

    # Renders a dedicated login page
    path('login/', views.load_login, name='load_login'),

    # Handles the submission from the login form
    path('login_access/', views.login_access, name='login_access'),

    # OTP verification page and logic
    path('verify-otp/', views.verify_otp, name='verify_otp'),

    # User logout
    path('logout/', views.logout_view, name='logout'),

    # ==============================================================================
    # USER ONBOARDING & SETUP
    # ==============================================================================
    path('questionnaire/', views.questionnaire_view, name='questionnaire_view'),
    path('ans/', views.answers_view, name='answers_page'),

    # ==============================================================================
    # USER PROFILE MANAGEMENT
    # ==============================================================================
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('delete-account/', views.delete_account, name='delete_account'),

    # ==============================================================================
    # MISCELLANEOUS / UNCATEGORIZED
    # ==============================================================================
    # TODO: Rename these paths and views to be more descriptive of their function
    path('x/', views.x, name='x'),
    path('z/', views.z, name='z'),
]

# ==============================================================================
# DEVELOPMENT SETTINGS
# ==============================================================================
# This is used to serve media files during development.
# In a production environment, your web server (e.g., Nginx) should handle this.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)