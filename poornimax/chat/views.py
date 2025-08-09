from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import (Q, Max, OuterRef, Subquery, Case, When, Value,
                              BooleanField, Exists, F)
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .models import Message, DeletedChat

User = get_user_model()


def _get_active_conversations(user):
    """
    Helper function to get all active conversation partners for a user.

    This single, efficient query annotates each user with:
    - last_message_time: The timestamp of the last message exchanged.
    - has_unread: A boolean indicating if there are unread messages.
    """
    
    # Subquery to get the deletion timestamp for the current user and an outer user.
    deleted_at_subquery = DeletedChat.objects.filter(
        user=user,
        other_user=OuterRef('pk')
    ).values('deleted_at')[:1]

    # Subquery for the last message time.
    last_message_subquery = Message.objects.filter(
        Q(sender=user, receiver=OuterRef('pk')) | Q(sender=OuterRef('pk'), receiver=user)
    ).order_by('-timestamp').values('timestamp')[:1]

    # Subquery to check for unread messages.
    # It must account for the chat deletion time.
    unread_subquery = Message.objects.filter(
        sender=OuterRef('pk'),
        receiver=user,
        read=False
    ).annotate(
        deleted_at=Subquery(deleted_at_subquery)
    ).filter(
        Q(deleted_at__isnull=True) | Q(timestamp__gt=F('deleted_at'))
    )

    # Main query to find all users the current user has messaged.
    users = User.objects.filter(
        Q(sent_messages__receiver=user) | Q(received_messages__sender=user)
    ).distinct().annotate(
        deleted_at=Subquery(deleted_at_subquery),
        last_message_time=Subquery(last_message_subquery),
        has_unread=Exists(unread_subquery)
    ).filter(
        # Filter out users where the chat was deleted and there are no new messages.
        Q(deleted_at__isnull=True) | Q(last_message_time__gt=F('deleted_at'))
    ).order_by('-last_message_time')

    return users


@login_required
def inbox_view(request):
    """Displays the user's inbox with all active conversations."""
    active_users = _get_active_conversations(request.user)
    return render(request, 'chat/inbox.html', {'users': active_users})


# chat/views.py

@login_required
def inbox_content(request):
    """Returns the rendered HTML for the inbox, used for AJAX refreshes."""
    # 1. This query runs successfully
    active_users = _get_active_conversations(request.user) 
    
    # 2. The error most likely happens HERE
    html = render_to_string('chat/inbox_partial.html', {'users': active_users}, request=request)
    
    # 3. This line is never reached
    return JsonResponse({'html': html})

@login_required
def inbox_unread_status(request):
    """
    Returns a simple dictionary of users who have unread messages.
    Used for efficient, lightweight polling to show/hide notification dots.
    """
    active_users_with_unread = _get_active_conversations(request.user).filter(has_unread=True)
    unread_status = {user.username: True for user in active_users_with_unread}
    return JsonResponse({'unread_status': unread_status})


@login_required
def inbox_updates(request):
    """
    Checks if there have been any new messages or deletions since the last check.
    This is a quick check to decide if a full refresh is needed.
    """
    after_str = request.GET.get('after')
    if not after_str:
        return JsonResponse({'error': 'Missing timestamp parameter'}, status=400)

    try:
        after_dt = parse_datetime(after_str)
        if after_dt is None:
            raise ValueError
    except ValueError:
        return JsonResponse({'error': 'Invalid timestamp format'}, status=400)

    user = request.user
    new_messages = Message.objects.filter(
        Q(receiver=user) | Q(sender=user),
        timestamp__gt=after_dt
    ).exists()

    deleted_chats = DeletedChat.objects.filter(
        user=user,
        deleted_at__gt=after_dt
    ).exists()
    
    # Check if a message was marked as read after the last update.
    read_messages = Message.objects.filter(
        receiver=user, read=True, timestamp__gt=after_dt
    ).exists()

    return JsonResponse({
        'updates': True,
        'last_update': timezone.now().isoformat(),
        'new_messages': new_messages,
        'deleted_chats': deleted_chats,
        'read_messages': read_messages
    })


@login_required
def chat_view(request, username):
    """Displays a chat conversation with another user."""
    other_user = get_object_or_404(User, username=username)

    # Mark all messages from this user as read upon opening the chat.
    Message.objects.filter(sender=other_user, receiver=request.user, read=False).update(read=True)

    # Handle sending a new message
    if request.method == 'POST':
        content = request.POST.get('message')
        if content:
            msg = Message.objects.create(sender=request.user, receiver=other_user, content=content)
            return JsonResponse({
                'sender': request.user.username,
                'content': msg.content,
                'timestamp': msg.timestamp.strftime('%H:%M'),
                'sender_is_user': True
            })

    # Get messages for the conversation, respecting deletion timestamps.
    deleted_chat = DeletedChat.objects.filter(user=request.user, other_user=other_user).first()
    message_filter = Q(sender__in=[request.user, other_user], receiver__in=[request.user, other_user])

    if deleted_chat:
        message_filter &= Q(timestamp__gt=deleted_chat.deleted_at)

    messages = Message.objects.filter(message_filter)
    
    return render(request, 'chat/chat.html', {'messages': messages, 'other_user': other_user})

from pathlib import Path
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import Message, DeletedChat
from django.contrib.auth import get_user_model

User = get_user_model()
@login_required
@require_POST
def delete_chat(request, username):
    other_user = get_object_or_404(User, username=username)
    if other_user == request.user:
        return JsonResponse({'success': False, 'error': 'Cannot delete chat with yourself.'}, status=400)

    # Get last deletion time for this chat
    last_deletion = DeletedChat.objects.filter(
        user=request.user,
        other_user=other_user
    ).values_list('deleted_at', flat=True).first()

    # Only grab messages after the last deletion
    message_filter = {
        'sender__in': [request.user, other_user],
        'receiver__in': [request.user, other_user],
    }
    if last_deletion:
        message_filter['timestamp__gt'] = last_deletion

    messages = Message.objects.filter(**message_filter).order_by('timestamp')

    try:
        base_dir = Path(settings.BASE_DIR) / 'deleted_chats'
        base_dir.mkdir(parents=True, exist_ok=True)
        file_path = base_dir / f"{request.user.username}_deletes_{other_user.username}.txt"

        with open(str(file_path), 'a', encoding='utf-8') as f:
            f.write(f"\n--- Chat history deleted by {request.user.username} on {timezone.now()} ---\n")
            for msg in messages:
                f.write(f"[{msg.timestamp}] {msg.sender.username} → {msg.receiver.username}: {msg.content}\n")
            f.write("\n")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'Could not archive chat: {e}'}, status=500)

    # Update deletion timestamp so next delete only gets new messages
    DeletedChat.objects.update_or_create(
        user=request.user,
        other_user=other_user,
        defaults={'deleted_at': timezone.now()}
    )

    return JsonResponse({'success': True})


@login_required
def poll_new_messages(request, username):
    """Polls for new messages within a specific chat window."""
    other_user = get_object_or_404(User, username=username)
    last_timestamp_str = request.GET.get('after')

    if not last_timestamp_str:
        return JsonResponse([], safe=False) # Nothing to check against

    try:
        last_dt = parse_datetime(last_timestamp_str)
        if last_dt is None:
            raise ValueError
    except ValueError:
        return JsonResponse({'error': 'Invalid timestamp format'}, status=400)

    # Fetch new messages and mark them as read
    new_messages = Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        timestamp__gt=last_dt
    )
    
    data = [{
        'sender': msg.sender.username,
        'content': msg.content,
        'timestamp': msg.timestamp.strftime('%H:%M'),
        'sender_is_user': False
    } for msg in new_messages]

    # Mark the fetched messages as read
    if new_messages.exists():
        new_messages.update(read=True)

    return JsonResponse(data, safe=False)