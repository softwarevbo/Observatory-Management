from django.db import models
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone


class TelescopeUserManager(models.Manager):
    def create_user(self, username, password=None, email=None, **extra_fields):
        user = self.model(username=username, email=email, **extra_fields)
        if password:
            user.password = make_password(password)
        user.save()
        return user


class TelescopeUser(models.Model):
    """
    Standalone isolated user database table exclusively for Telescope Control System (TCS).
    Roles in TCS are strictly TCS_ADMIN ('admin') and TCS_MEMBER ('operator').
    ROOT is the global system super admin and is NOT a TCS role.
    """
    objects = TelescopeUserManager()
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=128)
    role = models.CharField(
        max_length=50,
        default="operator",
        choices=[
            ("admin", "TCS Admin"),
            ("operator", "TCS Member"),
        ],
    )
    email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_telescope_admin = models.BooleanField(default=False)

    can_operate_vbt = models.BooleanField(default=True)
    can_operate_jcbt = models.BooleanField(default=True)
    can_operate_zeiss = models.BooleanField(default=True)
    can_operate_cassegrain = models.BooleanField(default=True)
    can_operate_schmidt = models.BooleanField(default=True)
    can_command_dome = models.BooleanField(default=True)
    can_trigger_exposures = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.username} ({'TCS Admin' if self.is_admin else 'TCS Member'})"

    class Meta:
        db_table = "telescope_telescopeuser"
        verbose_name = "Telescope User"
        verbose_name_plural = "Telescope Users"

    @property
    def canonical_role(self):
        from accounts.rbac import get_canonical_role
        return get_canonical_role(self)

    @property
    def display_name(self):
        return self.username

    @property
    def initials(self):
        return self.username[:2].upper()

    @property
    def is_admin(self):
        return self.is_telescope_admin or self.role == "admin"

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_superuser(self):
        return False

    @property
    def is_staff(self):
        return False

    @property
    def is_engineer(self):
        return self.is_admin

    @property
    def is_observer(self):
        return True

    @property
    def is_scientific_officer(self):
        return self.is_admin

    def can_access_telescope(self, telescope=None):
        return True

    def get_accessible_telescopes(self):
        return Telescope.objects.all()

    @property
    def is_superuser(self):
        return False

    @property
    def is_staff(self):
        return self.is_admin

    @property
    def can_access_pm(self):
        return False

    @property
    def can_access_inventory(self):
        return False

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False


class Telescope(models.Model):
    STATUS_ONLINE = 'online'
    STATUS_SLEWING = 'slewing'
    STATUS_TRACKING = 'tracking'
    STATUS_IDLE = 'idle'
    STATUS_MAINTENANCE = 'maintenance'
    STATUS_FAULT = 'fault'

    STATUS_CHOICES = [
        (STATUS_ONLINE, 'Online / Ready'),
        (STATUS_SLEWING, 'Slewing Target'),
        (STATUS_TRACKING, 'Tracking Target'),
        (STATUS_IDLE, 'Parked / Standby'),
        (STATUS_MAINTENANCE, 'Maintenance Mode'),
        (STATUS_FAULT, 'System Fault'),
    ]

    MOUNT_CHOICES = [
        ('alt_az', 'Alt-Azimuth Mount'),
        ('german_eq', 'German Equatorial Mount'),
        ('fork_eq', 'Fork Equatorial Mount'),
    ]

    DOME_CHOICES = [
        ('closed', 'Closed'),
        ('open', 'Open'),
        ('parked', 'Parked'),
        ('rotating', 'Rotating / Slewing'),
    ]

    id_name = models.CharField(max_length=50, unique=True, help_text="Short identifier, e.g., vbt_234")
    code = models.CharField(max_length=20, default="", blank=True, help_text="Short system code identifier.")
    name = models.CharField(max_length=150)
    aperture = models.CharField(max_length=50, default="2.0 Meter", blank=True, help_text="Aperture size")
    focal_ratio = models.CharField(max_length=10, default="f/9", blank=True, help_text="Focal ratio (e.g., f/9, f/11).")
    mount_type = models.CharField(max_length=20, choices=MOUNT_CHOICES, default='alt_az', blank=True)
    location = models.CharField(max_length=100, default="IIA VBO Site, Kavalur", blank=True)
    type = models.CharField(max_length=100, default="Reflector", blank=True, help_text="e.g., Reflector (Cassegrain / Prime Focus)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IDLE)
    current_target = models.CharField(max_length=200, default="None", blank=True)
    ra = models.CharField(max_length=50, default="00h 00m 00s", blank=True)
    dec = models.CharField(max_length=50, default="+00° 00′ 00″", blank=True)
    right_ascension = models.CharField(max_length=30, default="00h 00m 00.0s", blank=True)
    declination = models.CharField(max_length=30, default="+00° 00' 00.0\"", blank=True)
    epoch = models.CharField(max_length=10, default="J2000", blank=True)
    focus_position = models.FloatField(default=12.50, blank=True, help_text="Focuser position in mm.")
    dome = models.CharField(max_length=20, default="Closed", help_text="Open or Closed")
    dome_status = models.CharField(max_length=20, choices=DOME_CHOICES, default='closed')
    dome_azimuth = models.FloatField(default=0.0, help_text="Dome azimuth angle in degrees.")
    focus = models.CharField(max_length=50, default="Cassegrain", blank=True)
    instrument = models.CharField(max_length=100, default="None", blank=True)
    ccd_temp = models.CharField(max_length=50, default="Ambient", blank=True)
    primary_mirror_temp = models.FloatField(default=5.2, help_text="Mirror temperature in °C.")
    ambient_temp = models.FloatField(default=2.1, help_text="Ambient dome air temperature in °C.")
    humidity = models.FloatField(default=35.0, help_text="Relative humidity percentage.")
    tracking = models.CharField(max_length=20, default="Disabled", help_text="Enabled or Disabled")
    image = models.ImageField(upload_to="telescopes/", null=True, blank=True)
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="External image URL fallback")
    description = models.TextField(blank=True, help_text="Detailed information and specifications from VBO site")
    history = models.TextField(blank=True, help_text="Historical details")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = "telescopes_telescope"
        verbose_name = "Telescope"
        verbose_name_plural = "Telescopes"

    def save(self, *args, **kwargs):
        if not self.code and self.id_name:
            self.code = self.id_name.split("_")[0]
        elif not self.id_name and self.code:
            self.id_name = self.code
        if not self.right_ascension and self.ra:
            self.right_ascension = self.ra
        if not self.declination and self.dec:
            self.declination = self.dec
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class TelescopeLog(models.Model):
    EVENT_CHOICES = [
        ('slew', 'Slew Execution'),
        ('track_start', 'Tracking Started'),
        ('track_stop', 'Tracking Stopped'),
        ('dome_open', 'Dome Opened'),
        ('dome_close', 'Dome Closed'),
        ('fault', 'Hardware Fault'),
        ('maintenance', 'Maintenance Action'),
    ]

    telescope = models.ForeignKey(Telescope, on_delete=models.CASCADE, related_name="logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES, default='slew')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "telescopes_telescopelog"
        verbose_name = "Telescope Log"
        verbose_name_plural = "Telescope Logs"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.telescope.code}: {self.get_event_type_display()}"


class TelescopeDiscussion(models.Model):
    CATEGORY_CHOICES = [
        ('general', 'General Observatory Chat'),
        ('observation', 'Observation Logs & Targets'),
        ('hardware', 'Hardware & Mount Operations'),
        ('optics', 'Optics & Focusing'),
        ('software', 'Software & Plate Solving'),
        ('maintenance', 'Maintenance Notes'),
    ]

    telescope = models.ForeignKey(Telescope, on_delete=models.CASCADE, related_name="discussions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telescope_discussions")
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='general')
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "telescopes_telescopediscussion"
        verbose_name = "Telescope Discussion"
        verbose_name_plural = "Telescope Discussions"
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return f"[{self.telescope.code}] {self.title}"


class TelescopeDiscussionReply(models.Model):
    discussion = models.ForeignKey(TelescopeDiscussion, on_delete=models.CASCADE, related_name="replies")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telescope_discussion_replies")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "telescopes_telescopediscussionreply"
        verbose_name = "Telescope Discussion Reply"
        verbose_name_plural = "Telescope Discussion Replies"
        ordering = ["created_at"]

    def __str__(self):
        return f"Reply by @{self.user.username} on '{self.discussion.title}'"


class Instrument(models.Model):
    TYPE_SPECTROGRAPH = 'spectrograph'
    TYPE_CCD_IMAGER = 'ccd_imager'
    TYPE_IR_CAMERA = 'ir_camera'
    TYPE_PHOTOMETER = 'photometer'
    TYPE_POLARIMETER = 'polarimeter'
    TYPE_ADAPTIVE_OPTICS = 'adaptive_optics'

    TYPE_CHOICES = [
        (TYPE_SPECTROGRAPH, 'Optical Spectrograph'),
        (TYPE_CCD_IMAGER, 'Direct CCD Imager'),
        (TYPE_IR_CAMERA, 'Near-Infrared Camera'),
        (TYPE_PHOTOMETER, 'Fast Photometer'),
        (TYPE_POLARIMETER, 'Imaging Polarimeter'),
        (TYPE_ADAPTIVE_OPTICS, 'Adaptive Optics Unit'),
    ]

    STATUS_ONLINE = 'online'
    STATUS_CALIBRATING = 'calibrating'
    STATUS_STANDBY = 'standby'
    STATUS_MAINTENANCE = 'maintenance'
    STATUS_ERROR = 'error'

    STATUS_CHOICES = [
        (STATUS_ONLINE, 'Online / Science Ready'),
        (STATUS_CALIBRATING, 'Running Calibration'),
        (STATUS_STANDBY, 'Thermal Standby'),
        (STATUS_MAINTENANCE, 'Maintenance Lock'),
        (STATUS_ERROR, 'Cryo/Sensor Alarm'),
    ]

    name = models.CharField(max_length=150, help_text="Full Instrument Name.")
    code = models.CharField(max_length=20, unique=True, help_text="Short identifier code.")
    instrument_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_SPECTROGRAPH)
    telescope = models.ForeignKey(Telescope, on_delete=models.CASCADE, related_name="instruments", help_text="Mounted host telescope.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_STANDBY)

    detector_temp = models.FloatField(default=-110.5, help_text="Current CCD detector temperature (°C).")
    setpoint_temp = models.FloatField(default=-115.0, help_text="Target cooling setpoint (°C).")
    vacuum_pressure = models.FloatField(default=1.2e-6, help_text="Dewar vacuum pressure in mbar.")
    cooling_power_percent = models.FloatField(default=68.5, help_text="Cooler duty cycle percentage.")

    gain = models.FloatField(default=1.5, help_text="CCD gain in e-/ADU.")
    binning = models.CharField(max_length=10, default="1x1", help_text="Pixel binning mode (e.g., 1x1, 2x2).")
    readout_speed = models.CharField(max_length=50, default="100 kHz (Low Noise)")
    active_filter = models.CharField(max_length=50, default="V (550nm)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "instruments_instrument"
        verbose_name = "Instrument"
        verbose_name_plural = "Instruments"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name} [{self.get_status_display()}]"


class InstrumentSensor(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="sensors")
    sensor_name = models.CharField(max_length=100)
    unit = models.CharField(max_length=20, default="°C")
    current_value = models.FloatField()
    min_warning = models.FloatField()
    max_warning = models.FloatField()

    class Meta:
        db_table = "instruments_instrumentsensor"
        verbose_name = "Instrument Sensor"
        verbose_name_plural = "Instrument Sensors"

    def __str__(self):
        return f"{self.instrument.code} - {self.sensor_name}: {self.current_value} {self.unit}"

    @property
    def is_warning(self):
        return self.current_value < self.min_warning or self.current_value > self.max_warning


class TelemetryLog(models.Model):
    STATUS_NORMAL = 'normal'
    STATUS_WARNING = 'warning'
    STATUS_CRITICAL = 'critical'

    FLAG_CHOICES = [
        (STATUS_NORMAL, 'Normal'),
        (STATUS_WARNING, 'Warning'),
        (STATUS_CRITICAL, 'Critical Alarm'),
    ]

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="telemetry_logs")
    sensor_name = models.CharField(max_length=100)
    value = models.FloatField()
    unit = models.CharField(max_length=20, default="°C")
    status_flag = models.CharField(max_length=20, choices=FLAG_CHOICES, default=STATUS_NORMAL)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "instruments_telemetrylog"
        verbose_name = "Telemetry Log"
        verbose_name_plural = "Telemetry Logs"
        ordering = ["-timestamp"]


class FilterWheelConfig(models.Model):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="filter_wheel")
    slot_number = models.PositiveIntegerField()
    filter_name = models.CharField(max_length=50)
    central_wavelength = models.FloatField(help_text="Central wavelength in nm.")
    bandwidth = models.FloatField(help_text="FWHM Bandwidth in nm.")

    class Meta:
        db_table = "instruments_filterwheelconfig"
        verbose_name = "Filter Wheel Slot"
        verbose_name_plural = "Filter Wheel Configurations"
        unique_together = ('instrument', 'slot_number')
        ordering = ['slot_number']

    def __str__(self):
        return f"Slot #{self.slot_number}: {self.filter_name} ({self.central_wavelength}nm)"


class ObservationTarget(models.Model):
    OBJECT_CHOICES = [
        ('galaxy', 'Galaxy'),
        ('nebula', 'Nebula / HII Region'),
        ('star', 'Star / Star Cluster'),
        ('exoplanet', 'Exoplanet Host'),
        ('solar_system', 'Solar System Object'),
        ('quasar', 'Quasar / AGN'),
        ('other', 'Other / Unknown'),
    ]

    name = models.CharField(max_length=150)
    catalog_id = models.CharField(max_length=50, blank=True, help_text="Catalog identifier (e.g. NGC 224, HD 209458).")
    right_ascension = models.CharField(max_length=30, blank=True, default="00h 00m 00.0s")
    declination = models.CharField(max_length=30, blank=True, default="+00° 00' 00.0\"")
    object_class = models.CharField(max_length=20, choices=OBJECT_CHOICES, default='star')
    magnitude = models.FloatField(null=True, blank=True, help_text="Visual magnitude.")
    distance_ly = models.FloatField(null=True, blank=True, help_text="Estimated distance in light-years.")
    observation_date = models.DateField(null=True, blank=True)
    recommended_filter = models.CharField(max_length=50, default="V (550nm)")
    epoch = models.CharField(max_length=20, default="J2000.0")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "observations_observationtarget"
        verbose_name = "Observation Target"
        verbose_name_plural = "Observation Targets"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.catalog_id or self.get_object_class_display()})"


class ExposureRunLog(models.Model):
    SKY_CHOICES = [
        ('photometric', 'Photometric'),
        ('clear', 'Clear'),
        ('thin_cloud', 'Thin Clouds'),
        ('variable', 'Variable'),
    ]

    target = models.ForeignKey(ObservationTarget, on_delete=models.CASCADE, related_name="runs", null=True, blank=True)
    fits_file_ref = models.CharField(max_length=200, blank=True)
    signal_to_noise = models.FloatField(null=True, blank=True)
    seeing_arcsec = models.FloatField(null=True, blank=True)
    sky_transparency = models.CharField(max_length=20, choices=SKY_CHOICES, default='clear')
    airmass = models.FloatField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "observations_exposurerunlog"
        verbose_name = "Exposure Run Log"
        verbose_name_plural = "Exposure Run Logs"
        ordering = ['-started_at']


class UnifiedLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    telescope = models.CharField(max_length=20, default='vbt')
    date = models.DateField(default=timezone.now)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "observations_unifiedlog"
        verbose_name = "Unified Log"
        verbose_name_plural = "Unified Logs"
        ordering = ['-date']
        unique_together = ('telescope', 'date')

    def __str__(self):
        return f"{self.telescope.upper()} Log for {self.date}"


class MaintenanceTicket(models.Model):
    SEVERITY_CRITICAL = 'critical'
    SEVERITY_HIGH = 'high'
    SEVERITY_MEDIUM = 'medium'
    SEVERITY_LOW = 'low'

    SEVERITY_CHOICES = [
        (SEVERITY_CRITICAL, 'CRITICAL - System Halt'),
        (SEVERITY_HIGH, 'HIGH - Science Impact'),
        (SEVERITY_MEDIUM, 'MEDIUM - Degraded Mode'),
        (SEVERITY_LOW, 'LOW - Routine / Scheduled'),
    ]

    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CLOSED, 'Closed'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    instrument = models.ForeignKey(Instrument, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets")
    telescope = models.ForeignKey(Telescope, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets")
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="reported_tickets")
    assigned_engineer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets")
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "maintenance_maintenanceticket"
        verbose_name = "Maintenance Ticket"
        verbose_name_plural = "Maintenance Tickets"
        ordering = ['-created_at']

    def __str__(self):
        target = self.instrument or self.telescope
        return f"[{self.get_severity_display()}] {self.title} → {target}"

    @property
    def severity_color(self):
        return {
            'critical': '#ef4444',
            'high': '#f97316',
            'medium': '#f59e0b',
            'low': '#10b981',
        }.get(self.severity, '#64748b')


class CalibrationLog(models.Model):
    CAL_TYPE_CHOICES = [
        ('bias', 'Bias Frame'),
        ('dark', 'Dark Frame'),
        ('flat', 'Flat Field'),
        ('wavelength', 'Wavelength Calibration Lamp'),
        ('standard_star', 'Standard Star Flux Calibration'),
        ('focus', 'Focus / PSF Calibration'),
        ('pointing', 'Pointing Model Calibration'),
    ]

    CAL_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="calibrations")
    calibration_type = models.CharField(max_length=30, choices=CAL_TYPE_CHOICES)
    standard_lamp_or_target = models.CharField(max_length=100, blank=True)
    engineer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="calibrations_run")
    status = models.CharField(max_length=20, choices=CAL_STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)
    in_progress_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "maintenance_calibrationlog"
        verbose_name = "Calibration Log"
        verbose_name_plural = "Calibration Logs"
        ordering = ['-executed_at']

    def save(self, *args, **kwargs):
        if self.status == 'running' and not self.in_progress_at:
            self.in_progress_at = timezone.now()
        elif self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status == 'failed' and not self.failed_at:
            self.failed_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.instrument.code} | {self.get_calibration_type_display()} [{self.get_status_display()}]"


class PlateSolveRun(models.Model):
    STATUS_IDLE = 'idle'
    STATUS_SOLVING = 'solving'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_IDLE, 'Idle'),
        (STATUS_SOLVING, 'Solving in Progress'),
        (STATUS_SUCCESS, 'Solved Successfully'),
        (STATUS_FAILED, 'Solving Failed'),
    ]

    telescope = models.ForeignKey(Telescope, on_delete=models.SET_NULL, null=True, blank=True, related_name="plate_solves")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    target_ra_deg = models.FloatField(default=0.0)
    target_dec_deg = models.FloatField(default=0.0)
    fov_deg = models.FloatField(default=20.0)

    solved_ra_deg = models.FloatField(null=True, blank=True)
    solved_dec_deg = models.FloatField(null=True, blank=True)
    pixel_scale_arcsec = models.FloatField(default=35.15)
    rotation_angle_deg = models.FloatField(default=0.0)
    matched_stars_count = models.IntegerField(default=0)
    solution_time_sec = models.FloatField(default=0.42)
    ra_error_arcmin = models.FloatField(default=0.0)
    dec_error_arcmin = models.FloatField(default=0.0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IDLE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "platesolver_platesolverun"
        verbose_name = "Plate Solve Run"
        verbose_name_plural = "Plate Solve Runs"
        ordering = ['-created_at']

    def __str__(self):
        return f"Plate Solve #{self.pk} - {self.get_status_display()}"


class SiteFeedback(models.Model):
    CATEGORY_CHOICES = [
        ('bug_error', 'Bug / System Error'),
        ('ui_ux', 'UI / UX Design Issue'),
        ('feature_req', 'Feature Request'),
        ('performance', 'System Performance'),
        ('hardware_error', 'Hardware & Telemetry Error'),
        ('other_general', 'Other / General Feedback'),
    ]

    STATUS_CHOICES = [
        ('new', 'New'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedbacks')
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other_general')
    rating = models.IntegerField(default=5, blank=True, null=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    admin_response = models.TextField(blank=True, null=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_sitefeedback"
        verbose_name = "Site Feedback"
        verbose_name_plural = "Site Feedbacks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.category}] {self.subject}"
