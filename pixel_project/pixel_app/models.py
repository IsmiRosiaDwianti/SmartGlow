from django.db import models
from django.contrib.auth.models import User

class LightingLog(models.Model):
    # User bisa kosong (null=True, blank=True) supaya alat IoT tetap bisa kirim data
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)

    # Sensor data
    ambient_light_lux = models.FloatField()
    motion_detected = models.IntegerField()       # 0 atau 1
    day_of_week = models.IntegerField()           # 0-6
    time_of_day = models.IntegerField()           # 0-3
    weather_condition = models.IntegerField()     # 0=cerah, 1=mendung/gelap

    # AI output
    lighting_action_class = models.IntegerField() # 0=OFF, 1=ON, 2=DIM

    # (Opsional) asal data, biar tahu dari IoT atau Web Dashboard
    source = models.CharField(max_length=20, default='iot')

    def __str__(self):
        action_map = {0: "OFF", 1: "ON", 2: "DIM"}
        user_display = self.user.username if self.user else "IoT Device"
        return f"{user_display} - {self.timestamp} - {action_map.get(self.lighting_action_class, 'UNKNOWN')}"
