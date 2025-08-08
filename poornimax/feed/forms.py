# Django Imports
from django import forms

# Local Imports
from .models import Post, Comment, Confession, ConfessionComment


# ==============================================================================
# POST FORMS
# ==============================================================================

class PostForm(forms.ModelForm):
    """A form for creating and updating a Post."""
    class Meta:
        model = Post
        fields = ['image', 'caption', 'is_public']
        
        widgets = {
            'caption': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Write a caption...',
            }),
        }
        
        labels = {
            'image': 'Upload an Image',
            'caption': 'Caption',
            'is_public': 'Make this post public?',
        }
        
        help_texts = {
            'is_public': "If checked, this post will be visible to everyone on the explore page.",
        }


class CommentForm(forms.ModelForm):
    """A form for adding a new comment to a Post."""
    class Meta:
        model = Comment
        fields = ['content']
        
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Add a comment...',
                'class': 'comment-popup-input',  # Example of keeping a custom class
            }),
        }
        
        labels = {
            # An empty label can be used if the placeholder is sufficient
            'content': '',
        }


# ==============================================================================
# CONFESSION FORMS
# ==============================================================================

class ConfessionForm(forms.ModelForm):
    """A form for creating a new Confession."""
    class Meta:
        model = Confession
        fields = ['content', 'is_anonymous']
        
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Share your confession here. It will be posted for others to see.',
            }),
        }
        
        labels = {
            'content': 'Your Confession',
            'is_anonymous': 'Post Anonymously',
        }


class ConfessionCommentForm(forms.ModelForm):
    """A form for adding a new comment to a Confession."""
    class Meta:
        model = ConfessionComment
        fields = ['content', 'is_anonymous']
        
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Write a thoughtful comment...',
            }),
        }
        
        labels = {
            'content': 'Your Comment',
            'is_anonymous': 'Comment Anonymously',
        }