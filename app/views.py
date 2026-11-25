from datetime import timedelta
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .decorators import role_required
from .forms import FreezeForm, LoginForm, RegistrationForm
from .models import (
    Booking,
    Freeze,
    Schedule,
    Subscription,
    SubscriptionPlan,
    User,
    WorkoutType,
)

def index(request):
  workouts = WorkoutType.objects.all()[:3]
  plans = SubscriptionPlan.objects.filter(is_active=True)[:3]
  return render(
      request,
      'index.html',
      {
          'workouts': workouts,
          'plans': plans,
      },
  )

def login_view(request):
  if request.user.is_authenticated:
    return redirect('profile')

  if request.method == 'POST':
    form = LoginForm(request=request, data=request.POST)
    if form.is_valid():
      login(request, form.user)
      return redirect('profile')
  else:
    form = LoginForm()

  return render(request, 'login.html', {'form': form})

def register_view(request):
  if request.user.is_authenticated:
    return redirect('profile')

  if request.method == 'POST':
    form = RegistrationForm(request.POST)
    if form.is_valid():
      user = form.save()
      login(request, user)
      return redirect('profile')
  else:
    form = RegistrationForm()

  return render(request, 'register.html', {'form': form})

@require_POST
def logout_view(request):
  logout(request)
  return redirect('login')


@login_required
def profile_view(request):
  return render(request, 'profile.html')

def plans_list_view(request):
  plans = SubscriptionPlan.objects.filter(is_active=True)
  return render(request, 'plans.html', {'plans': plans})


@require_POST
@role_required(User.Role.CLIENT)
def buy_subscription_view(request, plan_id):
  plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
  
  has_active = Subscription.objects.filter(
      client=request.user,
      status__in=[Subscription.Status.ACTIVE, Subscription.Status.FROZEN],
  ).exists()

  if has_active:
    messages.error(
        request, 'У вас уже есть активный или замороженный абонемент.'
    )
    return redirect('profile')

  Subscription.objects.create(client=request.user, plan=plan)
  messages.success(request, f'Абонемент «{plan.name}» успешно оформлен!')
  return redirect('profile')


@login_required
def profile_view(request):
  active_sub = (
      Subscription.objects.filter(
          client=request.user,
          status__in=[Subscription.Status.ACTIVE, Subscription.Status.FROZEN],
      )
      .select_related('plan')
      .first()
  )

  history_subs = (
      Subscription.objects.filter(
          client=request.user, status=Subscription.Status.EXPIRED
      )
      .select_related('plan')
      .order_by('-end_date')
  )

  freeze_form = None
  if (
      active_sub
      and active_sub.status == Subscription.Status.ACTIVE
      and active_sub.remaining_freeze_days > 0
  ):
    freeze_form = FreezeForm(subscription=active_sub)

  return render(
      request,
      'profile.html',
      {
          'active_sub': active_sub,
          'history_subs': history_subs,
          'freeze_form': freeze_form,
      },
  )


@require_POST
@role_required(User.Role.CLIENT)
@transaction.atomic
def freeze_subscription_view(request, sub_id):
  sub = get_object_or_404(
      Subscription,
      id=sub_id,
      client=request.user,
      status=Subscription.Status.ACTIVE,
  )

  form = FreezeForm(subscription=sub, data=request.POST)
  if form.is_valid():
    days = form.cleaned_data['days']
    today = timezone.localdate()

    Freeze.objects.create(
        subscription=sub,
        start_date=today,
        end_date=today + timedelta(days=days - 1),
        status=Freeze.Status.ACTIVE,
    )

    sub.status = Subscription.Status.FROZEN
    sub.remaining_freeze_days -= days
    sub.end_date += timedelta(days=days)
    sub.save()

    messages.success(request, f'Абонемент заморожен на {days} дн.')
  else:
    messages.error(request, 'Некорректное количество дней для заморозки.')

  return redirect('profile')


@require_POST
@role_required(User.Role.CLIENT)
@transaction.atomic
def unfreeze_subscription_view(request, sub_id):
  sub = get_object_or_404(
      Subscription,
      id=sub_id,
      client=request.user,
      status=Subscription.Status.FROZEN,
  )

  active_freeze = sub.freezes.filter(status=Freeze.Status.ACTIVE).first()
  if active_freeze:
    today = timezone.localdate()
    planned_days = active_freeze.days_count
    used_days = max(0, (today - active_freeze.start_date).days)
    unused_days = max(0, planned_days - used_days)

    active_freeze.end_date = today
    active_freeze.status = Freeze.Status.COMPLETED
    active_freeze.save()

    sub.remaining_freeze_days += unused_days
    sub.end_date -= timedelta(days=unused_days)

  sub.status = Subscription.Status.ACTIVE
  sub.save()

  messages.success(request, 'Абонемент снова активен!')
  return redirect('profile')

def trainers_list_view(request):
  trainers = User.objects.filter(role=User.Role.TRAINER, is_active=True)
  return render(request, 'trainers.html', {'trainers': trainers})


def workouts_list_view(request):
  active_schedules = Schedule.objects.filter(
      is_completed=False
  ).select_related('trainer')
  workouts = WorkoutType.objects.prefetch_related(
      Prefetch('schedules', queryset=active_schedules, to_attr='active_slots')
  ).all()

  user_active_schedule_ids = set()
  if request.user.is_authenticated and request.user.role == User.Role.CLIENT:
    user_active_schedule_ids = set(
        Booking.objects.filter(
            client=request.user,
            status=Booking.Status.ACTIVE,
        ).values_list('schedule_id', flat=True)
    )

  return render(
      request,
      'workouts.html',
      {
          'workouts': workouts,
          'user_active_schedule_ids': user_active_schedule_ids,
      },
  )


def schedule_list_view(request):
  schedules = Schedule.objects.filter(is_completed=False).select_related(
    'workout_type', 'trainer'
)

  days_schedule = []
  for day_val, day_label in Schedule.DayOfWeek.choices:
    day_items = [s for s in schedules if s.day_of_week == day_val]
    days_schedule.append({
        'day_name': day_label,
        'items': day_items,
    })

  user_booked_ids = set()
  if request.user.is_authenticated and request.user.role == User.Role.CLIENT:
    today = timezone.localdate()
    active_bookings = Booking.objects.filter(
        client=request.user,
        status=Booking.Status.ACTIVE,
        workout_date__gte=today,
    ).select_related('schedule')

    for b in active_bookings:
      if b.workout_date == b.schedule.get_next_date():
        user_booked_ids.add(b.schedule_id)

  return render(
      request,
      'schedule.html',
      {
          'days_schedule': days_schedule,
          'user_booked_ids': user_booked_ids,
      },
  )


@require_POST
@role_required(User.Role.CLIENT)
@transaction.atomic
def book_workout_view(request, schedule_id):
  schedule = get_object_or_404(
        Schedule.objects.select_for_update(),
        id=schedule_id,
        is_completed=False,
  )
  
  next_date = schedule.get_next_date()

  already_active = Booking.objects.filter(
      client=request.user,
      schedule=schedule,
      status=Booking.Status.ACTIVE,
  ).exists()

  if already_active:
    messages.error(
        request,
        'Вы уже записаны на это занятие. Повторная запись возможна после его'
        ' прохождения.',
    )
    return redirect('workouts')

  if schedule.available_seats <= 0:
    messages.error(request, 'На ближайшее занятие больше нет свободных мест.')
    return redirect('workouts')

  today = timezone.localdate()
  sub = (
      Subscription.objects.select_for_update()
      .filter(
          client=request.user,
          status=Subscription.Status.ACTIVE,
          end_date__gte=today,
      )
      .select_related('plan')
      .first()
  )

  if not sub:
    messages.error(
        request, 'Для записи нужен активный (не замороженный) абонемент.'
    )
    return redirect('workouts')

  if sub.plan.kind == SubscriptionPlan.PlanKind.PACKAGE:
    if sub.remaining_workouts is None or sub.remaining_workouts <= 0:
      messages.error(request, 'На вашем пакетном абонементе закончились занятия.')
      return redirect('workouts')
    sub.remaining_workouts -= 1
    sub.save()

  Booking.objects.create(
      client=request.user,
      schedule=schedule,
      workout_date=next_date,
      subscription=sub,
      status=Booking.Status.ACTIVE,
  )

  messages.success(
      request,
      f'Вы записаны на «{schedule.workout_type.name}» ({next_date:%d.%m.%Y} в'
      f' {schedule.start_time:%H:%M})!',
  )
  return redirect('workouts')

@require_POST
@role_required(User.Role.CLIENT)
def hide_booking_view(request, booking_id):
  booking = get_object_or_404(
      Booking,
      id=booking_id,
      client=request.user,
  )

  today = timezone.localdate()
  is_finished = (
      booking.status in [Booking.Status.ATTENDED, Booking.Status.MISSED]
      or booking.workout_date < today
  )

  if not is_finished:
    messages.error(
        request,
        'Убрать можно только прошедшее занятие. Предстоящее можно только'
        ' отменить.',
    )
    return redirect('profile')

  booking.is_hidden_by_client = True
  booking.save()
  messages.success(request, 'Занятие удалено из списка.')
  return redirect('profile')


@require_POST
@role_required(User.Role.CLIENT)
@transaction.atomic
@require_POST
@role_required(User.Role.CLIENT)
@transaction.atomic
def cancel_booking_view(request, booking_id):
  booking = get_object_or_404(
      Booking.objects.select_related('schedule', 'subscription__plan'),
      id=booking_id,
      client=request.user,
      status=Booking.Status.ACTIVE,
  )

  today = timezone.localdate()
  if booking.workout_date < today:
    messages.error(request, 'Нельзя отменить прошедшее занятие.')
    return redirect('profile')

  booking.status = Booking.Status.CANCELED
  booking.save()

  sub = booking.subscription
  if (
      sub.plan.kind == SubscriptionPlan.PlanKind.PACKAGE
      and sub.status != Subscription.Status.EXPIRED
  ):
    sub.remaining_workouts = (sub.remaining_workouts or 0) + 1
    sub.save()

  messages.success(request, 'Запись отменена.')
  return redirect('profile')


@login_required
def profile_view(request):
  active_sub = (
      Subscription.objects.filter(
          client=request.user,
          status__in=[Subscription.Status.ACTIVE, Subscription.Status.FROZEN],
      )
      .select_related('plan')
      .first()
  )

  history_subs = (
      Subscription.objects.filter(
          client=request.user, status=Subscription.Status.EXPIRED
      )
      .select_related('plan')
      .order_by('-end_date')
  )

  freeze_form = None
  if (
      active_sub
      and active_sub.status == Subscription.Status.ACTIVE
      and active_sub.remaining_freeze_days > 0
  ):
    freeze_form = FreezeForm(subscription=active_sub)

  today = timezone.localdate()

  upcoming_bookings = (
        Booking.objects.filter(
            client=request.user,
            status=Booking.Status.ACTIVE,
            workout_date__gte=today,
        )
        .select_related('schedule__workout_type', 'schedule__trainer')
        .order_by('workout_date', 'schedule__start_time')
    )

  past_bookings = (
        Booking.objects.filter(
            client=request.user,
        )
        .exclude(status=Booking.Status.CANCELED)
        .filter(
            models.Q(
                status__in=[Booking.Status.ATTENDED, Booking.Status.MISSED]
            )
            | models.Q(workout_date__lt=today)
        )
        .select_related('schedule__workout_type', 'schedule__trainer')
        .order_by('-workout_date', '-schedule__start_time')
    )
  return render(
      request,
      'profile.html',
      {
          'active_sub': active_sub,
          'history_subs': history_subs,
          'freeze_form': freeze_form,
          'upcoming_bookings': upcoming_bookings,
          'past_bookings': past_bookings
      },
  )


@role_required(User.Role.TRAINER, User.Role.ADMIN)
def trainer_dashboard_view(request):
  schedules = (
      Schedule.objects.filter(
          trainer=request.user,
          is_completed=False,
      )
      .select_related('workout_type')
      .order_by('day_of_week', 'start_time')
  )

  schedule_list = []
  for item in schedules:
    bookings = (
        Booking.objects.filter(
            schedule=item,
        )
        .exclude(status=Booking.Status.CANCELED)
        .select_related('client')
        .order_by('client__full_name')
    )

    schedule_list.append({
        'schedule': item,
        'bookings': bookings,
        'session_date': (
            bookings[0].workout_date if bookings else item.get_next_date()
        ),
    })

  return render(
      request, 'trainer_dashboard.html', {'schedule_list': schedule_list}
  )


@require_POST
@role_required(User.Role.TRAINER, User.Role.ADMIN)
@transaction.atomic
def complete_workout_session_view(request, schedule_id):
  schedule = get_object_or_404(
      Schedule,
      id=schedule_id,
      trainer=request.user,
      is_completed=False,
  )

  bookings = Booking.objects.filter(
      schedule=schedule,
  ).exclude(status=Booking.Status.CANCELED)

  bookings.filter(status=Booking.Status.ACTIVE).update(
      status=Booking.Status.ATTENDED
  )

  schedule.is_completed = True
  schedule.save()

  messages.success(
      request,
      f'Занятие «{schedule.workout_type.name}» завершено и удалено из'
      ' расписания.',
  )
  return redirect('trainer_dashboard')


@require_POST
@role_required(User.Role.TRAINER, User.Role.ADMIN)
def hide_booking_by_trainer_view(request, booking_id):
  booking = get_object_or_404(
      Booking,
      id=booking_id,
      schedule__trainer=request.user,
  )

  today = timezone.localdate()
  is_finished = (
      booking.status in [Booking.Status.ATTENDED, Booking.Status.MISSED]
      or booking.workout_date < today
  )

  if not is_finished:
    messages.error(
        request,
        'Сначала отметьте присутствие клиента, прежде чем убрать запись.',
    )
    return redirect('trainer_dashboard')

  booking.is_hidden_by_trainer = True
  booking.save()
  messages.success(
      request, f'Запись клиента {booking.client.full_name} убрана из списка.'
  )
  return redirect('trainer_dashboard')


@require_POST
@role_required(User.Role.TRAINER, User.Role.ADMIN)
def mark_attendance_view(request, booking_id):
  booking = get_object_or_404(
      Booking,
      id=booking_id,
      schedule__trainer=request.user,
  )

  new_status = request.POST.get('status')
  if new_status in [
      Booking.Status.ATTENDED,
      Booking.Status.MISSED,
      Booking.Status.ACTIVE,
  ]:
    booking.status = new_status
    booking.save()
    messages.success(
        request,
        f'Статус для {booking.client.full_name} обновлен:'
        f' {booking.get_status_display()}.',
    )

  return redirect('trainer_dashboard')