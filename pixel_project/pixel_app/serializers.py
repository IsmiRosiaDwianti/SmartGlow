from rest_framework import serializers
from .models import LightingLog

class LightingLogSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = LightingLog
        fields = [
            'id','user','timestamp',
            'ambient_light_lux','motion_detected','day_of_week','time_of_day',
            'weather_condition','lighting_action_class'
        ]
