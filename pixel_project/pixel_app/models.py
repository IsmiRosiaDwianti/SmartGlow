from django.db import models
from django.contrib.auth.models import User

class LightingLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Sensor data
    ambient_light_lux = models.FloatField()
    motion_detected = models.IntegerField(default=0)  # 0 atau 1
    day_of_week = models.IntegerField()          # 0-6
    time_of_day = models.IntegerField()          # 0-3
    weather_condition = models.IntegerField()    # encoding
    
    # ✅ HANYA SATU FIELD - konsisten dengan dataset ML
    lighting_action_class = models.IntegerField(default=0)  # 0,1,2

    def __str__(self):
        action_map = {0: "OFF", 1: "ON", 2: "DIM"}
        action_text = action_map.get(self.lighting_action_class, "UNKNOWN")
        return f"{self.user.username} - {self.timestamp} - {action_text}"