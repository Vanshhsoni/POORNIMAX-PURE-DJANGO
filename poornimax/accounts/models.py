from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

# College choices
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
    ('AI DS', 'AI DS')
]

GENDER_CHOICES = [
    ('Male', 'Male'),
    ('Female', 'Female'),
    ('Other', 'Other'),
]

class User(AbstractUser):
    objects = UserManager()

    full_name = models.CharField(max_length=255, default="No Name Provided")
    college_email = models.EmailField(unique=True, default="noemail@poornima.org")
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    college = models.CharField(max_length=50, choices=COLLEGE_CHOICES)
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    dob = models.DateField(default='2000-01-01')
    otp_verified = models.BooleanField(default=False)
    has_answered_questionnaire = models.BooleanField(default=False)
    is_profile_locked = models.BooleanField(default=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['college_email', 'full_name', 'dob', 'college', 'department', 'gender']

    def __str__(self):
        return self.username

    # Check if mutual heart exists with another user
    def has_mutual_heart(self, other_user):
        return Crush.objects.filter(
            sender=self, receiver=other_user, is_mutual=True
        ).exists()


# Profile Model - Single definition
class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    has_answered_questionnaire = models.BooleanField(default=False)
    # Add any other profile fields you need here
    
    def __str__(self):
        return f'{self.user.username} Profile'


# Signal to create Profile when User is created
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


# 💘 Crush Model
class Crush(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='crushes_sent')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='crushes_received')
    is_mutual = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        status = "Mutual ❤️" if self.is_mutual else "Sent 💘"
        return f"{self.sender.username} → {self.receiver.username} [{status}]"

    def check_mutual_and_create_friendship(self):
        reverse = Crush.objects.filter(sender=self.receiver, receiver=self.sender).first()
        if reverse:
            self.is_mutual = True
            reverse.is_mutual = True
            self.save()
            reverse.save()

            # Ensure the friendship is created only if it doesn't exist
            if not Friendship.are_friends(self.sender, self.receiver):
                Friendship.objects.get_or_create(user1=self.sender, user2=self.receiver)


# 🤝 Friendship Model
class Friendship(models.Model):
    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='friendships_from')
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='friendships_to')
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)  # Track when friendship is confirmed

    class Meta:
        unique_together = ('user1', 'user2')

    def __str__(self):
        return f"{self.user1.username} 🤝 {self.user2.username}"

    @staticmethod
    def are_friends(user1, user2):
        return Friendship.objects.filter(
            models.Q(user1=user1, user2=user2) |
            models.Q(user1=user2, user2=user1)
        ).exists()

    @staticmethod
    def get_or_create_friendship(user1, user2):
        """Returns existing friendship or creates one if it doesn't exist."""
        return Friendship.objects.get_or_create(user1=user1, user2=user2)


# UserQuestionnaire Model
class UserQuestionnaire(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='questionnaire')

    # Step 1: About You
    personality = models.CharField(max_length=50, blank=True)
    communication_style = models.CharField(max_length=50, blank=True)

    # Step 2: Your Vibe
    hobbies_interests = models.TextField(blank=True)
    
    # Step 3: Connections
    year = models.CharField(max_length=50, blank=True)
    relationship_status = models.CharField(max_length=50, blank=True)
    
    # Updated 'looking_for' field with more specific choices
    looking_for = models.CharField(max_length=50, blank=True, choices=[
        ('Friendship', 'Friendship'),
        ('Girlfriend', 'Girlfriend'),
        ('Boyfriend', 'Boyfriend'),
        ('Serious Relationship', 'Serious Relationship'),
        ('FWB', 'FWB'),
        ('Something Casual', 'Something Casual'),
        ("Let's see where it goes", "Let's see where it goes"),
    ])

    def __str__(self):
        return f"Questionnaire for {self.user.username}"


# ProfileView Model
class ProfileView(models.Model):
    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile_views_made')
    viewed = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile_views_received')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('viewer', 'viewed')  # Remove timestamp from unique_together
        
    def __str__(self):
        return f"{self.viewer.username} viewed {self.viewed.username}'s profile"