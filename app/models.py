from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import timedelta
from django.utils import timezone

class User(AbstractUser):

    class Role(models.TextChoices):
        CLIENT = 'client', 'Клиент'
        TRAINER = 'trainer', 'Тренер'
        ADMIN = 'admin', 'Администратор'

    first_name = None
    last_name = None
    photo = models.ImageField(
      'Фотография', upload_to='trainers/', null=True, blank=True
    )
    price = models.IntegerField('Цена', default=0)
    full_name = models.CharField('ФИО', max_length=150)
    email = models.EmailField('Email', unique=True)
    phone = models.CharField('Номер телефона', max_length=20, unique=True)
    role = models.CharField(
      'Роль', max_length=10, choices=Role.choices, default=Role.CLIENT
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name', 'phone']

    def __str__(self):
        return f'{self.full_name} ({self.get_role_display()})'
    
class SubscriptionPlan(models.Model):

  class PlanKind(models.TextChoices):
    PACKAGE = 'package', 'Пакетный'
    TARIFF = 'tariff', 'Тарифный (безлимит)'

  name = models.CharField('Название', max_length=100)
  kind = models.CharField(
      'Вид абонемента',
      max_length=10,
      choices=PlanKind.choices,
      default=PlanKind.TARIFF,
  )
  price = models.IntegerField('Цена')
  duration_days = models.PositiveIntegerField('Срок действия (дней)')
  workouts_count = models.PositiveIntegerField(
      'Количество занятий',
      null=True,
      blank=True,
  )
  freeze_days_limit = models.PositiveIntegerField(
      'Доступно дней заморозки', default=0
  )
  is_active = models.BooleanField('Доступен к покупке', default=True)

  def __str__(self):
    return f'{self.name} ({self.price} руб.)'

class Subscription(models.Model):

  class Status(models.TextChoices):
    ACTIVE = 'active', 'Активен'
    FROZEN = 'frozen', 'Заморожен'
    EXPIRED = 'expired', 'Истек'

  client = models.ForeignKey(
      User,
      on_delete=models.CASCADE,
      related_name='subscriptions',
      limit_choices_to={'role': User.Role.CLIENT},
      verbose_name='Клиент',
  )
  plan = models.ForeignKey(
      SubscriptionPlan,
      on_delete=models.PROTECT,
      verbose_name='Тип абонемента',
  )
  status = models.CharField(
      'Статус',
      max_length=15,
      choices=Status.choices,
      default=Status.ACTIVE,
  )
  start_date = models.DateField('Дата начала', default=timezone.now)
  end_date = models.DateField('Дата окончания', blank=True)
  remaining_workouts = models.PositiveIntegerField(
      'Остаток занятий',
      null=True,
      blank=True,
  )
  remaining_freeze_days = models.PositiveIntegerField(
      'Остаток дней заморозки',
      default=0,
  )

  def save(self, *args, **kwargs):
    if not self.pk:
      self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
      self.remaining_freeze_days = self.plan.freeze_days_limit
      if self.plan.kind == SubscriptionPlan.PlanKind.PACKAGE:
        self.remaining_workouts = self.plan.workouts_count
      else:
        self.remaining_workouts = None
    super().save(*args, **kwargs)

  def __str__(self):
    return f'{self.client.full_name} — {self.plan.name} ({self.get_status_display()})'

class Freeze(models.Model):

  class Status(models.TextChoices):
    ACTIVE = 'active', 'Активна'
    COMPLETED = 'completed', 'Завершена'

  subscription = models.ForeignKey(
      Subscription,
      on_delete=models.CASCADE,
      related_name='freezes',
      verbose_name='Абонемент',
  )
  start_date = models.DateField('Дата начала', default=timezone.now)
  end_date = models.DateField('Дата окончания')
  status = models.CharField(
      'Статус',
      max_length=15,
      choices=Status.choices,
      default=Status.ACTIVE,
  )

  @property
  def days_count(self):
    return (self.end_date - self.start_date).days + 1

  def __str__(self):
    return f'Заморозка #{self.id} ({self.subscription})'

class WorkoutType(models.Model):
  name = models.CharField('Название направления', max_length=100)
  description = models.TextField('Описание', blank=True)
  duration_minutes = models.PositiveIntegerField(
      'Длительность (минут)', default=60
  )

  def __str__(self):
    return self.name


class Schedule(models.Model):
  class DayOfWeek(models.IntegerChoices):
    MONDAY = 1, 'Понедельник'
    TUESDAY = 2, 'Вторник'
    WEDNESDAY = 3, 'Среда'
    THURSDAY = 4, 'Четверг'
    FRIDAY = 5, 'Пятница'
    SATURDAY = 6, 'Суббота'
    SUNDAY = 7, 'Воскресенье'

  is_completed = models.BooleanField('Занятие проведено', default=False)
  workout_type = models.ForeignKey(
      WorkoutType,
      on_delete=models.CASCADE,
      related_name='schedules',
      verbose_name='Направление',
  )
  trainer = models.ForeignKey(
      User,
      on_delete=models.CASCADE,
      related_name='trainer_schedules',
      limit_choices_to={'role': User.Role.TRAINER},
      verbose_name='Тренер',
  )
  day_of_week = models.IntegerField(
      'День недели',
      choices=DayOfWeek.choices,
      default=DayOfWeek.MONDAY,
  )
  start_time = models.TimeField('Время начала')
  max_capacity = models.PositiveIntegerField('Максимум мест', default=10)

  class Meta:
    ordering = ['day_of_week', 'start_time']

  def get_next_date(self):
    today = timezone.localdate()
    now_time = timezone.localtime().time()
    target_weekday = self.day_of_week - 1
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0 and self.start_time <= now_time:
      days_ahead = 7
    return today + timedelta(days=days_ahead)

  @property
  def booked_count(self):
    next_date = self.get_next_date()
    return self.bookings.filter(
        status=Booking.Status.ACTIVE,
        workout_date=next_date,
    ).count()

  @property
  def available_seats(self):
    return max(0, self.max_capacity - self.booked_count)

  def __str__(self):
    return (
        f'{self.get_day_of_week_display()} {self.start_time:%H:%M} —'
        f' {self.workout_type.name}'
    )
  class Meta:
    ordering = ['start_time']

  @property
  def booked_count(self):
    return self.bookings.filter(status=Booking.Status.ACTIVE).count()

  @property
  def available_seats(self):
    return max(0, self.max_capacity - self.booked_count)

  def __str__(self):
    return f'{self.workout_type.name} — {self.start_time:%d.%m.%Y %H:%M}'


class Booking(models.Model):

  class Status(models.TextChoices):
    ACTIVE = 'active', 'Записан'
    ATTENDED = 'attended', 'Присутствовал'
    MISSED = 'missed', 'Не явился'
    CANCELED = 'canceled', 'Отменено'
    
  is_hidden_by_trainer = models.BooleanField('Скрыто тренером', default=False)
  
  client = models.ForeignKey(
      User,
      on_delete=models.CASCADE,
      related_name='bookings',
      limit_choices_to={'role': User.Role.CLIENT},
      verbose_name='Клиент',
  )
  schedule = models.ForeignKey(
      Schedule,
      on_delete=models.CASCADE,
      related_name='bookings',
      verbose_name='Слот расписания',
  )
  workout_date = models.DateField('Дата занятия')
  subscription = models.ForeignKey(
      Subscription,
      on_delete=models.CASCADE,
      related_name='bookings',
      verbose_name='Абонемент',
  )
  status = models.CharField(
      'Статус',
      max_length=15,
      choices=Status.choices,
      default=Status.ACTIVE,
  )
  created_at = models.DateTimeField('Дата записи', auto_now_add=True)

  def __str__(self):
    return f'{self.client.full_name} -> {self.schedule} ({self.workout_date})'
    