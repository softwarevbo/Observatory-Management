from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import User
from inventory.models import Branch

"""
This module contains Django Forms for handling authentication and user administration tasks.
It covers:
1. User login credentials validation.
2. User account registration (creation form) with validation for unique fields and matching passwords.
3. User account modification (edit form) for system admin actions.
4. Administrative password resets.
5. Self-service password changes verifying current credentials.
"""

class LoginForm(AuthenticationForm):
    """
    Form for validating user login attempts.
    Extends Django's standard AuthenticationForm to customize widgets and styling.
    """
    # Overriding the username input field widget to apply Bootstrap classes & placeholder
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your username",
                "autofocus": True, # Focus cursor automatically on page load
            }
        )
    )
    # Overriding the password input field widget to render as dots/asterisks
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your password",
            }
        )
    )


class UserCreateForm(forms.ModelForm):
    """
    ModelForm used by administrators to create a new User account.
    A ModelForm automatically generates fields based on a database model (User).
    """
    # Manually defined fields for passwords to handle entry & confirm verification
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
        """
        Configuration for the ModelForm.
        Link it to the User model and specify fields to include.
        """
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
        ]
        # Customizing CSS styling and attributes for automatically generated inputs
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
        }

    def clean_username(self):
        """
        Custom validation hook: checks if the username is unique in the database.
        Django runs all methods starting with 'clean_<fieldname>' during `form.is_valid()`.
        """
        username = self.cleaned_data.get("username")
        from django.contrib.auth import get_user_model
        from inventory.models import InventoryUser
        User = get_user_model()
        if User.objects.filter(username=username).exists() or InventoryUser.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        """
        Custom validation hook: checks if the email is unique in the database.
        """
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_password2(self):
        """
        Custom validation hook: verifies that both password entries match.
        """
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")
        return p2

    def save(self, commit=True):
        """
        Overrides the save method to correctly hash the user password.
        Saving a raw text password directly makes it insecure and breaks login.
        """
        user = super().save(commit=False)
        # set_password hashes the text before storing it
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    """
    ModelForm used by administrators to modify an existing User profile.
    Notice we exclude the username field to prevent changing logins once established.
    """
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
        }


class AdminPasswordResetForm(forms.Form):
    """
    Regular Django Form (not modelform) used by admins to change someone else's password.
    Requires inputting the new password twice and checking if they match.
    """
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
        """Verifies that the double-entry passwords match."""
        p1 = self.cleaned_data.get("new_password1")
        p2 = self.cleaned_data.get("new_password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")
        return p2


class UserSelfPasswordChangeForm(forms.Form):
    """
    Form used by users to change their own password.
    It requires confirming their current password before letting them set a new one.
    """
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
        """
        Overriding constructor to accept the user object as an argument.
        We need reference to the user to check their current password correctness.
        """
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        """
        Validates that the entered current password matches the active user's actual password.
        Uses Django's built-in `check_password()` method which does safe cryptographic hash verification.
        """
        pwd = self.cleaned_data.get("current_password")
        if not self.user.check_password(pwd):
            raise ValidationError("Current password is incorrect.")
        return pwd

    def clean_new_password2(self):
        """Validates that the double-entered new passwords match."""
        p1 = self.cleaned_data.get("new_password1")
        p2 = self.cleaned_data.get("new_password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")
        return p2
