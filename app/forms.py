from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from .models import User


class RegistrationForm(UserCreationForm):

  class Meta:
    model = User
    fields = ('full_name', 'email', 'phone', 'price')

  def save(self, commit=True):
    user = super().save(commit=False)
    user.username = self.cleaned_data['email']
    user.role = User.Role.CLIENT
    user.price = User.price
    
    if commit:
      user.save()
    return user


class LoginForm(forms.Form):
  email = forms.EmailField(label='Email')
  password = forms.CharField(label='Пароль', widget=forms.PasswordInput)

  def __init__(self, request=None, *args, **kwargs):
    self.request = request
    self.user = None
    super().__init__(*args, **kwargs)

  def clean(self):
    cleaned_data = super().clean()
    email = cleaned_data.get('email')
    password = cleaned_data.get('password')

    if email and password:
      self.user = authenticate(self.request, username=email, password=password)
      if self.user is None:
        raise forms.ValidationError('Неверный email или пароль.')
      if not self.user.is_active:
        raise forms.ValidationError('Аккаунт заблокирован.')
    return cleaned_data

from django import forms
from .models import Freeze


class FreezeForm(forms.Form):
  days = forms.IntegerField(label='Количество дней заморозки', min_value=1)

  def __init__(self, subscription, *args, **kwargs):
    self.subscription = subscription
    super().__init__(*args, **kwargs)
    self.fields['days'].max_value = subscription.remaining_freeze_days

  def clean_days(self):
    days = self.cleaned_data['days']
    if days > self.subscription.remaining_freeze_days:
      raise forms.ValidationError(
          f'Доступно максимум {self.subscription.remaining_freeze_days} дн.'
      )
    return days