from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Q, Max, OuterRef, Subquery
from django.template.loader import render_to_string
from django.utils.dateparse import parse_datetime
from chat.models import Message, DeletedChat
import os

from django.db.models import Case, When, Value, BooleanField

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


User = get_user_model()

from django.db.models import OuterRef, Subquery, Q, Max

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Q, Max, OuterRef, Subquery
from django.template.loader import render_to_string
from django.utils.dateparse import parse_datetime
from chat.models import Message, DeletedChat

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, Exists, OuterRef, Case, When, Value, BooleanField, Subquery
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.shortcuts import render
from .models import Message, DeletedChat

User = get_user_model()

@login_required
def inbox_view(request):
    user = request.user
    msgs = Message.objects.filter(Q(sender=user) | Q(receiver=user))

    user_ids = set()
    for msg in msgs.values('sender', 'receiver'):
        if msg['sender'] != user.id:
            user_ids.add(msg['sender'])
        if msg['receiver'] != user.id:
            user_ids.add(msg['receiver'])

    deleted_chats = DeletedChat.objects.filter(user=user, other_user__in=user_ids)
    deleted_map = {dc.other_user_id: dc.deleted_at for dc in deleted_chats}

    filtered_user_ids = []
    for other_id in user_ids:
        last_msg_time = msgs.filter(
            Q(sender=user, receiver=other_id) | Q(sender=other_id, receiver=user)
        ).aggregate(last_time=Max('timestamp'))['last_time']

        deleted_at = deleted_map.get(other_id)
        if not deleted_at or (last_msg_time and last_msg_time > deleted_at):
            filtered_user_ids.append(other_id)

    users = User.objects.filter(id__in=filtered_user_ids)

    # Subquery to get last message timestamp
    last_msg_subquery = Message.objects.filter(
        Q(sender=user, receiver=OuterRef('pk')) | Q(sender=OuterRef('pk'), receiver=user)
    ).order_by('-timestamp').values('timestamp')[:1]

    # Create a case-by-case subquery for unread messages that respects deletion timestamps
    unread_cases = []
    for user_id in filtered_user_ids:
        deleted_at = deleted_map.get(user_id)
        if deleted_at:
            # Only count unread messages after deletion timestamp
            unread_filter = Q(
                sender=user_id,
                receiver=user,
                read=False,
                timestamp__gt=deleted_at
            )
        else:
            # No deletion, count all unread messages
            unread_filter = Q(
                sender=user_id,
                receiver=user,
                read=False
            )
        unread_cases.append(When(pk=user_id, then=Exists(Message.objects.filter(unread_filter))))

    # Apply the conditional unread check
    users = users.annotate(
        last_message_time=Subquery(last_msg_subquery),
        has_unread=Case(
            *unread_cases,
            default=Value(False),
            output_field=BooleanField()
        )
    ).order_by('-last_message_time')

    return render(request, 'chat/inbox.html', {'users': users})

@login_required
def inbox_content(request):
    user = request.user
    msgs = Message.objects.filter(Q(sender=user) | Q(receiver=user))

    user_ids = set()
    for msg in msgs.values('sender', 'receiver'):
        if msg['sender'] != user.id:
            user_ids.add(msg['sender'])
        if msg['receiver'] != user.id:
            user_ids.add(msg['receiver'])

    deleted_chats = DeletedChat.objects.filter(user=user, other_user__in=user_ids)
    deleted_map = {dc.other_user_id: dc.deleted_at for dc in deleted_chats}

    filtered_user_ids = []
    for other_id in user_ids:
        last_msg_time = msgs.filter(
            Q(sender=user, receiver=other_id) | Q(sender=other_id, receiver=user)
        ).aggregate(last_time=Max('timestamp'))['last_time']

        deleted_at = deleted_map.get(other_id)
        if not deleted_at or (last_msg_time and last_msg_time > deleted_at):
            filtered_user_ids.append(other_id)

    users = User.objects.filter(id__in=filtered_user_ids)

    # Last message timestamp subquery
    last_message_time_subquery = msgs.filter(
        Q(sender=user, receiver=OuterRef('pk')) | Q(sender=OuterRef('pk'), receiver=user)
    ).order_by('-timestamp').values('timestamp')[:1]

    # Add the same unread logic as in inbox_view
    unread_cases = []
    for user_id in filtered_user_ids:
        deleted_at = deleted_map.get(user_id)
        if deleted_at:
            # Only count unread messages after deletion timestamp
            unread_filter = Q(
                sender=user_id,
                receiver=user,
                read=False,
                timestamp__gt=deleted_at
            )
        else:
            # No deletion, count all unread messages
            unread_filter = Q(
                sender=user_id,
                receiver=user,
                read=False
            )
        unread_cases.append(When(pk=user_id, then=Exists(Message.objects.filter(unread_filter))))

    users = users.annotate(
        last_message_time=Subquery(last_message_time_subquery),
        has_unread=Case(
            *unread_cases,
            default=Value(False),
            output_field=BooleanField()
        ) if unread_cases else Value(False, output_field=BooleanField())
    ).order_by('-last_message_time')

    html = render_to_string('chat/inbox_partial.html', {'users': users}, request=request)
    return JsonResponse({'html': html})

@login_required
def inbox_updates(request):
    after = request.GET.get('after')
    if not after:
        return JsonResponse({'error': 'Missing timestamp parameter'}, status=400)

    after_dt = parse_datetime(after)
    if after_dt is None:
        return JsonResponse({'error': 'Invalid timestamp format'}, status=400)

    new_messages = Message.objects.filter(
        Q(receiver=request.user) | Q(sender=request.user),
        timestamp__gt=after_dt
    ).exists()

    deleted_chats = DeletedChat.objects.filter(
        user=request.user,
        deleted_at__gt=after_dt
    ).exists()

    # Check for messages that were marked as read (this helps detect when dots should disappear)
    read_messages = Message.objects.filter(
        receiver=request.user,
        read=True,
        timestamp__gt=after_dt
    ).exists()

    return JsonResponse({
        'updates': True,
        'last_update': timezone.now().isoformat(),
        'new_messages': new_messages,
        'deleted_chats': deleted_chats,
        'read_messages': read_messages
    })

# Optional: Add a dedicated endpoint for just unread status updates (more efficient)
@login_required
def inbox_unread_status(request):
    """
    Returns just the unread status for each user without full HTML refresh.
    More efficient for frequent polling.
    """
    user = request.user
    msgs = Message.objects.filter(Q(sender=user) | Q(receiver=user))

    user_ids = set()
    for msg in msgs.values('sender', 'receiver'):
        if msg['sender'] != user.id:
            user_ids.add(msg['sender'])
        if msg['receiver'] != user.id:
            user_ids.add(msg['receiver'])

    deleted_chats = DeletedChat.objects.filter(user=user, other_user__in=user_ids)
    deleted_map = {dc.other_user_id: dc.deleted_at for dc in deleted_chats}

    unread_status = {}
    for other_id in user_ids:
        deleted_at = deleted_map.get(other_id)
        
        if deleted_at:
            # Only count unread messages after deletion timestamp
            has_unread = Message.objects.filter(
                sender=other_id,
                receiver=user,
                read=False,
                timestamp__gt=deleted_at
            ).exists()
        else:
            # No deletion, count all unread messages
            has_unread = Message.objects.filter(
                sender=other_id,
                receiver=user,
                read=False
            ).exists()
        
        if has_unread:
            try:
                other_user = User.objects.get(id=other_id)
                unread_status[other_user.username] = True
            except User.DoesNotExist:
                pass

    return JsonResponse({'unread_status': unread_status})

@login_required
def chat_view(request, username):
    other_user = get_object_or_404(User, username=username)

    # Mark all unread messages from other_user to current user as read
    Message.objects.filter(sender=other_user, receiver=request.user, read=False).update(read=True)

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

    deleted_chat = DeletedChat.objects.filter(user=request.user, other_user=other_user).first()

    if deleted_chat:
        messages = Message.objects.filter(
            sender__in=[request.user, other_user],
            receiver__in=[request.user, other_user],
            timestamp__gt=deleted_chat.deleted_at
        )
    else:
        messages = Message.objects.filter(
            sender__in=[request.user, other_user],
            receiver__in=[request.user, other_user]
        )

    return render(request, 'chat/chat.html', {
        'messages': messages,
        'other_user': other_user
    })


from pathlib import Path
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from .models import DeletedChat, Message
from accounts.models import User  # Adjust import if needed
from django.conf import settings

@login_required
@require_POST
def delete_chat(request, username):
    other_user = get_object_or_404(User, username=username)

    if other_user == request.user:
        return JsonResponse({'success': False, 'error': 'Cannot delete chat with yourself.'}, status=400)

    user1 = request.user.username
    user2 = other_user.username

    # Use pathlib.Path for paths
    base_dir = settings.BASE_DIR / 'deleted_chats'
    base_dir.mkdir(parents=True, exist_ok=True)  # create directory if it doesn't exist

    file_path = base_dir / f"{user1}_deletes_{user2}.txt"

    deleted_chat_record = DeletedChat.objects.filter(user=request.user, other_user=other_user).first()
    last_deleted_at = deleted_chat_record.deleted_at if deleted_chat_record else None

    if last_deleted_at:
        messages = Message.objects.filter(
            Q(sender=request.user, receiver=other_user) | Q(sender=other_user, receiver=request.user),
            timestamp__gt=last_deleted_at
        ).order_by('timestamp')
    else:
        messages = Message.objects.filter(
            Q(sender=request.user, receiver=other_user) | Q(sender=other_user, receiver=request.user)
        ).order_by('timestamp')

    if not messages.exists():
        DeletedChat.objects.update_or_create(
            user=request.user,
            other_user=other_user,
            defaults={'deleted_at': timezone.now()}
        )
        return JsonResponse({'success': True, 'message': 'No new messages to delete.'})

    timestamp_str = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    header = f"\n--- Chat deleted on {timestamp_str} ---\n"

    lines = []
    for msg in messages:
        time_str = msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        sender = msg.sender.username
        content = msg.content.replace('\n', ' ')
        lines.append(f"[{time_str}] {sender}: {content}")

    chat_text = header + "\n".join(lines) + "\n"

    # Open the file using the string representation of Path
    with open(str(file_path), 'a', encoding='utf-8') as f:
        f.write(chat_text)

    DeletedChat.objects.update_or_create(
        user=request.user,
        other_user=other_user,
        defaults={'deleted_at': timezone.now()}
    )

    return JsonResponse({'success': True})


@login_required
def poll_new_messages(request, username):
    other_user = get_object_or_404(User, username=username)

    last_timestamp = request.GET.get('after')
    if last_timestamp:
        last_dt = parse_datetime(last_timestamp)
    else:
        last_dt = timezone.now()

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

    return JsonResponse(data, safe=False)
