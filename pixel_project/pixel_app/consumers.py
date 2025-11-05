import json
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import LightingLog
from .ai_model import predict_lighting_action

class SensorDataConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        all_data = await self.get_all_sensor_data()
        if all_data:
            await self.send(text_data=json.dumps(all_data))

    async def disconnect(self, close_code):
        print("🔴 WebSocket disconnected")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            user = await self.get_default_user()
            saved_data = await self.process_and_save_sensor_data(data, user)

            await self.send(text_data=json.dumps({
                'type': 'sensor_update',
                'data': [saved_data]
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({'type':'error','error': str(e)}))

    @database_sync_to_async
    def get_all_sensor_data(self):
        all_logs = LightingLog.objects.all().order_by('timestamp')
        data_list = [self.format_log(log) for log in all_logs]
        return {'type':'initial_data','data':data_list} if data_list else None

    @database_sync_to_async
    def process_and_save_sensor_data(self, data, user):
        lux = float(data.get('ambient_light_lux', 0))
        motion = self.estimate_motion(lux)
        weather_condition = self.estimate_weather(lux)
        now = datetime.now()
        time_of_day = self.estimate_time_of_day(now.hour)
        day_of_week = now.weekday()

        lighting_action_class = predict_lighting_action(lux, motion, day_of_week, time_of_day, weather_condition)
        if lighting_action_class not in [0,1,2]:
            lighting_action_class = 0

        log_entry = LightingLog.objects.create(
            user=user,
            ambient_light_lux=lux,
            motion_detected=motion,
            day_of_week=day_of_week,
            time_of_day=time_of_day,
            weather_condition=weather_condition,
            lighting_action_class=lighting_action_class
        )
        return self.format_log(log_entry)

    @database_sync_to_async
    def get_default_user(self):
        return User.objects.first()

    # ================= LOGIKA GENERATE FITUR =================
    def estimate_motion(self, lux: float) -> int:
        return 1 if lux < 100 else 0

    def estimate_weather(self, lux: float) -> int:
        return 0 if lux > 200 else 1

    def estimate_time_of_day(self, hour: int) -> int:
        if 6 <= hour < 12:
            return 1
        elif 12 <= hour < 18:
            return 2
        elif 18 <= hour < 24:
            return 3
        else:
            return 0

    def format_log(self, log):
        return {
            'ambient_light_lux': log.ambient_light_lux,
            'motion_detected': log.motion_detected,
            'day_of_week': log.day_of_week,
            'time_of_day': log.time_of_day,
            'weather_condition': log.weather_condition,
            'lighting_action_class': log.lighting_action_class,
            'timestamp': log.timestamp.isoformat()
        }
