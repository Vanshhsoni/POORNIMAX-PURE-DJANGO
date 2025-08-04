from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.db import IntegrityError
from accounts.models import User, UserQuestionnaire
from feed.models import Confession , ConfessionLike , ConfessionComment , Comment
from django.shortcuts import get_object_or_404

# confession = get_object_or_404(Confession, pk=confession_id)


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from accounts.models import Crush, Friendship
from django.utils.timesince import timesince

from django.db import models
from datetime import datetime 


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils.timesince import timesince
from .forms import *
from .models import *
from accounts.models import *

@login_required
def profile(request, user_id):
    profile_user = get_object_or_404(User, id=user_id)
    if request.user != profile_user:
        # Create profile view record
        ProfileView.objects.create(viewer=request.user, viewed=profile_user)
        
    # Check crush status without filtering by is_mutual
    sent_crush = Crush.objects.filter(sender=request.user, receiver=profile_user).exists()
    received_crush = Crush.objects.filter(sender=profile_user, receiver=request.user).exists()
    
    # Check if both users have sent crushes to each other and at least one is marked mutual
    is_mutual = False
    if sent_crush and received_crush:
        sent_crush_obj = Crush.objects.get(sender=request.user, receiver=profile_user)
        received_crush_obj = Crush.objects.get(sender=profile_user, receiver=request.user)
        is_mutual = sent_crush_obj.is_mutual or received_crush_obj.is_mutual
    
    # Get user's posts
    posts = Post.objects.filter(user=profile_user).order_by('-created_at')
    
    # Get the latest post
    latest_post = posts.first()
    
    # Add like and comment counts to posts
    for post in posts:
        post.likes_count = Like.objects.filter(post=post).count()
        post.comments_count = Comment.objects.filter(post=post).count()
    
    # Calculate compatibility score when viewing another user's profile
    compatibility_score = None
    if request.user != profile_user:
        try:
            compatibility_score = calculate_compatibility(request.user, profile_user)
        except UserQuestionnaire.DoesNotExist:
            # If either user hasn't completed the questionnaire
            compatibility_score = None
    
    context = {
        'profile_user': profile_user,
        'sent_crush': sent_crush,
        'received_crush': received_crush,
        'is_mutual': is_mutual,
        'posts': posts,
        'latest_post': latest_post,
        'compatibility_score': compatibility_score,
        'user_year': getattr(profile_user.questionnaire, 'year', None)
    }
    return render(request, 'feed/profile.html', context)


# accounts/utils.py (or wherever you prefer to keep this function)


def _calculate_jaccard_similarity(set1, set2):
    """Helper function to calculate similarity for lists like hobbies."""
    if not set1 and not set2:
        return 1.0  # Both have no hobbies, which is a form of similarity
    if not set1 or not set2:
        return 0.0  # One has hobbies, the other doesn't

    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union != 0 else 0

def calculate_compatibility(user1, user2):
    """
    Calculates a compatibility score between two users based on their new questionnaire answers.
    The score is weighted across three main categories.
    """
    try:
        q1 = UserQuestionnaire.objects.get(user=user1)
        q2 = UserQuestionnaire.objects.get(user=user2)
    except UserQuestionnaire.DoesNotExist:
        return None # One or both users haven't answered the questionnaire

    # --- Define Weights (must sum to 100) ---
    INTENT_WEIGHT = 50  # Relationship status, what they're looking for, year
    PERSONALITY_WEIGHT = 30  # Personality and communication style
    HOBBIES_WEIGHT = 20  # Shared interests

    total_score = 0

    # ====================================================================
    # --- 1. Intent & Life Stage (Weight: 50%) ---
    # ====================================================================
    intent_score = 0
    intent_max_score = 4 # Max possible points in this category

    # Score for relationship_status (Max: 2 points)
    if q1.relationship_status == q2.relationship_status:
        intent_score += 2
    elif {q1.relationship_status, q2.relationship_status} <= {'Single', 'Focusing on me'}:
        # If one is 'Single' and other is 'Focusing on me', they are still compatible
        intent_score += 1

    # Score for looking_for (Max: 1 point)
    if q1.looking_for == q2.looking_for:
        intent_score += 1
    # Being open is compatible with someone looking for friends
    elif 'New friends' in {q1.looking_for, q2.looking_for} and 'Not sure yet' in {q1.looking_for, q2.looking_for}:
        intent_score += 0.5
        
    # Score for year (Max: 1 point)
    if q1.year == q2.year:
        intent_score += 1
        
    total_score += (intent_score / intent_max_score) * INTENT_WEIGHT

    # ====================================================================
    # --- 2. Personality & Communication (Weight: 30%) ---
    # ====================================================================
    personality_score = 0
    personality_max_score = 4 # Max possible points in this category

    # Score for personality type (Max: 2 points)
    if q1.personality == q2.personality:
        personality_score += 2
    elif 'A mix of both' in {q1.personality, q2.personality}:
        # 'A mix of both' is highly compatible with others
        personality_score += 1.5
    elif {q1.personality, q2.personality} == {'Introvert', 'Extrovert'}:
        # Complementary pairing
        personality_score += 0.5

    # Score for communication_style (Max: 2 points)
    if q1.communication_style == q2.communication_style:
        personality_score += 2
    elif 'A bit of everything' in {q1.communication_style, q2.communication_style}:
        # 'A bit of everything' is highly compatible
        personality_score += 1.5

    total_score += (personality_score / personality_max_score) * PERSONALITY_WEIGHT
    
    # ====================================================================
    # --- 3. Hobbies & Interests (Weight: 20%) ---
    # ====================================================================
    hobbies1 = set(q1.hobbies_interests.split(',')) if q1.hobbies_interests else set()
    hobbies2 = set(q2.hobbies_interests.split(',')) if q2.hobbies_interests else set()

    # Jaccard similarity score is already between 0 and 1
    hobby_similarity = _calculate_jaccard_similarity(hobbies1, hobbies2)
    total_score += hobby_similarity * HOBBIES_WEIGHT
    
    # ====================================================================
    # --- Final Calculation ---
    # ====================================================================
    
    # Clamp the score to a realistic range (e.g., 19% to 99%)
    final_score = max(19, min(99, total_score))

    return round(final_score)

@login_required
def all_users(request):
    logged_in_user = request.user
    
    compatibility_scores = []
    other_users = User.objects.exclude(id=logged_in_user.id)

    for user in other_users:
        try:
            compatibility_score = calculate_compatibility(logged_in_user, user)
            if compatibility_score is not None:
                compatibility_scores.append((user, compatibility_score))
        except UserQuestionnaire.DoesNotExist:
            continue

    # Sort the compatibility scores in descending order
    compatibility_scores.sort(key=lambda x: x[1], reverse=True)

    return render(request, 'feed/all.html', {
        'compatibility_scores': compatibility_scores,
    })


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta


from accounts.models import Crush, Friendship

@login_required
def home(request):
    current_user = request.user
    all_users = User.objects.exclude(id=current_user.id)
    
    # Count unique viewers instead of total views
    profile_views = ProfileView.objects.filter(viewed=current_user).values('viewer').distinct().count()
    
    def get_crush_status(person):
        sent = Crush.objects.filter(sender=current_user, receiver=person).first()
        received = Crush.objects.filter(sender=person, receiver=current_user).first()
        if sent and received and sent.is_mutual and received.is_mutual:
            return "mutual"
        elif sent:
            return "sent"
        elif received:
            return "received"
        return "none"

    # Recently joined
    recently_joined = all_users.filter(date_joined__gte=timezone.now() - timedelta(days=7))[:10]

    same_year = []
    try:
        user_year = current_user.questionnaire.year
        same_year_questionnaires = UserQuestionnaire.objects.filter(year=user_year).exclude(user=current_user)
        same_year = [uq.user for uq in same_year_questionnaires][:10]
    except UserQuestionnaire.DoesNotExist:
        pass

    same_department = all_users.filter(department=current_user.department)[:10]
    same_college = all_users.filter(college=current_user.college)[:10]

    # Crush stats
    hearts_sent = Crush.objects.filter(sender=current_user, is_mutual=False).count()
    hearts_received = Crush.objects.filter(receiver=current_user, is_mutual=False).count()
    
    # Only count mutual crushes as friends
    friends = Crush.objects.filter(
        (models.Q(sender=current_user) & models.Q(receiver__in=all_users) & models.Q(is_mutual=True)) |
        (models.Q(receiver=current_user) & models.Q(sender__in=all_users) & models.Q(is_mutual=True))
    ).count()
    
    # Since each mutual crush is counted twice (once in each direction), divide by 2
    friends = friends // 2

    # Add crush status mapping for each group
    def annotate_users_with_crush(users):
        return [
            {
                'user': person,
                'crush_status': get_crush_status(person)
            } for person in users
        ]

    context = {
        'profile_views': profile_views,
        'recently_joined': annotate_users_with_crush(recently_joined),
        'same_year': annotate_users_with_crush(same_year),
        'same_department': annotate_users_with_crush(same_department),
        'same_college': annotate_users_with_crush(same_college),
        'hearts_sent': hearts_sent,
        'hearts_received': hearts_received,
        'friends': friends
    }

    return render(request, 'feed/home.html', context)

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from django.contrib import messages





from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from accounts.models import Crush, Friendship  # Import your Crush and Friendship models
from django.contrib.auth import get_user_model

User = get_user_model()

# In feed/views.py

@login_required
def crush_action(request, user_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

    profile_user = get_object_or_404(User, id=user_id)
    current_user = request.user

    if profile_user == current_user:
        return JsonResponse({'status': 'error', 'message': 'You cannot send a crush to yourself.'}, status=403)

    action = request.POST.get('crush_action')

    # --- Your existing logic for send_crush, accept_crush, and uncrush ---
    # (The logic inside these if/elif blocks remains the same)
    if action == 'send_crush':
        # Check if crush already exists
        existing_crush = Crush.objects.filter(sender=request.user, receiver=profile_user).first()
        
        if not existing_crush:
            # Create new crush
            crush = Crush.objects.create(sender=request.user, receiver=profile_user)
            # Check if there's a mutual crush and handle friendship creation
            crush.check_mutual_and_create_friendship()
    
    elif action == 'uncrush':
        # Remove the crush from sender to receiver
        crush_sent = Crush.objects.filter(sender=request.user, receiver=profile_user).first()
        if crush_sent:
            crush_sent.delete()
            
            # If there was a mutual crush, set the reverse crush to not mutual
            crush_received = Crush.objects.filter(sender=profile_user, receiver=request.user).first()
            if crush_received:
                crush_received.is_mutual = False
                crush_received.save()
    # (Include your 'accept_crush' logic here if you use it on this page)
    # --- End of existing logic ---


    # --- New section to calculate updated stats and return JSON ---
    
    # 1. Recalculate the crush status for the specific user
    def get_crush_status(person):
        sent = Crush.objects.filter(sender=current_user, receiver=person).first()
        received = Crush.objects.filter(sender=person, receiver=current_user).first()
        if sent and received and sent.is_mutual and received.is_mutual:
            return "mutual"
        elif sent:
            return "sent"
        elif received:
            return "received"
        return "none"

    new_crush_status = get_crush_status(profile_user)

    # 2. Recalculate the summary stats for the current user
    hearts_sent_count = Crush.objects.filter(sender=current_user, is_mutual=False).count()
    hearts_received_count = Crush.objects.filter(receiver=current_user, is_mutual=False).count()
    
    # Calculate friends count (mutual crushes)
    mutual_crush_ids = Crush.objects.filter(sender=current_user, is_mutual=True).values_list('receiver_id', flat=True)
    friends_count = User.objects.filter(id__in=mutual_crush_ids).count()

    # 3. Return all the updated data as a JSON response
    return JsonResponse({
        'status': 'ok',
        'message': 'Action successful',
        'new_crush_status': new_crush_status,
        'stats': {
            'hearts_sent': hearts_sent_count,
            'hearts_received': hearts_received_count,
            'friends': friends_count,
        }
    })
    

# In feed/views.py

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
# ... your other imports

# Add this new function to your views file
@login_required
def get_home_updates(request):
    current_user = request.user
    
    # This view does very little work. It's fast and efficient.
    stats_data = {
        'hearts_sent': Crush.objects.filter(sender=current_user, is_mutual=False).count(),
        'hearts_received': Crush.objects.filter(receiver=current_user, is_mutual=False).count(),
        'friends': Crush.objects.filter(sender=current_user, is_mutual=True).count(),
        'profile_views': ProfileView.objects.filter(viewed=current_user).values('viewer').distinct().count()
    }
    
    return JsonResponse({'stats': stats_data})
# Add this to feed/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import *
from .models import *

@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            post.save()
            messages.success(request, "Post created successfully!")
            return redirect('feed:profile', user_id=request.user.id)
    else:
        form = PostForm()
    
    return render(request, 'feed/create_post.html', {'form': form})

# Add these to feed/views.py
from .models import Confession, ConfessionLike

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Post, Like, Comment
from django.utils.timesince import timesince
# ... other necessary imports

@login_required
def like_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        like, created = Like.objects.get_or_create(post=post, user=request.user)

        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        
        return JsonResponse({
            'success': True,
            'liked': liked,
            'likes_count': post.likes.count()
        })
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def add_comment(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        content = request.POST.get('content')
        if content:
            comment = Comment.objects.create(
                post=post,
                user=request.user,
                content=content
            )
            return JsonResponse({
                'success': True,
                'comment': {
                    'user_image': comment.user.profile_picture.url,
                    'username': comment.user.username,
                    'content': comment.content,
                    'time': 'just now'
                },
                'comments_count': post.comments.count()
            })
    return JsonResponse({'success': False, 'error': 'Invalid request'})

# Your get_post_data and other views remain the same.


@login_required
def delete_comment(request, comment_id):
    if request.method == 'POST':
        comment = get_object_or_404(Comment, id=comment_id)
        post_user_id = comment.post.user.id
        
        # Only comment owner or post owner can delete
        if request.user == comment.user or request.user == comment.post.user:
            comment.delete()
            # Redirect to the profile page of the post owner
            return redirect('feed:profile', user_id=post_user_id)
        
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def delete_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        post_user_id = post.user.id
        
        # Only post owner can delete their post
        if request.user == post.user:
            post.delete()
            # Redirect to the profile page of the post owner
            return redirect('feed:profile', user_id=post_user_id)
        
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def get_post_data(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    # Check if user can view this post
    profile_user = post.user
    sent_crush = Crush.objects.filter(sender=request.user, receiver=profile_user).exists()
    received_crush = Crush.objects.filter(sender=profile_user, receiver=request.user).exists()
    
    is_mutual = False
    if sent_crush and received_crush:
        sent_crush_obj = Crush.objects.get(sender=request.user, receiver=profile_user)
        received_crush_obj = Crush.objects.get(sender=profile_user, receiver=request.user)
        is_mutual = sent_crush_obj.is_mutual or received_crush_obj.is_mutual
    
    # Check if user can see this post
    if not (request.user == profile_user or is_mutual):
        return JsonResponse({'success': False, 'error': 'Not authorized'})
    
    # Get comments
    comments = []
    for comment in Comment.objects.filter(post=post).order_by('-created_at'):
        comments.append({
            'id': comment.id,
            'username': comment.user.username,
            'user_id': comment.user.id,
            'user_image': comment.user.profile_picture.url,
            'content': comment.content,
            'time': timesince(comment.created_at),
            'is_owner': comment.user == request.user,
            'can_delete': comment.user == request.user or post.user == request.user
        })
    
    # Check if user has liked this post
    liked = Like.objects.filter(post=post, user=request.user).exists()
    likes_count = Like.objects.filter(post=post).count()
    
    return JsonResponse({
        'success': True,
        'post': {
            'id': post.id,
            'image': post.image.url,
            'caption': post.caption,
            'time': timesince(post.created_at),
            'username': post.user.username,
            'user_id': post.user.id,
            'user_image': post.user.profile_picture.url,
            'liked': liked,
            'likes_count': likes_count,
            'comments': comments,
            'is_owner': post.user == request.user
        }
    })
    

# Existing imports...
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required


@login_required
def hearts_sent(request):
    """Display all users to whom the current user has sent hearts (excluding mutual hearts)"""
    # Modified to exclude mutual hearts
    sent_crushes = Crush.objects.filter(sender=request.user, is_mutual=False).select_related('receiver')
    
    context = {
        'user': request.user,
        'sent_hearts': [
            {
                'user': crush.receiver,
                'crush_status': 'sent',  # Always 'sent' since we filtered is_mutual=False
                'sent_date': crush.timestamp
            }
            for crush in sent_crushes
        ]
    }
    return render(request, 'feed/hearts_sent.html', context)

@login_required
def hearts_received(request):
    """Display all users who have sent hearts to the current user (excluding mutual hearts)"""
    # Modified to exclude mutual hearts
    received_crushes = Crush.objects.filter(receiver=request.user, is_mutual=False).select_related('sender')
    
    context = {
        'user': request.user,
        'received_hearts': [
            {
                'user': crush.sender,
                'crush_status': 'received',  # Always 'received' since we filtered is_mutual=False
                'received_date': crush.timestamp
            }
            for crush in received_crushes
        ]
    }
    return render(request, 'feed/hearts_received.html', context)

@login_required
def friends_list(request):
    current_user = request.user
    all_users = User.objects.exclude(id=current_user.id)
   
    # Count unique viewers instead of total views
    profile_views = ProfileView.objects.filter(viewed=current_user).values('viewer').distinct().count()
   
    # Crush stats
    hearts_sent = Crush.objects.filter(sender=current_user, is_mutual=False).count()
    hearts_received = Crush.objects.filter(receiver=current_user, is_mutual=False).count()
    
    # Find mutual crushes (these are the friends)
    mutual_crushes = Crush.objects.filter(
        models.Q(sender=current_user, is_mutual=True) | 
        models.Q(receiver=current_user, is_mutual=True)
    ).select_related('sender', 'receiver')
    
    # Extract unique friends from mutual crushes
    friends_list = []
    processed_users = set()
    
    for crush in mutual_crushes:
        friend = crush.receiver if crush.sender == current_user else crush.sender
        
        # Avoid duplicate entries
        if friend.id not in processed_users:
            processed_users.add(friend.id)
            friends_list.append({
                'user': friend
            })
    
    # Count of unique friends
    friends_count = len(friends_list)
    
    context = {
        'user': request.user,
        'friends': friends_list,
        'profile_views': profile_views,
        'hearts_sent': hearts_sent,
        'hearts_received': hearts_received,
        'friends_count': friends_count
    }
    return render(request, 'feed/friends.html', context)
    

from django.http import JsonResponse
from .models import ConfessionLike, ConfessionComment
from .forms import ConfessionCommentForm

# feed/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Exists, OuterRef, Q, Value
from django.db.models.functions import Coalesce
from django.utils.timesince import timesince
from django.template.loader import render_to_string
from .forms import ConfessionForm
from .models import Confession, ConfessionLike, ConfessionComment
from accounts.models import User

# Other views from your original file (profile, home, etc.) are omitted for clarity.
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Exists, OuterRef, Q
from django.utils.timesince import timesince

from .models import Confession, ConfessionLike, ConfessionComment
from accounts.models import User

# A path to a default avatar for users without a profile picture.
# Make sure you have this file in your static directory.
DEFAULT_AVATAR_URL = '/static/ann.png'
ANONYMOUS_AVATAR_URL = '/static/ann.png'

@login_required
def explore(request):
    """
    Renders the main explore page.
    - The Confession query now uses select_related('user') to efficiently fetch
      the author's data (including profile picture) without extra database hits.
    """
    user_likes = ConfessionLike.objects.filter(
        confession=OuterRef('pk'),
        user=request.user
    )
    confessions = Confession.objects.select_related('user').annotate(
        like_count=Count('likes', distinct=True),
        comment_count=Count('comments', distinct=True),
        is_liked=Exists(user_likes)
    ).order_by('-created_at')[:20]

    return render(request, 'feed/explore.html', {
        'confessions': confessions,
        'anonymous_avatar': ANONYMOUS_AVATAR_URL,
        'default_avatar': DEFAULT_AVATAR_URL,
    })

@login_required
def search_users_api(request):
    """
    API for real-time user search.
    - FIXED: Now safely handles users with no profile picture to prevent 500 errors.
    """
    query = request.GET.get('q', '').strip()
    users_data = []

    if query:
        users = User.objects.filter(
            Q(username__icontains=query) | Q(full_name__icontains=query)
        ).exclude(id=request.user.id)[:10]

        for user in users:
            users_data.append({
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name or user.username,
                # Safely get URL or provide a default
                'profile_picture_url': user.profile_picture.url if user.profile_picture else DEFAULT_AVATAR_URL,
            })

    return JsonResponse({'users': users_data})


@login_required
def get_confession_details_api(request, confession_id):
    """
    API to get details for a single confession and its comments.
    - Now provides a specific avatar for anonymous comments.
    """
    confession = get_object_or_404(Confession, pk=confession_id)
    comments = confession.comments.select_related('user').order_by('created_at')

    comment_list = []
    for comment in comments:
        is_anon = comment.is_anonymous
        user = comment.user
        
        # Determine the correct profile picture URL
        if is_anon:
            pic_url = ANONYMOUS_AVATAR_URL
        elif user and user.profile_picture:
            pic_url = user.profile_picture.url
        else:
            pic_url = DEFAULT_AVATAR_URL

        comment_list.append({
            'user': "Anonymous" if is_anon else user.username,
            'profile_picture_url': pic_url,
            'content': comment.content,
            'time_since': timesince(comment.created_at) + " ago",
        })
        
    author_name = "Anonymous"
    if confession.user and not confession.is_anonymous:
        author_name = confession.user.username

    return JsonResponse({
        'success': True,
        'confession': {'content': confession.content, 'author': author_name},
        'comments': comment_list
    })

@login_required
def like_confession(request):
    """
    Handles liking/unliking a confession.
    """
    if request.method == 'POST':
        confession_id = request.POST.get('confession_id')
        confession = get_object_or_404(Confession, id=confession_id)
        like, created = ConfessionLike.objects.get_or_create(user=request.user, confession=confession)

        if not created:
            like.delete()
            is_liked = False
        else:
            is_liked = True

        return JsonResponse({
            'liked': is_liked,
            'like_count': confession.likes.count()
        })
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@login_required
def add_confession_comment(request):
    """
    Handles adding a new comment to a confession.
    """
    if request.method == 'POST':
        confession_id = request.POST.get('confession_id')
        content = request.POST.get('content', '').strip()
        is_anonymous = request.POST.get('is_anonymous') == 'true'
        confession = get_object_or_404(Confession, id=confession_id)

        if not content:
            return JsonResponse({'error': 'Comment cannot be empty'}, status=400)

        ConfessionComment.objects.create(
            confession=confession,
            user=request.user,
            content=content,
            is_anonymous=is_anonymous
        )

        return JsonResponse({
            'success': True,
            'message': 'Comment added successfully',
            'comment_count': confession.comments.count()
        })
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@login_required
def create_confession(request):
    """
    Handles the creation of a new confession.
    """
    if request.method == 'POST':
        form = ConfessionForm(request.POST)
        if form.is_valid():
            confession = form.save(commit=False)
            if not form.cleaned_data.get('is_anonymous'):
                confession.user = request.user
            confession.save()
            messages.success(request, "Confession posted successfully!")
            return redirect('feed:explore')
    else:
        form = ConfessionForm(initial={'is_anonymous': True})

    return render(request, 'feed/confession.html', {'form': form})

from django.http import JsonResponse

@login_required
def confession_comments_api(request, confession_id):
    confession = get_object_or_404(Confession, id=confession_id)
    comments = confession.comments.select_related('user').order_by('-created_at')
    return JsonResponse({
        "confession": {
            "id": confession.id,
            "content": confession.content,
        },
        "comments": [
            {
                "user": comment.user.username,
                "content": comment.content,
                "is_anonymous": comment.is_anonymous
            }
            for comment in comments
        ]
    })
from django.http import JsonResponse
from feed.models import ConfessionComment
from django.core.serializers import serialize

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
import traceback

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
import traceback

import traceback
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

def get_profile_picture_url(user):
    try:
        if hasattr(user, 'profile') and user.profile.profile_picture:
            return user.profile.profile_picture.url
    except Exception:
        pass
    return ''

def get_confession_comments(request, confession_id):
    try:
        confession = Confession.objects.get(id=confession_id)
        comments = confession.comments.select_related('user').all()
        
        comment_list = []
        for comment in comments:
            comment_list.append({
                'id': comment.id,
                'user': comment.user.username,
                'profile_picture': get_profile_picture_url(comment.user),
                'comment': comment.content,        # use content here
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'anonymous': comment.is_anonymous, # use is_anonymous here
            })
        return JsonResponse({'comments': comment_list})
    
    except Confession.DoesNotExist:
        return JsonResponse({'error': 'Confession not found'}, status=404)
    except Exception as e:
        # Log error if needed
        print("Exception in get_confession_comments:", e)
        return JsonResponse({'error': 'Server error occurred'}, status=500)

from django.template.loader import render_to_string # Add this import at the top
# In feed/views.py

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
        Crush.objects.filter(sender=current_user, receiver=profile_user).delete()
        received_crush_obj = Crush.objects.filter(sender=profile_user, receiver=current_user).first()
        if received_crush_obj:
            received_crush_obj.is_mutual = False; received_crush_obj.save()
    
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

# feed/views.py
from django.core.paginator import Paginator
from django.http import JsonResponse

@login_required
def load_users_api(request):
    category = request.GET.get('category')
    page_number = request.GET.get('page', 1)
    
    # IMPORTANT: Replace these querysets with your actual logic
    if category == 'recently_joined':
        # Your logic for recently_joined users
        all_users = User.objects.order_by('-date_joined').exclude(id=request.user.id)
    elif category == 'trending':
        # Your logic for trending users (e.g., order by profile views or hearts received)
        all_users = User.objects.order_by('-profile_views').exclude(id=request.user.id)
    elif category == 'same_year':
        # Your logic for same_year users
        all_users = User.objects.filter(year=request.user.year).exclude(id=request.user.id)
    elif category == 'same_department':
        # Your logic for same_department users
        all_users = User.objects.filter(department=request.user.department).exclude(id=request.user.id)
    elif category == 'same_college':
        # Your logic for same_college users
        all_users = User.objects.filter(college=request.user.college).exclude(id=request.user.id)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid category'}, status=400)

    paginator = Paginator(all_users, 10) # Show 10 users per page
    page_obj = paginator.get_page(page_number)

    users_data = []
    for user in page_obj.object_list:
        # Here, you'd check crush status like in your main view
        # This is a simplified example. You need to replicate your crush_status logic.
        crush_status = 'none' # Replace with your actual logic
        
        users_data.append({
            'id': user.id,
            'full_name': user.full_name,
            'profile_picture_url': user.profile_picture.url if user.profile_picture else '',
            'department': user.department or 'N/A',
            'college': user.college or 'N/A',
            'profile_url': request.build_absolute_uri(reverse('feed:profile', args=[user.id])),
            'crush_status': crush_status, # You need to calculate this
        })

    return JsonResponse({
        'status': 'ok',
        'users': users_data,
        'has_next': page_obj.has_next()
    })