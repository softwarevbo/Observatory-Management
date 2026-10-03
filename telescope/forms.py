from django import forms
from .models import (
    Telescope, TelescopeDiscussion, TelescopeDiscussionReply,
    Instrument, ObservationTarget, MaintenanceTicket, CalibrationLog,
    SiteFeedback, TelescopeUser
)


class TelescopeForm(forms.ModelForm):
    class Meta:
        model = Telescope
        fields = ['name', 'code', 'aperture', 'focal_ratio', 'mount_type', 'location', 'focus_position', 'status', 'description', 'history']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'aperture': forms.TextInput(attrs={'class': 'form-control'}),
            'focal_ratio': forms.TextInput(attrs={'class': 'form-control'}),
            'mount_type': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'focus_position': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'history': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class SlewTargetForm(forms.Form):
    target_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. M31 / NGC 224'}))
    right_ascension = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12h 30m 45.2s'}))
    declination = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+45° 15\' 22.0"'}))
    epoch = forms.CharField(max_length=10, initial="J2000", widget=forms.TextInput(attrs={'class': 'form-control'}))


class TelescopeDiscussionForm(forms.ModelForm):
    class Meta:
        model = TelescopeDiscussion
        fields = ['telescope', 'category', 'title', 'content', 'is_pinned']
        widgets = {
            'telescope': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Discussion topic / title...'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Write message or log details for this telescope...'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TelescopeDiscussionReplyForm(forms.ModelForm):
    class Meta:
        model = TelescopeDiscussionReply
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Write your reply...'}),
        }


class InstrumentForm(forms.ModelForm):
    class Meta:
        model = Instrument
        fields = [
            'name', 'code', 'instrument_type', 'telescope', 'status',
            'detector_temp', 'setpoint_temp', 'vacuum_pressure', 'cooling_power_percent',
            'gain', 'binning', 'readout_speed', 'active_filter'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'instrument_type': forms.Select(attrs={'class': 'form-select'}),
            'telescope': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'detector_temp': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'setpoint_temp': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'vacuum_pressure': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0000001'}),
            'cooling_power_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'gain': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'binning': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1x1'}),
            'readout_speed': forms.TextInput(attrs={'class': 'form-control'}),
            'active_filter': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ObservationTargetForm(forms.ModelForm):
    class Meta:
        model = ObservationTarget
        fields = ['name', 'catalog_id', 'right_ascension', 'declination', 'object_class', 'magnitude', 'distance_ly', 'observation_date', 'recommended_filter', 'epoch', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'catalog_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NGC 224 / HD 209458'}),
            'right_ascension': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00h 42m 44.3s'}),
            'declination': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+41° 16\' 09"'}),
            'object_class': forms.Select(attrs={'class': 'form-select'}),
            'magnitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'distance_ly': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'observation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'recommended_filter': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'V (550nm) / H-alpha / Iodine Cell'}),
            'epoch': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'J2000.0'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class MaintenanceTicketForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model
        from .models import TelescopeUser
        User = get_user_model()
        
        # Filter assigned_engineer queryset to only include TCS engineers/staff and superusers (excluding PM users)
        tcs_user_pks = list(TelescopeUser.objects.values_list('pk', flat=True))
        tcs_engineers = User.objects.filter(role__in=['TCS_ADMIN', 'TCS_MEMBER', 'ROOT', 'engineer', 'admin', 'scientific_officer', 'observer'])
        if not tcs_engineers.exists():
            tcs_engineers = User.objects.filter(is_superuser=True)
            
        self.fields['assigned_engineer'].queryset = tcs_engineers

    class Meta:
        model = MaintenanceTicket
        fields = ['title', 'description', 'severity', 'instrument', 'telescope', 'assigned_engineer']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'instrument': forms.Select(attrs={'class': 'form-select'}),
            'telescope': forms.Select(attrs={'class': 'form-select'}),
            'assigned_engineer': forms.Select(attrs={'class': 'form-select'}),
        }


class ResolveTicketForm(forms.ModelForm):
    class Meta:
        model = MaintenanceTicket
        fields = ['status', 'resolution_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'resolution_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class CalibrationLogForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            accessible_telescopes = user.get_accessible_telescopes()
            self.fields['instrument'].queryset = Instrument.objects.filter(telescope__in=accessible_telescopes)

    class Meta:
        model = CalibrationLog
        fields = ['instrument', 'calibration_type', 'standard_lamp_or_target', 'status', 'notes']
        widgets = {
            'instrument': forms.Select(attrs={'class': 'form-select'}),
            'calibration_type': forms.Select(attrs={'class': 'form-select'}),
            'standard_lamp_or_target': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class SiteFeedbackForm(forms.ModelForm):
    class Meta:
        model = SiteFeedback
        fields = ['category', 'subject', 'message', 'name', 'email', 'is_public']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief title of bug, issue, or feedback'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the bug, error details, steps to reproduce, or feedback...'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name (optional)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Contact Email (optional)'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TelescopeUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Password"
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirm Password"
    )

    class Meta:
        model = TelescopeUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'department', 'designation', 'phone', 'assigned_telescopes')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'assigned_telescopes': forms.CheckboxSelectMultiple(),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', "Passwords do not match.")
        return cleaned_data


class TelescopeAdminEditForm(forms.ModelForm):
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to keep unchanged'}),
        help_text="Optional: Reset user's password."
    )

    class Meta:
        model = TelescopeUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'department', 'designation', 'phone', 'is_active', 'assigned_telescopes')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'assigned_telescopes': forms.CheckboxSelectMultiple(),
        }


class SiteFeedbackForm(forms.ModelForm):
    class Meta:
        model = SiteFeedback
        fields = ['category', 'subject', 'message', 'name', 'email', 'is_public']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief title of bug, issue, or feedback'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the bug, error details, steps to reproduce, or feedback...'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name (optional)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Contact Email (optional)'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


