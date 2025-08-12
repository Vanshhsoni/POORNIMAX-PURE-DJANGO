# Django Core Imports
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince
from django.http import JsonResponse, HttpResponse
from django.db import models
from django.db.models import Count, Exists, OuterRef, Q
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
# Make sure you have this import
from django.db.models import OuterRef, Exists
# App-specific Imports
from .forms import PostForm, ConfessionForm, ConfessionCommentForm
from .models import Post, Like, Comment, Confession, ConfessionLike, ConfessionComment
from accounts.models import UserQuestionnaire, Crush, Friendship, ProfileView

# Get the User model
User = get_user_model()

# Define constants for avatar URLs
DEFAULT_AVATAR_URL = '/static/ann.png' # Make sure this path is correct
ANONYMOUS_AVATAR_URL = '/static/ann.png' # Make sure this path is correct


# --- Utility Functions (Ideally in a separate 'utils.py' file) ---

def _calculate_jaccard_similarity(set1, set2):
    """Helper function to calculate similarity for lists like hobbies."""
    if not set1 and not set2:
        return 1.0
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union != 0 else 0

def calculate_compatibility(user1, user2):
    """Calculates a compatibility score between two users based on their questionnaire answers."""
    try:
        q1 = UserQuestionnaire.objects.get(user=user1)
        q2 = UserQuestionnaire.objects.get(user=user2)
    except UserQuestionnaire.DoesNotExist:
        return None

    INTENT_WEIGHT, PERSONALITY_WEIGHT, HOBBIES_WEIGHT = 50, 30, 20
    total_score = 0

    # 1. Intent & Life Stage
    intent_score, intent_max_score = 0, 4
    if q1.relationship_status == q2.relationship_status:
        intent_score += 2
    elif {q1.relationship_status, q2.relationship_status} <= {'Single', 'Focusing on me'}:
        intent_score += 1
    if q1.looking_for == q2.looking_for:
        intent_score += 1
    elif 'New friends' in {q1.looking_for, q2.looking_for} and 'Not sure yet' in {q1.looking_for, q2.looking_for}:
        intent_score += 0.5
    if q1.year == q2.year:
        intent_score += 1
    total_score += (intent_score / intent_max_score) * INTENT_WEIGHT

    # 2. Personality & Communication
    personality_score, personality_max_score = 0, 4
    if q1.personality == q2.personality:
        personality_score += 2
    elif 'A mix of both' in {q1.personality, q2.personality}:
        personality_score += 1.5
    elif {q1.personality, q2.personality} == {'Introvert', 'Extrovert'}:
        personality_score += 0.5
    if q1.communication_style == q2.communication_style:
        personality_score += 2
    elif 'A bit of everything' in {q1.communication_style, q2.communication_style}:
        personality_score += 1.5
    total_score += (personality_score / personality_max_score) * PERSONALITY_WEIGHT
    
    # 3. Hobbies & Interests
    hobbies1 = set(q1.hobbies_interests.split(',')) if q1.hobbies_interests else set()
    hobbies2 = set(q2.hobbies_interests.split(',')) if q2.hobbies_interests else set()
    hobby_similarity = _calculate_jaccard_similarity(hobbies1, hobbies2)
    total_score += hobby_similarity * HOBBIES_WEIGHT
    
    final_score = max(19, min(99, round(total_score)))
    return final_score


# --- Main Page Views ---
@login_required
def home(request):
    """
    Updated home view - removed initial post loading to rely on lazy loading
    """
    current_user = request.user
    all_users_qs = User.objects.exclude(id=current_user.id)

    # Logic for stats and user carousels (keep this the same)
    profile_views = ProfileView.objects.filter(viewed=current_user).values('viewer').distinct().count()

    def get_crush_status(person):
        sent = Crush.objects.filter(sender=current_user, receiver=person).exists()
        received = Crush.objects.filter(sender=person, receiver=current_user).exists()
        if sent and received: return "mutual"
        if sent: return "sent"
        if received: return "received"
        return "none"

    recently_joined = all_users_qs.filter(date_joined__gte=timezone.now() - timezone.timedelta(days=7))[:10]

    try:
        user_year = current_user.questionnaire.year
        same_year = [uq.user for uq in UserQuestionnaire.objects.filter(year=user_year).exclude(user=current_user).select_related('user')[:10]]
    except (UserQuestionnaire.DoesNotExist, AttributeError):
        same_year = []

    same_department = all_users_qs.filter(department=current_user.department)[:10] if current_user.department else []
    same_college = all_users_qs.filter(college=current_user.college)[:10] if current_user.college else []
    
    def annotate_users_with_crush(users):
        return [{'user': person, 'crush_status': get_crush_status(person)} for person in users]

    context = {
        # REMOVED: 'public_posts': public_posts,  # Let lazy loading handle this
        'profile_views': profile_views,
        'recently_joined': annotate_users_with_crush(recently_joined),
        'same_year': annotate_users_with_crush(same_year),
        'same_department': annotate_users_with_crush(same_department),
        'same_college': annotate_users_with_crush(same_college),
        'hearts_sent': Crush.objects.filter(sender=current_user, is_mutual=False).count(),
        'hearts_received': Crush.objects.filter(receiver=current_user, is_mutual=False).count(),
        'friends': Crush.objects.filter(sender=current_user, is_mutual=True).count(),
    }
    return render(request, 'feed/home.html', context)

@login_required
def profile(request, user_id):
    """
    Renders a user's profile page, handling post visibility based on friendship.
    """
    profile_user = get_object_or_404(User, id=user_id)
    
    if request.user != profile_user:
        ProfileView.objects.get_or_create(viewer=request.user, viewed=profile_user)

    is_mutual = Crush.objects.filter(sender=request.user, receiver=profile_user, is_mutual=True).exists()

    # REVISED: Post visibility logic
    if request.user == profile_user or is_mutual:
        posts_qs = Post.objects.filter(user=profile_user) # View all posts
    else:
        posts_qs = Post.objects.filter(user=profile_user, is_public=True) # View only public posts

    posts = posts_qs.annotate(
        likes_count=Count('likes', distinct=True),
        comments_count=Count('comments', distinct=True)
    ).order_by('-created_at')
    
    context = {
        'profile_user': profile_user,
        'sent_crush': Crush.objects.filter(sender=request.user, receiver=profile_user).exists(),
        'received_crush': Crush.objects.filter(sender=profile_user, receiver=request.user).exists(),
        'is_mutual': is_mutual,
        'posts': posts,
        'compatibility_score': calculate_compatibility(request.user, profile_user) if request.user != profile_user else None,
    }
    return render(request, 'feed/profile.html', context)

@login_required
def all_users(request):
    """Renders a page with all other users, sorted by compatibility score."""
    users = User.objects.exclude(id=request.user.id)
    compatibility_scores = []
    for user in users:
        score = calculate_compatibility(request.user, user)
        if score is not None:
            compatibility_scores.append((user, score))
    compatibility_scores.sort(key=lambda x: x[1], reverse=True)
    return render(request, 'feed/all.html', {'compatibility_scores': compatibility_scores})

@login_required
def explore(request):
    """Renders the Confessions explore page."""
    user_confession_likes = ConfessionLike.objects.filter(confession=OuterRef('pk'), user=request.user)
    confessions = Confession.objects.select_related('user').annotate(
        like_count=Count('likes', distinct=True),
        comment_count=Count('comments', distinct=True),
        is_liked=Exists(user_confession_likes)
    ).order_by('-created_at')[:20]

    return render(request, 'feed/explore.html', {'confessions': confessions})


# --- Regular Post Views (Create, Delete) ---
# feed/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import PostForm

# ✨ 1. Import necessary libraries
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import sys

@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user

            # ✨ 2. Start Image Compression Logic
            image_field = form.cleaned_data.get('image')
            if image_field:
                # Check if the image size is greater than 2 MB (2 * 1024 * 1024 bytes)
                if image_field.size > 2 * 1024 * 1024:
                    
                    # Target size is 1 MB
                    target_size_kb = 1024 
                    
                    # Open the image using Pillow
                    img = Image.open(image_field)
                    
                    # If the image is RGBA (has transparency), convert it to RGB
                    if img.mode == 'RGBA':
                        img = img.convert('RGB')
                        
                    output_buffer = BytesIO()
                    
                    # Start with a high quality and decrease it until the file size is below the target
                    quality = 85 # Initial quality
                    
                    # This loop will try to save the image with decreasing quality
                    # to get the file size under 1MB.
                    while quality > 10:
                        output_buffer.seek(0) # Rewind buffer
                        img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
                        if output_buffer.tell() / 1024 < target_size_kb:
                            break
                        quality -= 5 # Decrease quality by 5

                    # The buffer now contains the compressed image data.
                    # We create a new Django ContentFile from the buffer's content.
                    compressed_image = ContentFile(output_buffer.getvalue())
                    
                    # We need to save this new file to the post's image field.
                    # We must provide a name for the new file. We can reuse the old one.
                    post.image.save(image_field.name, compressed_image, save=False)

            # ✨ 3. End of Image Compression Logic

            post.save() # Now save the post instance with the (potentially compressed) image
            messages.success(request, "Post created successfully!")
            return redirect('feed:profile', user_id=request.user.id)
    else:
        form = PostForm()
    return render(request, 'feed/create_post.html', {'form': form})

@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.user == post.user:
        post.delete()
        messages.success(request, "Post deleted.")
    else:
        messages.error(request, "Permission denied.")
    return redirect('feed:profile', user_id=request.user.id)

@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    post_owner_id = comment.post.user.id
    if request.user == comment.user or request.user == comment.post.user:
        comment.delete()
        messages.success(request, "Comment deleted.")
    else:
        messages.error(request, "Permission denied.")
    return redirect('feed:profile', user_id=post_owner_id)


# --- AJAX / API Views for Posts ---

@login_required
def like_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        like, created = Like.objects.get_or_create(post=post, user=request.user)
        if not created:
            like.delete()
        return JsonResponse({'success': True, 'liked': created, 'likes_count': post.likes.count()})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


@login_required
def get_post_comments(request, post_id):
    """
    NEW VIEW: Fetches all comments for a given post for the comment modal.
    """
    post = get_object_or_404(Post, id=post_id)
    # Security check: Ensure user can view the post before showing comments
    is_mutual = Crush.objects.filter(sender=request.user, receiver=post.user, is_mutual=True).exists()
    if not post.is_public and request.user != post.user and not is_mutual:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    comments = post.comments.select_related('user').order_by('created_at')
    comments_data = [{
        'user': {
            'profile_picture_url': c.user.profile_picture.url if c.user.profile_picture else DEFAULT_AVATAR_URL,
            'username': c.user.username,
            'full_name': c.user.full_name or c.user.username
        },
        'content': c.content,
        'created_at': c.created_at.isoformat(),
    } for c in comments]
    
    return JsonResponse({'comments': comments_data})
1
@login_required
def add_comment(request, post_id):
    """
    Handles adding a new comment to a post via AJAX.
    CORRECTED to return JSON in a consistent format for the frontend.
    """
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        content = request.POST.get('content')
        if content:
            comment = Comment.objects.create(post=post, user=request.user, content=content)
            # Return JSON in the format the 'renderComment' JS function expects
            return JsonResponse({
                'success': True,
                'comment': {
                    'user': {
                        'profile_picture_url': comment.user.profile_picture.url if comment.user.profile_picture else DEFAULT_AVATAR_URL,
                        'username': comment.user.username,
                        'full_name': comment.user.full_name or comment.user.username
                    },
                    'content': comment.content,
                    'created_at': comment.created_at.isoformat(), # Use ISO format for new Date() in JS
                }
            })
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def get_post_data(request, post_id):
    """AJAX view to fetch details for a single post, with visibility checks."""
    post = get_object_or_404(Post, id=post_id)
    
    is_mutual = Crush.objects.filter(sender=request.user, receiver=post.user, is_mutual=True).exists()

    # IMPORTANT SECURITY CHECK
    if not (post.is_public or request.user == post.user or is_mutual):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)

    comments_data = [{
        'id': c.id,
        'username': c.user.username,
        'user_id': c.user.id,
        'user_image': c.user.profile_picture.url if c.user.profile_picture else DEFAULT_AVATAR_URL,
        'content': c.content,
        'time': timesince(c.created_at),
        'can_delete': request.user == c.user or request.user == post.user,
    } for c in post.comments.order_by('-created_at')]

    post_data = {
        'id': post.id,
        'image': post.image.url,
        'caption': post.caption,
        'time': timesince(post.created_at),
        'username': post.user.username,
        'user_id': post.user.id,
        'user_image': post.user.profile_picture.url if post.user.profile_picture else DEFAULT_AVATAR_URL,
        'liked': post.likes.filter(user=request.user).exists(),
        'likes_count': post.likes.count(),
        'comments': comments_data,
        'is_owner': request.user == post.user
    }
    return JsonResponse({'success': True, 'post': post_data})


# --- Crush & Friendship Views ---

@login_required
def crush_action(request, user_id):
    """
    Handles crush/uncrush actions from user cards.
    CORRECTED to use safer, more explicit logic and prevent 500 errors.
    """
    if request.method == 'POST':
        profile_user = get_object_or_404(User, id=user_id)
        current_user = request.user
        if profile_user == current_user:
            return JsonResponse({'status': 'error', 'message': 'Action on self not allowed.'}, status=403)

        action = request.POST.get('crush_action')

        if action == 'send_crush':
            crush, created = Crush.objects.get_or_create(sender=current_user, receiver=profile_user)
            # Check if it's now mutual and update both records if so
            if Crush.objects.filter(sender=profile_user, receiver=current_user).exists():
                Crush.objects.filter(Q(sender=current_user, receiver=profile_user) | Q(sender=profile_user, receiver=current_user)).update(is_mutual=True)
                Friendship.objects.get_or_create(user1=current_user, user2=profile_user)

        elif action == 'uncrush':
            # Remove the crush from the current user
            Crush.objects.filter(sender=current_user, receiver=profile_user).delete()
            # Find the other user's crush record (if it exists) and set is_mutual to False
            Crush.objects.filter(sender=profile_user, receiver=current_user).update(is_mutual=False)
            # Delete the friendship
            Friendship.objects.filter(
                (Q(user1=current_user) & Q(user2=profile_user)) |
                (Q(user1=profile_user) & Q(user2=current_user))
            ).delete()


        # Re-calculate the status after the action
        sent = Crush.objects.filter(sender=current_user, receiver=profile_user).exists()
        received = Crush.objects.filter(sender=profile_user, receiver=current_user).exists()
        new_status = "mutual" if sent and received else "sent" if sent else "received" if received else "none"

        return JsonResponse({
            'status': 'ok', 'new_crush_status': new_status,
            'stats': {
                'hearts_sent': Crush.objects.filter(sender=request.user, is_mutual=False).count(),
                'hearts_received': Crush.objects.filter(receiver=request.user, is_mutual=False).count(),
                'friends': Crush.objects.filter(sender=request.user, is_mutual=True).count(),
            }
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)



@login_required
def crush_action_profile(request, user_id):
    """
    Handles crush actions for the profile page via AJAX.
    Returns a JSON response with the new crush status.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

    profile_user = get_object_or_404(User, id=user_id)
    current_user = request.user

    if profile_user == current_user:
        return JsonResponse({'status': 'error', 'message': 'You cannot perform this action on yourself.'}, status=403)

    action = request.POST.get('crush_action')
    if action not in ['send_crush', 'accept_crush', 'uncrush']:
        return JsonResponse({'status': 'error', 'message': 'Invalid crush action'}, status=400)

    # --- Crush Logic (This remains the same) ---
    if action == 'send_crush':
        crush, created = Crush.objects.get_or_create(sender=current_user, receiver=profile_user)
        if created:
            received_crush_obj = Crush.objects.filter(sender=profile_user, receiver=current_user).first()
            if received_crush_obj:
                crush.is_mutual = True; received_crush_obj.is_mutual = True
                crush.save(); received_crush_obj.save()
    elif action == 'accept_crush':
        received_crush_obj = Crush.objects.filter(sender=profile_user, receiver=current_user).first()
        if received_crush_obj:
            sent_crush_obj, created = Crush.objects.get_or_create(sender=current_user, receiver=profile_user)
            sent_crush_obj.is_mutual = True; received_crush_obj.is_mutual = True
            sent_crush_obj.save(); received_crush_obj.save()
    elif action == 'uncrush':
        crush_to_delete = Crush.objects.filter(sender=current_user, receiver=profile_user).first()
        if crush_to_delete:
            crush_to_delete.delete()
        received_crush_obj = Crush.objects.filter(sender=profile_user, receiver=current_user).first()
        if received_crush_obj:
            received_crush_obj.is_mutual = False
            received_crush_obj.save()

    # --- Re-fetch current status ---
    is_mutual = Crush.objects.filter(sender=request.user, receiver=profile_user, is_mutual=True).exists()
    sent_crush = Crush.objects.filter(sender=request.user, receiver=profile_user).exists()
    received_crush = Crush.objects.filter(sender=profile_user, receiver=request.user).exists()

    # --- Return the new status as JSON ---
    return JsonResponse({
        'status': 'ok',
        'is_mutual': is_mutual,
        'sent_crush': sent_crush,
        'received_crush': received_crush,
    })

@login_required
def hearts_sent(request):
    sent_crushes = Crush.objects.filter(sender=request.user, is_mutual=False).select_related('receiver')
    return render(request, 'feed/hearts_sent.html', {'sent_hearts': sent_crushes})

@login_required
def hearts_received(request):
    received_crushes = Crush.objects.filter(receiver=request.user, is_mutual=False).select_related('sender')
    return render(request, 'feed/hearts_received.html', {'received_hearts': received_crushes})



def friends_list(request):
    friend_ids = Crush.objects.filter(sender=request.user, is_mutual=True).values_list('receiver_id', flat=True)
    # This line is key: 'friends' is a QuerySet of User objects.
    friends = User.objects.filter(id__in=friend_ids) 
    return render(request, 'feed/friends.html', {'friends': friends})

# --- Confession Views ---

@login_required
def create_confession(request):
    if request.method == 'POST':
        form = ConfessionForm(request.POST)
        if form.is_valid():
            confession = form.save(commit=False)
            if not form.cleaned_data.get('is_anonymous'):
                confession.user = request.user
            confession.save()
            messages.success(request, "Confession posted!")
            return redirect('feed:explore')
    else:
        form = ConfessionForm(initial={'is_anonymous': True})
    return render(request, 'feed/confession.html', {'form': form})

@login_required
def like_confession(request):
    if request.method == 'POST':
        confession = get_object_or_404(Confession, id=request.POST.get('confession_id'))
        like, created = ConfessionLike.objects.get_or_create(user=request.user, confession=confession)
        if not created:
            like.delete()
        return JsonResponse({'liked': created, 'like_count': confession.likes.count()})
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def add_confession_comment(request):
    if request.method == 'POST':
        confession = get_object_or_404(Confession, id=request.POST.get('confession_id'))
        content = request.POST.get('content', '').strip()
        if content:
            ConfessionComment.objects.create(
                confession=confession,
                user=request.user,
                content=content,
                is_anonymous=request.POST.get('is_anonymous') == 'true'
            )
            return JsonResponse({'success': True, 'comment_count': confession.comments.count()})
    return JsonResponse({'error': 'Invalid request'}, status=400)


# --- Other API/AJAX Views ---

@login_required
def get_home_updates(request):
    """AJAX endpoint to periodically update stats on the home page."""
    return JsonResponse({'stats': {
        'hearts_sent': Crush.objects.filter(sender=request.user, is_mutual=False).count(),
        'hearts_received': Crush.objects.filter(receiver=request.user, is_mutual=False).count(),
        'friends': Crush.objects.filter(sender=request.user, is_mutual=True).count(),
        'profile_views': ProfileView.objects.filter(viewed=request.user).values('viewer').distinct().count(),
    }})

@login_required
def load_users_api(request):
    """Paginates and loads users for different categories on the home page."""
    category = request.GET.get('category')
    page_number = request.GET.get('page', 1)
    
    queryset = User.objects.exclude(id=request.user.id)
    if category == 'recently_joined':
        all_users = queryset.order_by('-date_joined')
    # Add other category logic here if needed, e.g., 'trending'
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid category'}, status=400)

    paginator = Paginator(all_users, 10)
    page_obj = paginator.get_page(page_number)
    
    users_data = []
    # This part can be slow if you have many users.
    # A more advanced solution might annotate the crush status directly in the query.
    for user in page_obj.object_list:
        users_data.append({
            'id': user.id,
            'full_name': user.full_name,
            'profile_picture_url': user.profile_picture.url if user.profile_picture else DEFAULT_AVATAR_URL,
            'profile_url': reverse('feed:profile', args=[user.id]),
        })

    return JsonResponse({'status': 'ok', 'users': users_data, 'has_next': page_obj.has_next()})

@login_required
def search_users_api(request):
    """API for real-time user search."""
    query = request.GET.get('q', '').strip()
    users_data = []
    if query:
        users = User.objects.filter(
            Q(username__icontains=query) | Q(full_name__icontains=query)
        ).exclude(id=request.user.id)[:10]
        for user in users:
            users_data.append({
                'id': user.id, 'username': user.username, 'full_name': user.full_name or user.username,
                'profile_picture_url': user.profile_picture.url if user.profile_picture else DEFAULT_AVATAR_URL,
            })
    return JsonResponse({'users': users_data})

@login_required
def get_confession_details_api(request, confession_id):
    """API to get details for a single confession and its comments."""
    confession = get_object_or_404(Confession, pk=confession_id)
    
    comments = confession.comments.select_related('user').order_by('created_at')
    comment_list = []
    for comment in comments:
        # Get the correct profile picture URL for each comment
        if comment.is_anonymous or not comment.user:
            profile_pic = ANONYMOUS_AVATAR_URL
        else:
            profile_pic = comment.user.profile_picture.url if comment.user.profile_picture else DEFAULT_AVATAR_URL

        comment_list.append({
            'user': "Anonymous" if comment.is_anonymous or not comment.user else comment.user.username,
            'profile_picture_url': profile_pic,
            'content': comment.content,
            'time_since': timesince(comment.created_at) + " ago",
        })
        
    author_name = "Anonymous" if confession.is_anonymous or not confession.user else confession.user.username
    
    # NEW: Get the correct profile picture URL for the confession's author
    if confession.is_anonymous or not confession.user:
        author_avatar_url = ANONYMOUS_AVATAR_URL
    else:
        author_avatar_url = confession.user.profile_picture.url if confession.user.profile_picture else DEFAULT_AVATAR_URL

    return JsonResponse({
        'success': True,
        'confession': {
            'content': confession.content,
            'author': author_name,
            'author_avatar': author_avatar_url  # This is the new key
        },
        'comments': comment_list
    })

# The following two views are referenced in your urls.py but seem redundant
# with get_confession_details_api. I've included them to prevent errors.
@login_required
def confession_comments_api(request, confession_id):
    return get_confession_details_api(request, confession_id)

@login_required
def get_confession_comments(request, confession_id):
    return get_confession_details_api(request, confession_id)


# Add these implementations to your views.py file

@login_required
def lazy_load_section(request, section_type):
    """
    Lazy loads different user sections for the home page carousels.
    Handles: recently-joined, same-year, same-department, same-college
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    current_user = request.user
    users_data = []
    
    try:
        if section_type == 'recently-joined':
            # Users who joined in the last 7 days
            users = User.objects.exclude(id=current_user.id).filter(
                date_joined__gte=timezone.now() - timezone.timedelta(days=7)
            ).order_by('-date_joined')[:10]
            
        elif section_type == 'same-year':
            # Users from the same academic year
            try:
                user_year = current_user.questionnaire.year
                questionnaires = UserQuestionnaire.objects.filter(
                    year=user_year
                ).exclude(user=current_user).select_related('user')[:10]
                users = [q.user for q in questionnaires]
            except (UserQuestionnaire.DoesNotExist, AttributeError):
                users = []
                
        elif section_type == 'same-department':
            # Users from the same department
            if current_user.department:
                users = User.objects.exclude(id=current_user.id).filter(
                    department=current_user.department
                )[:10]
            else:
                users = []
                
        elif section_type == 'same-college':
            # Users from the same college
            if current_user.college:
                users = User.objects.exclude(id=current_user.id).filter(
                    college=current_user.college
                )[:10]
            else:
                users = []
        else:
            return JsonResponse({'error': 'Invalid section type'}, status=400)
        
        # Helper function to get crush status
        def get_crush_status(person):
            sent = Crush.objects.filter(sender=current_user, receiver=person).exists()
            received = Crush.objects.filter(sender=person, receiver=current_user).exists()
            if sent and received: 
                return "mutual"
            if sent: 
                return "sent"
            if received: 
                return "received"
            return "none"
        
        # Format user data for frontend
        for user in users:
            users_data.append({
                'id': user.id,
                'full_name': user.full_name or user.username,
                'department': getattr(user, 'department', None) or 'N/A',
                'college': getattr(user, 'college', None) or 'N/A',
                'profile_picture': user.profile_picture.url if user.profile_picture else DEFAULT_AVATAR_URL,
                'crush_status': get_crush_status(user),
            })
            
        return JsonResponse({
            'success': True,
            'users': users_data
        })
        
    except Exception as e:
        return JsonResponse({
            'error': f'Failed to load {section_type} users: {str(e)}'
        }, status=500)

@login_required  
def lazy_load_posts(request):
    """
    Lazy loads paginated posts for the public feed with comprehensive error handling.
    """
    print(f"DEBUG: lazy_load_posts called with method: {request.method}")
    print(f"DEBUG: GET parameters: {request.GET}")
    
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        page_number = int(request.GET.get('page', 1))
        posts_per_page = 5
        
        print(f"DEBUG: Loading page {page_number}")
        
        # Check if we have any posts at all
        total_posts = Post.objects.count()
        public_posts_count = Post.objects.filter(is_public=True).count()
        
        print(f"DEBUG: Total posts: {total_posts}, Public posts: {public_posts_count}")
        
        # Get public posts with like status for current user
        user_post_likes = Like.objects.filter(post=OuterRef('pk'), user=request.user)
        all_public_posts = Post.objects.filter(is_public=True).select_related('user').annotate(
            is_liked=Exists(user_post_likes)
        ).order_by('-created_at')
        
        print(f"DEBUG: Query executed, found {all_public_posts.count()} public posts")
        
        # If no posts, return empty result
        if not all_public_posts.exists():
            print("DEBUG: No public posts found")
            return JsonResponse({
                'success': True,
                'posts': [],
                'has_more': False,
                'debug_info': {
                    'total_posts': total_posts,
                    'public_posts': public_posts_count,
                    'page_requested': page_number
                }
            })
        
        # Paginate
        paginator = Paginator(all_public_posts, posts_per_page)
        
        try:
            posts_page = paginator.page(page_number)
            print(f"DEBUG: Page {page_number} has {len(posts_page)} posts")
        except Exception as page_error:
            print(f"DEBUG: Page error: {page_error}")
            return JsonResponse({
                'success': True,
                'posts': [],
                'has_more': False,
                'error': f'Page {page_number} not found'
            })
        
        # Format posts data for frontend
        posts_data = []
        for post in posts_page:
            try:
                post_data = {
                    'id': post.id,
                    'image': post.image.url if post.image else '',
                    'caption': post.caption or '',
                    'is_liked': getattr(post, 'is_liked', False),
                    'user': {
                        'id': post.user.id,
                        'username': post.user.username,
                        'full_name': post.user.full_name or post.user.username,
                        'profile_picture': post.user.profile_picture.url if post.user.profile_picture else DEFAULT_AVATAR_URL,
                    },
                    'created_at': post.created_at.isoformat(),
                }
                posts_data.append(post_data)
                print(f"DEBUG: Added post {post.id} to data")
            except Exception as post_error:
                print(f"DEBUG: Error processing post {post.id}: {post_error}")
                continue
        
        result = {
            'success': True,
            'posts': posts_data,
            'has_more': posts_page.has_next(),
            'debug_info': {
                'page': page_number,
                'posts_in_page': len(posts_data),
                'total_pages': paginator.num_pages,
                'has_next': posts_page.has_next()
            }
        }
        
        print(f"DEBUG: Returning {len(posts_data)} posts, has_more: {posts_page.has_next()}")
        return JsonResponse(result)
        
    except Exception as e:
        print(f"DEBUG: Exception in lazy_load_posts: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': f'Failed to load posts: {str(e)}',
            'success': False
        }, status=500)
    

@login_required
def debug_posts(request):
    """Debug view to check posts and data"""
    try:
        # Check total posts
        total_posts = Post.objects.count()
        public_posts = Post.objects.filter(is_public=True).count()
        user_posts = Post.objects.filter(user=request.user).count()
        
        # Get some sample posts
        sample_posts = Post.objects.filter(is_public=True)[:3]
        
        debug_data = {
            'total_posts': total_posts,
            'public_posts': public_posts,
            'user_posts': user_posts,
            'sample_posts': [
                {
                    'id': p.id,
                    'user': p.user.username,
                    'caption': p.caption[:50] if p.caption else 'No caption',
                    'has_image': bool(p.image),
                    'is_public': p.is_public,
                    'created_at': str(p.created_at)
                } for p in sample_posts
            ]
        }
        
        return JsonResponse(debug_data)
    except Exception as e:
        return JsonResponse({'error': str(e)})
    

# Add these debug views to your views.py to diagnose the issue

@login_required
def debug_comprehensive_posts(request):
    """Comprehensive debug view to check all aspects of post loading"""
    try:
        from django.db import connection
        
        # Basic counts
        total_posts = Post.objects.count()
        public_posts = Post.objects.filter(is_public=True).count()
        user_posts = Post.objects.filter(user=request.user).count()
        
        # Check if Post model has the expected fields
        post_fields = [field.name for field in Post._meta.get_fields()]
        
        # Test the exact query used in lazy_load_posts
        user_post_likes = Like.objects.filter(post=OuterRef('pk'), user=request.user)
        all_public_posts = Post.objects.filter(is_public=True).select_related('user').annotate(
            is_liked=Exists(user_post_likes)
        ).order_by('-created_at')
        
        # Get first few posts with full details
        sample_posts = []
        for post in all_public_posts[:5]:
            try:
                sample_posts.append({
                    'id': post.id,
                    'user_id': post.user.id,
                    'username': post.user.username,
                    'full_name': getattr(post.user, 'full_name', 'No full_name attr'),
                    'caption': post.caption[:100] if post.caption else 'No caption',
                    'has_image': bool(post.image),
                    'image_url': post.image.url if post.image else 'No image',
                    'is_public': post.is_public,
                    'is_liked': getattr(post, 'is_liked', 'No is_liked attr'),
                    'created_at': str(post.created_at),
                    'user_has_profile_pic': bool(post.user.profile_picture),
                    'profile_pic_url': post.user.profile_picture.url if post.user.profile_picture else 'No profile pic'
                })
            except Exception as e:
                sample_posts.append({
                    'id': post.id,
                    'error': str(e)
                })
        
        # Check SQL queries
        queries = connection.queries[-5:] if connection.queries else []
        
        # Check Like model
        like_count = Like.objects.count()
        user_likes = Like.objects.filter(user=request.user).count()
        
        debug_data = {
            'success': True,
            'basic_stats': {
                'total_posts': total_posts,
                'public_posts': public_posts,
                'user_posts': user_posts,
                'like_count': like_count,
                'user_likes': user_likes,
            },
            'post_model_fields': post_fields,
            'sample_posts': sample_posts,
            'recent_queries': [q['sql'][:200] + '...' if len(q['sql']) > 200 else q['sql'] for q in queries],
            'user_info': {
                'id': request.user.id,
                'username': request.user.username,
                'is_authenticated': request.user.is_authenticated,
            }
        }
        
        return JsonResponse(debug_data, indent=2)
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@login_required
def test_lazy_load_posts(request):
    """Test the exact lazy_load_posts functionality with detailed logging"""
    try:
        # Simulate the lazy_load_posts function with more debugging
        page_number = int(request.GET.get('page', 1))
        posts_per_page = 5
        
        print(f"=== LAZY LOAD DEBUG START ===")
        print(f"User: {request.user.username} (ID: {request.user.id})")
        print(f"Page requested: {page_number}")
        
        # Step 1: Check basic counts
        total_posts = Post.objects.count()
        public_posts_count = Post.objects.filter(is_public=True).count()
        print(f"Total posts in DB: {total_posts}")
        print(f"Public posts in DB: {public_posts_count}")
        
        # Step 2: Try to get public posts without annotation first
        basic_public_posts = Post.objects.filter(is_public=True).select_related('user').order_by('-created_at')
        print(f"Basic public posts query count: {basic_public_posts.count()}")
        
        # Step 3: Add annotation
        user_post_likes = Like.objects.filter(post=OuterRef('pk'), user=request.user)
        annotated_posts = basic_public_posts.annotate(is_liked=Exists(user_post_likes))
        print(f"Annotated posts query count: {annotated_posts.count()}")
        
        # Step 4: Test pagination
        from django.core.paginator import Paginator
        paginator = Paginator(annotated_posts, posts_per_page)
        print(f"Paginator created - total pages: {paginator.num_pages}")
        
        try:
            posts_page = paginator.page(page_number)
            print(f"Page {page_number} loaded - has {len(posts_page)} posts")
        except Exception as page_error:
            print(f"Pagination error: {page_error}")
            return JsonResponse({
                'error': f'Pagination failed: {str(page_error)}',
                'debug_info': {
                    'total_posts': total_posts,
                    'public_posts': public_posts_count,
                    'total_pages': paginator.num_pages,
                    'page_requested': page_number
                }
            })
        
        # Step 5: Process posts
        posts_data = []
        for i, post in enumerate(posts_page):
            try:
                print(f"Processing post {i+1}: ID {post.id}")
                
                # Check user object
                user_data = {
                    'id': post.user.id,
                    'username': post.user.username,
                    'full_name': getattr(post.user, 'full_name', None) or post.user.username,
                }
                
                # Check profile picture
                if hasattr(post.user, 'profile_picture') and post.user.profile_picture:
                    user_data['profile_picture'] = post.user.profile_picture.url
                else:
                    user_data['profile_picture'] = '/static/images/default_avatar.png'  # Adjust this path
                
                post_data = {
                    'id': post.id,
                    'image': post.image.url if post.image else '',
                    'caption': post.caption or '',
                    'is_liked': getattr(post, 'is_liked', False),
                    'user': user_data,
                    'created_at': post.created_at.isoformat(),
                }
                
                posts_data.append(post_data)
                print(f"Successfully processed post {post.id}")
                
            except Exception as post_error:
                print(f"Error processing post {post.id}: {post_error}")
                posts_data.append({
                    'id': post.id,
                    'error': str(post_error),
                    'user': {'id': post.user.id, 'username': post.user.username}
                })
        
        print(f"=== LAZY LOAD DEBUG END ===")
        
        return JsonResponse({
            'success': True,
            'posts': posts_data,
            'has_more': posts_page.has_next(),
            'debug_info': {
                'page': page_number,
                'posts_in_page': len(posts_data),
                'total_pages': paginator.num_pages,
                'total_posts': total_posts,
                'public_posts': public_posts_count,
                'has_next': posts_page.has_next()
            }
        })
        
    except Exception as e:
        import traceback
        print(f"MAJOR ERROR in test_lazy_load_posts: {str(e)}")
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


# Also add this improved version of your lazy_load_posts with better error handling
@login_required  
def lazy_load_posts_improved(request):
    """
    Improved version of lazy_load_posts with comprehensive error handling
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        page_number = int(request.GET.get('page', 1))
        posts_per_page = 5
        
        # Check basic counts first
        total_posts = Post.objects.count()
        if total_posts == 0:
            return JsonResponse({
                'success': True,
                'posts': [],
                'has_more': False,
                'message': 'No posts in database'
            })
        
        public_posts_count = Post.objects.filter(is_public=True).count()
        if public_posts_count == 0:
            return JsonResponse({
                'success': True,
                'posts': [],
                'has_more': False,
                'message': 'No public posts in database'
            })
        
        # Build query step by step
        base_query = Post.objects.filter(is_public=True).select_related('user')
        
        # Check if Like model exists and is working
        try:
            like_test = Like.objects.count()
            user_post_likes = Like.objects.filter(post=OuterRef('pk'), user=request.user)
            all_public_posts = base_query.annotate(is_liked=Exists(user_post_likes))
        except Exception as like_error:
            print(f"Like annotation failed: {like_error}")
            # Fallback without like annotation
            all_public_posts = base_query.extra(select={'is_liked': 'FALSE'})
        
        all_public_posts = all_public_posts.order_by('-created_at')
        
        # Paginate
        from django.core.paginator import Paginator
        paginator = Paginator(all_public_posts, posts_per_page)
        
        if page_number > paginator.num_pages:
            return JsonResponse({
                'success': True,
                'posts': [],
                'has_more': False,
                'message': f'Page {page_number} does not exist (max: {paginator.num_pages})'
            })
        
        posts_page = paginator.page(page_number)
        
        # Format posts data with error handling for each post
        posts_data = []
        for post in posts_page:
            try:
                # Safely get user data
                user_full_name = None
                if hasattr(post.user, 'full_name'):
                    user_full_name = post.user.full_name
                
                # Safely get profile picture
                profile_picture_url = '/static/images/default_avatar.png'  # Set your default
                if hasattr(post.user, 'profile_picture') and post.user.profile_picture:
                    try:
                        profile_picture_url = post.user.profile_picture.url
                    except:
                        pass  # Use default
                
                # Safely get image URL
                image_url = ''
                if post.image:
                    try:
                        image_url = post.image.url
                    except:
                        pass  # No image
                
                post_data = {
                    'id': post.id,
                    'image': image_url,
                    'caption': post.caption or '',
                    'is_liked': getattr(post, 'is_liked', False),
                    'user': {
                        'id': post.user.id,
                        'username': post.user.username,
                        'full_name': user_full_name or post.user.username,
                        'profile_picture': profile_picture_url,
                    },
                    'created_at': post.created_at.isoformat() if hasattr(post.created_at, 'isoformat') else str(post.created_at),
                }
                posts_data.append(post_data)
                
            except Exception as post_error:
                print(f"Error processing post {post.id}: {post_error}")
                # Skip this post but continue with others
                continue
        
        return JsonResponse({
            'success': True,
            'posts': posts_data,
            'has_more': posts_page.has_next(),
            'page_info': {
                'current_page': page_number,
                'total_pages': paginator.num_pages,
                'posts_in_page': len(posts_data),
                'total_public_posts': public_posts_count
            }
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in lazy_load_posts_improved: {error_trace}")
        
        return JsonResponse({
            'success': False,
            'error': f'Failed to load posts: {str(e)}',
            'traceback': error_trace
        }, status=500)