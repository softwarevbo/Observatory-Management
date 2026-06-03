from django.db import models

class Telescope(models.Model):
    STATUS_CHOICES = [
        ("observing", "Observing"),
        ("idle", "Idle / Ready"),
        ("maintenance", "Under Maintenance"),
    ]

    id_name = models.CharField(max_length=50, unique=True, help_text="Short identifier, e.g., vbt_234")
    name = models.CharField(max_length=100)
    aperture = models.CharField(max_length=50, help_text="e.g., 2.34 Meter")
    type = models.CharField(max_length=100, help_text="e.g., Reflector (Cassegrain / Prime Focus)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="idle")
    current_target = models.CharField(max_length=200, default="None", blank=True)
    ra = models.CharField(max_length=50, default="00h 00m 00s", blank=True)
    dec = models.CharField(max_length=50, default="+00° 00′ 00″", blank=True)
    dome = models.CharField(max_length=20, default="Closed", help_text="Open or Closed")
    focus = models.CharField(max_length=50, default="Cassegrain", blank=True)
    instrument = models.CharField(max_length=100, default="None", blank=True)
    ccd_temp = models.CharField(max_length=50, default="Ambient", blank=True)
    tracking = models.CharField(max_length=20, default="Disabled", help_text="Enabled or Disabled")
    image = models.ImageField(upload_to="telescopes/", null=True, blank=True)
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="External image URL fallback")
    description = models.TextField(blank=True, help_text="Detailed information and specifications from VBO site")
    history = models.TextField(blank=True, help_text="Historical details")

    def __str__(self):
        return self.name
