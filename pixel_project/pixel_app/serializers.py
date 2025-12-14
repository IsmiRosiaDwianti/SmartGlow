from rest_framework import serializers
from .models import LightingLog

class LightingLogSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    display_lux = serializers.SerializerMethodField()

    class Meta:
        model = LightingLog
        fields = [
            'id',
            'user',
            'timestamp',

            # sensor input
            'ambient_light_lux',
            'display_lux',          # field tambahan untuk tampilan web
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

    def get_display_lux(self, obj):
        return "" if obj.ambient_light_lux is None else obj.ambient_light_lux
