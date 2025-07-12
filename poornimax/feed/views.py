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
    }
    return render(request, 'feed/profile.html', context)


def calculate_compatibility(user1, user2):
    try:
        user1_questionnaire = UserQuestionnaire.objects.get(user=user1)
        user2_questionnaire = UserQuestionnaire.objects.get(user=user2)
        
        total_score = 0
        max_possible_score = 0
        
        # Relationship Intent - Highest weight (45%)
        relationship_weight = 45
        relationship_score = 0
        relationship_max = 5
        
        if user1_questionnaire.relationship_status == user2_questionnaire.relationship_status:
            relationship_score += 1
        if user1_questionnaire.dating_approach == user2_questionnaire.dating_approach:
            relationship_score += 1
        if user1_questionnaire.compatibility == user2_questionnaire.compatibility:
            relationship_score += 1
        if user1_questionnaire.relationship_view == user2_questionnaire.relationship_view:
            relationship_score += 1
        if user1_questionnaire.similar_interests == user2_questionnaire.similar_interests:
            relationship_score += 1
            
        # Calculate weighted relationship score
        total_score += (relationship_score / relationship_max) * relationship_weight
        max_possible_score += relationship_weight
        
        # Multiple Choice Fields - Medium weight (35%)
        multi_choice_weight = 35
        multi_choice_score = 0
        multi_choice_max = 3
        
        # Hobbies comparison
        user1_hobbies = set(user1_questionnaire.hobbies.split(',')) if user1_questionnaire.hobbies else set()
        user2_hobbies = set(user2_questionnaire.hobbies.split(',')) if user2_questionnaire.hobbies else set()
        if user1_hobbies and user2_hobbies:
            common_hobbies = user1_hobbies.intersection(user2_hobbies)
            hobby_similarity = len(common_hobbies) / max(len(user1_hobbies.union(user2_hobbies)), 1)
            multi_choice_score += hobby_similarity
            
        # College events comparison
        user1_events = set(user1_questionnaire.college_events.split(',')) if user1_questionnaire.college_events else set()
        user2_events = set(user2_questionnaire.college_events.split(',')) if user2_questionnaire.college_events else set()
        if user1_events and user2_events:
            common_events = user1_events.intersection(user2_events)
            events_similarity = len(common_events) / max(len(user1_events.union(user2_events)), 1)
            multi_choice_score += events_similarity
            
        # Weekend plans comparison
        user1_weekends = set(user1_questionnaire.weekend_plans.split(',')) if user1_questionnaire.weekend_plans else set()
        user2_weekends = set(user2_questionnaire.weekend_plans.split(',')) if user2_questionnaire.weekend_plans else set()
        if user1_weekends and user2_weekends:
            common_weekends = user1_weekends.intersection(user2_weekends)
            weekends_similarity = len(common_weekends) / max(len(user1_weekends.union(user2_weekends)), 1)
            multi_choice_score += weekends_similarity
            
        # Calculate weighted multi-choice score
        total_score += (multi_choice_score / multi_choice_max) * multi_choice_weight
        max_possible_score += multi_choice_weight
        
        # Personality Traits - Lower weight (20%)
        personality_weight = 20
        personality_score = 0
        personality_max = 7
        
        if user1_questionnaire.introvert_extrovert == user2_questionnaire.introvert_extrovert:
            personality_score += 1
        if user1_questionnaire.first_meet == user2_questionnaire.first_meet:
            personality_score += 1
        if user1_questionnaire.sleep_type == user2_questionnaire.sleep_type:
            personality_score += 1
        if user1_questionnaire.important_trait == user2_questionnaire.important_trait:
            personality_score += 1
        if user1_questionnaire.comm_style == user2_questionnaire.comm_style:
            personality_score += 1
        if user1_questionnaire.posting_frequency == user2_questionnaire.posting_frequency:
            personality_score += 1
        if user1_questionnaire.free_time == user2_questionnaire.free_time:
            personality_score += 1
            
        # Calculate weighted personality score
        total_score += (personality_score / personality_max) * personality_weight
        max_possible_score += personality_weight
        
        # Calculate final percentage (normalized to 100%)
        final_score = (total_score / max_possible_score) * 100
        
        # Ensure minimum compatibility of 19% and maximum of 99%
        final_score = max(19, min(99, final_score))
        
        # Round to nearest integer
        return round(final_score)
        
    except UserQuestionnaire.DoesNotExist:
        return None


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
    trending = all_users.order_by('-date_joined')[:10]

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
        'trending': annotate_users_with_crush(trending),
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

@login_required
def crush_action(request, user_id):
    profile_user = get_object_or_404(User, id=user_id)
    
    # Don't allow sending crush to yourself
    if profile_user == request.user:
        messages.error(request, "You cannot send a crush to yourself.")
        return redirect('feed:profile', user_id=user_id)
    
    if request.method == 'POST':
        action = request.POST.get('crush_action')

        # Handle Send Crush action
        if action == 'send_crush':
            # Check if crush already exists
            existing_crush = Crush.objects.filter(sender=request.user, receiver=profile_user).first()
            
            if not existing_crush:
                # Create new crush
                crush = Crush.objects.create(sender=request.user, receiver=profile_user)
                # Check if there's a mutual crush and handle friendship creation
                crush.check_mutual_and_create_friendship()
                messages.success(request, 'Crush sent! 💘')
            else:
                messages.info(request, 'You already sent a crush.')

        # Handle Accept Crush action
        elif action == 'accept_crush':
            # First check if they sent us a crush
            received_crush = Crush.objects.filter(sender=profile_user, receiver=request.user).first()
            
            if received_crush:
                # Create the reverse crush
                crush, created = Crush.objects.get_or_create(sender=request.user, receiver=profile_user)
                
                # Update both crushes to mutual
                received_crush.is_mutual = True
                crush.is_mutual = True
                received_crush.save()
                crush.save()
                
                # Create friendship if it doesn't exist
                if not Friendship.are_friends(request.user, profile_user):
                    Friendship.objects.get_or_create(user1=request.user, user2=profile_user)
                
                messages.success(request, 'It\'s a match! 💖 You\'re now friends!')
            else:
                messages.error(request, 'No crush to accept.')

        # Handle Uncrush action
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
                
                messages.success(request, 'Crush removed 💔')
            else:
                messages.info(request, 'No crush to remove.')

        return redirect('feed:profile', user_id=user_id)

    # If not POST request
    return HttpResponse("Invalid request", status=400)




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

@login_required
def explore(request):
    query = request.GET.get('q', '')
    users = []

    if query:
        users = User.objects.filter(username__icontains=query).exclude(id=request.user.id)[:20]

    confessions = Confession.objects.all().prefetch_related('likes')[:20]

    # Annotate each confession with is_liked attribute
    for confession in confessions:
        confession.is_liked = confession.likes.filter(user=request.user).exists()
        confession.like_count = confession.likes.count()

    return render(request, 'feed/explore.html', {
        'query': query,
        'users': users,
        'confessions': confessions
    })

@login_required
def create_confession(request):
    if request.method == 'POST':
        form = ConfessionForm(request.POST)
        if form.is_valid():
            confession = form.save(commit=False)
            
            # Only store user reference if not anonymous
            if not confession.is_anonymous:
                confession.user = request.user
            
            confession.save()
            messages.success(request, "Confession posted successfully!")
            return redirect('feed:explore')
    else:
        form = ConfessionForm(initial={'is_anonymous': True})
    
    return render(request, 'feed/confession.html', {'form': form})

@login_required
def like_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        
        # Check if already liked
        like_exists = Like.objects.filter(post=post, user=request.user).exists()
        
        if like_exists:
            # Unlike
            Like.objects.filter(post=post, user=request.user).delete()
            liked = False
        else:
            # Like
            Like.objects.create(post=post, user=request.user)
            liked = True
        
        # Redirect to the profile page of the post owner
        return redirect('feed:profile', user_id=post.user.id)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            comment = Comment.objects.create(
                post=post,
                user=request.user,
                content=content
            )
            
            # Redirect to the profile page of the post owner
            return redirect('feed:profile', user_id=post.user.id)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


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

@login_required
def like_confession(request):
    confession_id = request.POST.get('confession_id')
    confession = Confession.objects.get(id=confession_id)

    liked, created = ConfessionLike.objects.get_or_create(user=request.user, confession=confession)
    if not created:
        liked.delete()
        liked = False
    else:
        liked = True

    return JsonResponse({
        'liked': liked,
        'like_count': confession.likes.count()
    })

@login_required
def add_confession_comment(request):
    confession_id = request.POST.get('confession_id')
    content = request.POST.get('content')
    is_anonymous = request.POST.get('is_anonymous') == 'true'
    confession = Confession.objects.get(id=confession_id)

    ConfessionComment.objects.create(
        confession=confession,
        user=request.user,
        content=content,
        is_anonymous=is_anonymous
    )

    return JsonResponse({
        'comment_count': confession.comments.count(),
        'message': 'Comment added successfully'
    })


from django.http import JsonResponse


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
