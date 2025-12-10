from rest_framework import serializers
from .models import LightingLog

class LightingLogSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = LightingLog
        fields = [
            'id',
            'user',
            'timestamp',

            # sensor input
            'ambient_light_lux',
            'motion_detected',
            'day_of_week',
            'time_of_day',
            'weather_condition',

            # output AI
            'lighting_action_class',

            # mode & sumber
            'control_mode',
            'is_manual',
            'source',

            # manual override (opsional)
            'manual_command',
        ]
