from django.db import models
from django.contrib.auth.models import User

class LightingLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    # Sensor data
    ambient_light_lux = models.FloatField()
    motion_detected = models.IntegerField()  # 0 atau 1
    day_of_week = models.IntegerField()      # 0-6
    time_of_day = models.IntegerField()      # 0-3
    weather_condition = models.IntegerField()# 0=cerah, 1=mendung/gelap

    # AI output
    lighting_action_class = models.IntegerField()  # 0=OFF,1=ON,2=DIM

    def __str__(self):
        action_map = {0: "OFF", 1: "ON", 2: "DIM"}
        return f"{self.user.username} - {self.timestamp} - {action_map.get(self.lighting_action_class, 'UNKNOWN')}"
