from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import User
from inventory.models import Branch


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your username",
                "autofocus": True,
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your password",
            }
        )
    )


class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        min_length=6,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Min. 6 characters",
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Re-enter password",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "team",
            "designation",
            "phone",
            "avatar_color",
            "can_access_pm",
            "can_access_inventory",
            "can_access_telescope",
            "inventory_branch",
        ]
        widgets = {
            "username": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. john_doe"}
            ),
            "first_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "First name"}
            ),
            "last_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Last name"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "user@company.com"}
            ),
            "role": forms.Select(attrs={"class": "form-control"}),
            "team": forms.Select(attrs={"class": "form-control"}),
            "designation": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. Senior Engineer"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+91 99999 99999"}
            ),
            "avatar_color": forms.TextInput(
                attrs={"class": "form-control", "type": "color"}
            ),
            "can_access_pm": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "can_access_inventory": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "can_access_telescope": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "inventory_branch": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "role",
            "team",
            "designation",
            "phone",
            "avatar_color",
            "is_active",
            "can_access_pm",
            "can_access_inventory",
            "can_access_telescope",
            "inventory_branch",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-control"}),
            "team": forms.Select(attrs={"class": "form-control"}),
            "designation": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "avatar_color": forms.TextInput(
                attrs={"class": "form-control", "type": "color"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "can_access_pm": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "can_access_inventory": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "can_access_telescope": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "inventory_branch": forms.Select(attrs={"class": "form-control"}),
        }


class AdminPasswordResetForm(forms.Form):
    new_password1 = forms.CharField(
        label="New Password",
        min_length=6,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New password (min. 6 chars)",
                "autocomplete": "new-password",
            }
        ),
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm new password",
                "autocomplete": "new-password",
            }
        ),
    )

    def clean_new_password2(self):
        p1 = self.cleaned_data.get("new_password1")
        p2 = self.cleaned_data.get("new_password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")
        return p2


class UserSelfPasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Your current password"}
        ),
    )
    new_password1 = forms.CharField(
        label="New Password",
        min_length=6,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New password (min. 6 chars)",
            }
        ),
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm new password"}
        ),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        pwd = self.cleaned_data.get("current_password")
        if not self.user.check_password(pwd):
            raise ValidationError("Current password is incorrect.")
        return pwd

    def clean_new_password2(self):
        p1 = self.cleaned_data.get("new_password1")
        p2 = self.cleaned_data.get("new_password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")
        return p2
