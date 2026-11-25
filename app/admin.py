from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Freeze, Subscription, SubscriptionPlan, User
from .models import Booking, Schedule, WorkoutType




@admin.register(User)
class CustomUserAdmin(UserAdmin):
  list_display = ('email', 'full_name', 'phone', 'role', 'is_staff')
  list_filter = ('role', 'is_staff', 'is_active')
  search_fields = ('email', 'full_name', 'phone')
  ordering = ('email',)

  fieldsets = (
      (None, {'fields': ('email', 'password')}),
      ('Личные данные', {'fields': ('full_name', 'phone', 'photo', 'role')}),
      (
          'Права доступа',
          {'fields': ('is_active', 'is_staff', 'is_superuser')},
      ),
  )
  add_fieldsets = (
      (
          None,
          {
              'classes': ('wide',),
              'fields': (
                  'email',
                  'full_name',
                  'phone',
                  'role',
                  'password1',
                  'password2',
              ),
          },
      ),
  )


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
  list_display = (
      'name',
      'kind',
      'price',
      'duration_days',
      'workouts_count',
      'freeze_days_limit',
      'is_active',
  )
  list_filter = ('kind', 'is_active')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
  list_display = (
      'client',
      'plan',
      'status',
      'start_date',
      'end_date',
      'remaining_workouts',
      'remaining_freeze_days',
  )
  list_filter = ('status', 'plan')
  search_fields = ('client__full_name', 'client__email')


@admin.register(Freeze)
class FreezeAdmin(admin.ModelAdmin):
  list_display = ('subscription', 'start_date', 'end_date', 'status')
  list_filter = ('status',)

@admin.register(WorkoutType)
class WorkoutTypeAdmin(admin.ModelAdmin):
  list_display = ('name', 'duration_minutes')


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
  list_display = (
      'day_of_week',
      'start_time',
      'workout_type',
      'trainer',
      'max_capacity',
      'booked_count',
  )
  list_filter = ('day_of_week', 'workout_type', 'trainer')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
  list_display = ('client', 'schedule', 'subscription', 'status', 'created_at')
  list_filter = ('status', 'schedule__workout_type')