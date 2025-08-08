# Django Imports
from django.urls import path

# Local Imports
from . import views

# Define the application namespace for URL reversing
app_name = "feed"


urlpatterns = [
    # ===================================================================
    # Core Application Pages
    # ===================================================================
    path('home/', views.home, name='home'),
    path('explore/', views.explore, name='explore'),
    path('all/', views.all_users, name='all'),
    path('friends/', views.friends_list, name='friends_list'),

    # ===================================================================
    # User Profile & Interactions
    # ===================================================================
    path('profile/<int:user_id>/', views.profile, name='profile'),
    path('crush_action/<int:user_id>/', views.crush_action, name='crush_action'),
    path('profile/crush_action/<int:user_id>/', views.crush_action_profile, name='crush_action_profile'),
    path('hearts/sent/', views.hearts_sent, name='hearts_sent'),
    path('hearts/received/', views.hearts_received, name='hearts_received'),

    # ===================================================================
    # Posts & Comments
    # ===================================================================
    path('create-post/', views.create_post, name='create_post'),
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('post/<int:post_id>/comments/', views.get_post_comments, name='get_post_comments'),
    path('post/<int:post_id>/data/', views.get_post_data, name='get_post_data'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),

    # ===================================================================
    # Confessions
    # ===================================================================
    path('confession/', views.create_confession, name='confession'),
    path('confession/<int:confession_id>/comments/', views.get_confession_comments, name='get_confession_comments'),

    # ===================================================================
    # API Endpoints (for AJAX / Fetch)
    # ===================================================================
    path('api/load-users/', views.load_users_api, name='load_users_api'),
    path('api/search-users/', views.search_users_api, name='search_users_api'),
    path('api/get-home-updates/', views.get_home_updates, name='get_home_updates'),
    path('api/confession/like/', views.like_confession, name='like_confession'),
    path('api/confession/comment/', views.add_confession_comment, name='add_confession_comment'),
    path('api/confession/<int:confession_id>/comments/', views.confession_comments_api, name='confession_comments_api'),
    path('api/confession/<int:confession_id>/details/', views.get_confession_details_api, name='get_confession_details_api'),

    # ===================================================================
    # Lazy Loading Endpoints
    # ===================================================================
    path('lazy-load/posts/', views.lazy_load_posts, name='lazy_load_posts'),
    path('lazy-load/recently-joined/', views.lazy_load_section, {'section_type': 'recently-joined'}, name='lazy_load_recently_joined'),
    path('lazy-load/same-year/', views.lazy_load_section, {'section_type': 'same-year'}, name='lazy_load_same_year'),
    path('lazy-load/same-department/', views.lazy_load_section, {'section_type': 'same-department'}, name='lazy_load_same_department'),
    path('lazy-load/same-college/', views.lazy_load_section, {'section_type': 'same-college'}, name='lazy_load_same_college'),
    
    # ===================================================================
    # Debugging & Testing Endpoints
    # ===================================================================
    path('debug-posts/', views.debug_comprehensive_posts, name='debug_posts'),
    path('test-lazy-load/', views.test_lazy_load_posts, name='test_lazy_load'),
    path('lazy-load-improved/', views.lazy_load_posts_improved, name='lazy_load_improved'),
]