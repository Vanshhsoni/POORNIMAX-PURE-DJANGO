import os
import random
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from .models import User, UserQuestionnaire



otp_store = {}
User = get_user_model()

def load_signup(request):
    return render(request, 'accounts/signup.html')

def load_login(request):
    return render(request, 'accounts/login.html')

def login_signup(request):
    return render(request,'accounts/login_signup.html')
@login_required
def x(request):
    return render(request, 'accounts/x.html')  # Dummy success/dashboard page

@login_required
def z(request):
    return render(request,'accounts/z.html')



def signup_access(request):
    if request.method == 'POST':
        data = request.POST
        profile_picture = request.FILES.get('profile_picture')

        email = data.get('college_email')
        if not email.endswith('@poornima.org'):
            messages.error(request, "Use only your college email (@poornima.org).")
            return redirect('accounts:load_signup')

        if User.objects.filter(username=data['username']).exists():
            messages.error(request, 'Username already taken.')
            return redirect('accounts:load_signup')

        if User.objects.filter(college_email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('accounts:load_signup')

        if data['password'] != data['confirm_password']:
            messages.error(request, 'Passwords do not match.')
            return redirect('accounts:load_signup')

        # Use create_user to handle password hashing
        user = User.objects.create_user(
            full_name=data['full_name'],
            college_email=email,
            username=data['username'],
            password=data['password'],  # Hashed automatically
            dob=data['dob'],
            college=data['college'],
            department=data['department'],
            gender=data['gender'],
            bio=data['bio']
        )

        if profile_picture:
            path = os.path.join(settings.MEDIA_ROOT, 'profile_pics', user.username)
            os.makedirs(path, exist_ok=True)
            fs = FileSystemStorage(location=path)
            filename = fs.save(profile_picture.name, profile_picture)
            user.profile_picture.name = f'profile_pics/{user.username}/{filename}'
            user.save()

        messages.success(request, "Account created! Now login with OTP.")
        return redirect('accounts:load_login')

    return render(request, 'accounts/signup.html')

# accounts/views.py

import random
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from .models import User # Make sure to import your User model

# This is assumed to be a temporary in-memory store.
# For production, consider using request.session or a cache like Redis.
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import random

otp_store = {}

def login_access(request):
    if request.method == 'POST':
        email = request.POST.get('college_email')
        try:
            user = User.objects.get(college_email=email)
            otp = str(random.randint(100000, 999999))
            otp_store[email] = otp

            # HTML content with blue theme
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; background-color: #f4f8fb; padding: 20px;">
                    <div style="max-width: 500px; margin: auto; background: white; border-radius: 8px; 
                                padding: 20px; border: 1px solid #d9eaf7;">
                        <h2 style="color: #1e88e5; text-align: center;">PoornimaX Login OTP</h2>
                        <p style="font-size: 16px; color: #333;">
                            Hello <b>{user.first_name}</b>,<br><br>
                            Your One-Time Password (OTP) for login is:
                        </p>
                        <div style="background-color: #e3f2fd; padding: 15px; text-align: center; 
                                    font-size: 24px; font-weight: bold; color: #1e88e5; 
                                    border-radius: 6px;">
                            {otp}
                        </div>
                        <p style="font-size: 14px; color: #666; margin-top: 20px;">
                            This OTP will be valid for the next 5 minutes. Do not share it with anyone.
                        </p>
                    </div>
                </body>
            </html>
            """

            # Fallback plain text
            text_content = f"Your PoornimaX OTP is: {otp}"

            msg = EmailMultiAlternatives(
                subject="Your PoornimaX OTP",
                body=text_content,
                from_email=settings.EMAIL_HOST_USER,
                to=[email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()

            return render(request, 'accounts/login.html', {
                'show_otp': True,
                'email': email
            })

        except User.DoesNotExist:
            messages.error(request, "Email not found.")
            return redirect('accounts:load_login')

    return render(request, 'accounts/login.html')



def verify_otp(request):
    if request.method == 'POST':
        email = request.POST.get('college_email')
        submitted_otp = request.POST.get('otp')

        # Check if the stored OTP matches the submitted one
        if otp_store.get(email) == submitted_otp:
            # --- OTP IS CORRECT ---
            try:
                user = User.objects.get(college_email=email)
                user.otp_verified = True
                user.save()

                login(request, user)  # Create the user's session

                # Clean up the used OTP
                if email in otp_store:
                    del otp_store[email]

                # Redirect to the appropriate page
                if user.has_answered_questionnaire:
                    return redirect('feed:home')
                else:
                    return redirect('accounts:x')

            except User.DoesNotExist:
                messages.error(request, "An unexpected error occurred. Please try again.")
                return redirect('accounts:load_login')
        else:
            # --- OTP IS INCORRECT ---
            # Re-render the login page with the OTP popup still active
            # and pass a specific error message.
            context = {
                'show_otp': True,
                'email': email,
                'otp_error': 'Invalid OTP. Please try again.'
            }
            return render(request, 'accounts/login.html', context)

    # If the request method isn't POST, redirect to the login page.
    return redirect('accounts:load_login')

@login_required
def answers_view(request):
    user = request.user
    questionnaire = UserQuestionnaire.objects.get(user=user)

    def to_list(value):
        return [v.strip() for v in value.split(',')] if value else []

    context = {
        'user': user,
        'questionnaire': questionnaire,
        'hobbies': to_list(questionnaire.hobbies),
        'college_events': to_list(questionnaire.college_events),
        'weekend_plans': to_list(questionnaire.weekend_plans),
        'friendship_values': to_list(questionnaire.friendship_values),
        'content_posting': to_list(questionnaire.content_posting),
        'college_excitements': to_list(questionnaire.college_excitements),
        'learning_preferences': to_list(questionnaire.learning_preferences),
        'relaxation_methods': to_list(questionnaire.relaxation_methods),
    }
    return render(request, 'accounts/ans.html', context)

# in views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UserQuestionnaire 
# Make sure to import your updated model

# in views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UserQuestionnaire 
# Make sure to import your updated model

# in your app/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UserQuestionnaire # Make sure to import your updated model
# from accounts.models import Profile # Make sure you have a Profile model or similar


# in your app/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UserQuestionnaire, Profile

@login_required
def questionnaire_view(request):
    user = request.user
    
    # Ensure user has a profile
    profile, created = Profile.objects.get_or_create(user=user)
    
    # Check if user already completed questionnaire
    if profile.has_answered_questionnaire:
        messages.info(request, "You have already completed the questionnaire.")
        return redirect('feed:home')  # Adjust redirect as needed
    
    # Get 'looking_for' choices directly from the model for consistency
    looking_for_choices = [choice[0] for choice in UserQuestionnaire._meta.get_field('looking_for').choices]
    
    context = {
        'personality_choices': ['Introvert', 'Extrovert', 'A mix of both'],
        'comm_style_choices': ['Mostly texting', 'Voice & video calls', 'A bit of everything'],
        'hobbies_choices': ['Gaming', 'Music', 'Movies & Shows', 'Coding', 'Sports', 'Art & Design', 'Reading', 'Travel', 'Foodie'],
        'year_choices': ['1st Year', '2nd Year', '3rd Year', 'Final Year', 'Postgraduate'],
        'status_choices': ['Single', 'Taken', "It's Complicated", 'Focusing on me'],
        'looking_for_choices': looking_for_choices,
    }

    if request.method == 'POST':
        try:
            data = request.POST
            
            # Validate required fields
            required_fields = ['personality', 'communication_style', 'year', 'relationship_status', 'looking_for']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                messages.error(request, f"Please fill in all required fields: {', '.join(missing_fields)}")
                return render(request, 'accounts/questionnaire.html', context)
            
            # Create or update questionnaire
            questionnaire, created = UserQuestionnaire.objects.get_or_create(user=user)

            # Save data from the form
            questionnaire.personality = data.get('personality', '')
            questionnaire.communication_style = data.get('communication_style', '')
            questionnaire.year = data.get('year', '')
            questionnaire.relationship_status = data.get('relationship_status', '')
            questionnaire.looking_for = data.get('looking_for', '')
            
            # Handle hobbies (checkbox values)
            hobbies_list = data.getlist('hobbies_interests')
            if len(hobbies_list) > 5:
                messages.error(request, "Please select maximum 5 hobbies.")
                return render(request, 'accounts/questionnaire.html', context)
            
            questionnaire.hobbies_interests = ','.join(hobbies_list)
            questionnaire.save()

            # Update profile and user
            profile.has_answered_questionnaire = True
            profile.save()
            
            user.has_answered_questionnaire = True
            user.save()
            
            messages.success(request, "Your profile is set up! Let's find your vibe.")
            return redirect('feed:home')  # Adjust redirect as needed
            
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'accounts/questionnaire.html', context)

    else:
        # Pre-populate form if questionnaire exists
        try:
            questionnaire = UserQuestionnaire.objects.get(user=user)
            context['questionnaire'] = questionnaire
            if questionnaire.hobbies_interests:
                context['selected_hobbies'] = questionnaire.hobbies_interests.split(',')
        except UserQuestionnaire.DoesNotExist:
            pass

    return render(request, 'accounts/questionnaire.html', context)

@login_required
def edit_profile(request):
    user = request.user
    questionnaire, created = UserQuestionnaire.objects.get_or_create(user=user)

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        bio = request.POST.get('bio')
        department = request.POST.get('department')
        year = request.POST.get('year')
        profile_picture = request.FILES.get('profile_picture')

        # Update user fields
        user.full_name = full_name
        user.bio = bio
        user.department = department
        if profile_picture:
            user.profile_picture = profile_picture
        user.save()

        # Update questionnaire year
        questionnaire.year = year
        questionnaire.save()

        messages.success(request, "Profile updated successfully!")
        return redirect('feed:profile', user_id=request.user.id)


    return render(request, 'accounts/edit_profile.html', {
        'user': user,
        'questionnaire': questionnaire
    })
@login_required
def delete_account(request):
    user = request.user
    logout(request)
    user.delete()
    messages.success(request, "Your account has been deleted successfully.")
    return redirect('accounts:login_signup')

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('accounts:login_signup')