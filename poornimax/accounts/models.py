# accounts/models.py

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

# ==============================================================================
# CHOICES CONSTANTS
# ==============================================================================

COLLEGE_CHOICES = [
    ('PCE', 'PCE'),
    ('PIET', 'PIET'),
    ('PU', 'PU'),
]

DEPARTMENT_CHOICES = [
    ('CORE', 'CORE'),
    ('ECE', 'ECE'),
    ('Cyber Security', 'Cyber Security'),
    ('IT', 'IT'),
    ('Civil', 'Civil'),
    ('Mechanical', 'Mechanical'),
    ('Electrical', 'Electrical'),
    ('AI', 'AI'),
    ('AI DS', 'AI DS'),
]

GENDER_CHOICES = [
    ('Male', 'Male'),
    ('Female', 'Female'),
    ('Other', 'Other'),
]

RELATIONSHIP_CHOICES = [
    ('Friendship', 'Friendship'),
    ('Girlfriend', 'Girlfriend'),
    ('Boyfriend', 'Boyfriend'),
    ('Serious Relationship', 'Serious Relationship'),
    ('FWB', 'FWB'),
    ('Something Casual', 'Something Casual'),
    ("Let's see where it goes", "Let's see where it goes"),
]

# ==============================================================================
# CORE USER MODEL
# ==============================================================================

class User(AbstractUser):
    """Custom User model extending Django's AbstractUser."""
    objects = UserManager()

    # Extended Fields
    full_name = models.CharField(max_length=255, default="No Name Provided")
    college_email = models.EmailField(unique=True, default="noemail@poornima.org")
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    college = models.CharField(max_length=50, choices=COLLEGE_CHOICES)
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    dob = models.DateField(default='2000-01-01')

    # Status Fields
    otp_verified = models.BooleanField(default=False)
    has_answered_questionnaire = models.BooleanField(default=False)
    is_profile_locked = models.BooleanField(default=True, help_text="If true, profile is not publicly visible.")

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['college_email', 'full_name', 'dob', 'college', 'department', 'gender']

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.username

    def has_mutual_heart(self, other_user):
        """Checks if a mutual crush exists with another user."""
        return Crush.objects.filter(sender=self, receiver=other_user, is_mutual=True).exists()

# ==============================================================================
# USER PROFILE MODEL
# ==============================================================================

class Profile(models.Model):
    """Additional profile info for a user."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    has_answered_questionnaire = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.username} Profile'

# Create profile automatically
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)

# ==============================================================================
# USER QUESTIONNAIRE MODEL
# ==============================================================================

class UserQuestionnaire(models.Model):
    """Stores a user's onboarding questionnaire answers."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='questionnaire')
    personality = models.CharField(max_length=50, blank=True)
    communication_style = models.CharField(max_length=50, blank=True)
    hobbies_interests = models.TextField(blank=True)
    year = models.CharField(max_length=50, blank=True)
    relationship_status = models.CharField(max_length=50, blank=True)
    looking_for = models.CharField(max_length=50, blank=True, choices=RELATIONSHIP_CHOICES)

    def __str__(self):
        return f"Questionnaire for {self.user.username}"

# ==============================================================================
# CRUSH MODEL
# ==============================================================================

class Crush(models.Model):
    """Represents a 'crush' sent from one user to another."""
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='crushes_sent')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='crushes_received')
    is_mutual = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')
        verbose_name = "Crush"
        verbose_name_plural = "Crushes"

    def __str__(self):
        status = "Mutual ❤️" if self.is_mutual else "Sent 💘"
        return f"{self.sender.username} → {self.receiver.username} [{status}]"

    def check_mutual_and_create_friendship(self):
        """Check if reverse crush exists and mark both as mutual, creating friendship."""
        reverse = Crush.objects.filter(sender=self.receiver, receiver=self.sender).first()
        if reverse:
            self.is_mutual = True
            reverse.is_mutual = True
            self.save()
            reverse.save()
            if not Friendship.are_friends(self.sender, self.receiver):
                Friendship.objects.get_or_create(user1=self.sender, user2=self.receiver)

# ==============================================================================
# FRIENDSHIP MODEL
# ==============================================================================

class Friendship(models.Model):
    """Represents a confirmed mutual friendship."""
    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='friendships_from')
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='friendships_to')
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)  # optional timestamp for when confirmed

    class Meta:
        unique_together = ('user1', 'user2')
        verbose_name = "Friendship"
        verbose_name_plural = "Friendships"

    def __str__(self):
        return f"{self.user1.username} 🤝 {self.user2.username}"

    @staticmethod
    def are_friends(user1, user2):
        return Friendship.objects.filter(
            models.Q(user1=user1, user2=user2) |
            models.Q(user1=user2, user2=user1)
        ).exists()

# ==============================================================================
# PROFILE VIEW MODEL
# ==============================================================================

class ProfileView(models.Model):
    """Logs when a user views another user's profile."""
    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile_views_made')
    viewed = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile_views_received')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('viewer', 'viewed')
        ordering = ['-timestamp']
        verbose_name = "Profile View"
        verbose_name_plural = "Profile Views"

    def __str__(self):
        return f"{self.viewer.username} viewed {self.viewed.username}'s profile"