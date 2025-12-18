from django.db import models
from django.contrib.auth.models import User

class LightingLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)

    ambient_light_lux = models.FloatField()
    motion_detected = models.IntegerField()
    day_of_week = models.IntegerField()
    time_of_day = models.IntegerField()
    weather_condition = models.IntegerField()

    lighting_action_class = models.IntegerField() # 0=OFF, 1=ON, 2=DIM
    source = models.CharField(max_length=20, default='iot')
    
    # ✅ TAMBAHKAN FIELD INI
    control_mode = models.CharField(
        max_length=10, 
        choices=[('AUTO', 'Auto'), ('MANUAL', 'Manual')],
        default='AUTO'
    )
    is_manual = models.BooleanField(default=False)
    
    # ✅ OPTIONAL: Tambah untuk manual command
    manual_command = models.IntegerField(null=True, blank=True)  # 0, 1, 2

    def __str__(self):
        action_map = {0: "OFF", 1: "ON", 2: "DIM"}
        user_display = self.user.username if self.user else "IoT Device"
        mode_display = f" [{self.control_mode}]" if hasattr(self, 'control_mode') else ""
        return f"{user_display} - {self.timestamp} - {action_map.get(self.lighting_action_class, 'UNKNOWN')}{mode_display}"

    class Meta:
        ordering = ['-timestamp']  # Urutkan terbaru dulu


# ===========================
# MODEL BARU UNTUK CONTROL
# ===========================
class LightState(models.Model):
    MODE_CHOICES = (
        ('AUTO', 'AUTO'),
        ('MANUAL', 'MANUAL'),
    )
    STATUS_CHOICES = (
        ('ON', 'ON'),
        ('OFF', 'OFF'),
    )

    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='AUTO')
    status = models.CharField(max_length=5, choices=STATUS_CHOICES, default='OFF')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.mode} - {self.status}"
    
    class Meta:
        verbose_name = "Light State"
        verbose_name_plural = "Light States"