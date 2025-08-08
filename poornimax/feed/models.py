# Python Standard Library
import os

# Django Imports
from django.conf import settings
from django.db import models
from django.utils import timezone


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def post_image_path(instance, filename):
    """
    Generate file path for new post images.
    Uploads to: MEDIA_ROOT/posts/<username>/<filename>
    """
    return f'posts/{instance.user.username}/{filename}'


# ==============================================================================
# POST MODELS
# ==============================================================================

class Post(models.Model):
    """Represents a user's post in the feed, containing an image and caption."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='posts'
    )
    image = models.ImageField(upload_to=post_image_path)
    caption = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_public = models.BooleanField(default=False, help_text="Designates whether the post is visible to everyone.")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Post"
        verbose_name_plural = "Posts"

    def __str__(self):
        return f"Post by {self.user.username} on {self.created_at.strftime('%b %d, %Y')}"


class Like(models.Model):
    """Represents a 'like' from a user on a specific Post."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensures a user can only like a post once
        unique_together = ('post', 'user')
        ordering = ['-created_at']
        verbose_name = "Like"
        verbose_name_plural = "Likes"

    def __str__(self):
        return f"Like by {self.user.username} on {self.post}"


class Comment(models.Model):
    """Represents a comment from a user on a specific Post."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Comment"
        verbose_name_plural = "Comments"

    def __str__(self):
        return f"Comment by {self.user.username} on {self.post}"


# ==============================================================================
# CONFESSION MODELS
# ==============================================================================

class Confession(models.Model):
    """Represents a user's confession, which can be posted anonymously."""
    content = models.TextField()
    is_anonymous = models.BooleanField(default=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='confessions',
        null=True,  # Allows for truly anonymous confessions if user is not set
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Confession"
        verbose_name_plural = "Confessions"

    def __str__(self):
        if self.is_anonymous:
            return f"Anonymous confession on {self.created_at.strftime('%b %d, %Y')}"
        return f"Confession by {self.user.username} on {self.created_at.strftime('%b %d, %Y')}"


class ConfessionLike(models.Model):
    """Represents a 'like' from a user on a specific Confession."""
    confession = models.ForeignKey(Confession, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensures a user can only like a confession once
        unique_together = ('confession', 'user')
        ordering = ['-created_at']
        verbose_name = "Confession Like"
        verbose_name_plural = "Confession Likes"

    def __str__(self):
        return f"Like by {self.user.username} on Confession #{self.confession.id}"


class ConfessionComment(models.Model):
    """Represents a comment from a user on a specific Confession."""
    confession = models.ForeignKey(Confession, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']  # Show comments in chronological order
        verbose_name = "Confession Comment"
        verbose_name_plural = "Confession Comments"

    def __str__(self):
        user_display = "Anonymous" if self.is_anonymous else self.user.username
        return f"Comment by {user_display} on Confession #{self.confession.id}"