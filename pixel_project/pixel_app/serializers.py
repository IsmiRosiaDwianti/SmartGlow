from rest_framework import serializers
from .models import LightingLog

class LightingLogSerializer(serializers.ModelSerializer):
    # Field 'user' hanya untuk dibaca (otomatis dari user login)
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = LightingLog
        fields = [
            'id',
            'user', 
            'timestamp',
            'ambient_light_lux',
            'motion_detected',
            'day_of_week',          # ✅ TAMBAH INI (yang missing)
            'time_of_day',          # ✅ TAMBAH INI (yang missing)
            'weather_condition',
            'lighting_action_class', # ✅ PAKAI INI, BUKAN lighting_action
        ]