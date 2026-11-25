from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('plans/', views.plans_list_view, name='plans'),
    path(
        'plans/<int:plan_id>/buy/',
        views.buy_subscription_view,
        name='buy_subscription',
    ),
    path(
        'subscriptions/<int:sub_id>/freeze/',
        views.freeze_subscription_view,
        name='freeze_subscription',
    ),
    path(
        'subscriptions/<int:sub_id>/unfreeze/',
        views.unfreeze_subscription_view,
        name='unfreeze_subscription',
    ),
    path('trainers/', views.trainers_list_view, name='trainers'),
    path('workouts/', views.workouts_list_view, name='workouts'),
    path('schedule/', views.schedule_list_view, name='schedule'),
    path(
        'schedule/<int:schedule_id>/book/',
        views.book_workout_view,
        name='book_workout',
    ),
    path(
        'bookings/<int:booking_id>/cancel/',
        views.cancel_booking_view,
        name='cancel_booking',
    ),
    path(
        'trainer-panel/',
        views.trainer_dashboard_view,
        name='trainer_dashboard',
    ),
    path(
    'bookings/<int:booking_id>/attendance/',
    views.mark_attendance_view,
    name='mark_attendance',
    ),
    path(
    'trainer/bookings/<int:booking_id>/hide/',
    views.hide_booking_by_trainer_view,
    name='trainer_hide_booking'),
    path(
    'trainer/schedules/<int:schedule_id>/complete/',
    views.complete_workout_session_view,
    name='complete_workout_session'),
]