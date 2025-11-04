import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import LightingLog
from .ai_model import predict_lighting_action

class SensorDataConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        print("🟢 WebSocket connected")

        # Kirim semua data history
        all_data = await self.get_all_sensor_data()
        if all_data:
            await self.send(text_data=json.dumps(all_data))
            print(f"✅ Sent {len(all_data['data'])} historical data points")

    async def disconnect(self, close_code):
        print("🔴 WebSocket disconnected")

    async def receive(self, text_data):
        """
        Terima data sensor, proses dengan AI, simpan & kirim balik
        """
        try:
            data = json.loads(text_data)
            print("📨 Data received:", data)
            
            # Dapatkan user default
            user = await self.get_default_user()

            # Proses data dan simpan ke database
            saved_data = await self.process_and_save_sensor_data(data, user)
            
            print(f"🎯 AI Decision: {saved_data['lighting_action_class']}")
            
            # ✅ KIRIM DATA YANG BENAR KE FRONTEND
            response_data = {
                'type': 'sensor_update',  # ✅ GANTI 'new_data' → 'sensor_update'
                'data': [saved_data]  # ✅ WRAP DALAM ARRAY seperti yang diharapkan frontend
            }
            await self.send(text_data=json.dumps(response_data))
            
        except Exception as e:
            print(f"❌ Error: {e}")
            error_response = {
                'type': 'error',
                "error": str(e)
            }
            await self.send(text_data=json.dumps(error_response))

    @database_sync_to_async
    def get_all_sensor_data(self):
        """
        Ambil SEMUA data history dari database - SESUAI MODEL BARU
        """
        try:
            all_logs = LightingLog.objects.all().order_by('timestamp')
            if all_logs.exists():
                data_list = []
                for log in all_logs:
                    # ✅ SESUAI MODEL YANG BARU (lighting_action_class sebagai INTEGER)
                    data_list.append({
                        'ambient_light_lux': float(log.ambient_light_lux),
                        'motion_detected': log.motion_detected,  # ✅ INTEGER, bukan boolean
                        'day_of_week': log.day_of_week,
                        'time_of_day': log.time_of_day,
                        'weather_condition': log.weather_condition,
                        'lighting_action_class': log.lighting_action_class,  # ✅ INTEGER 0,1,2
                        'timestamp': log.timestamp.isoformat()
                    })
                return {
                    'type': 'initial_data',
                    'data': data_list
                }
            return None
        except Exception as e:
            print(f"❌ Error getting historical data: {e}")
            return None

    @database_sync_to_async 
    def process_and_save_sensor_data(self, data, user):
        """
        Proses data sensor dengan AI dan simpan ke database - SESUAI MODEL BARU
        """
        try:
            # ✅ EXTRACT DATA SESUAI MODEL BARU
            lux = float(data.get('ambient_light_lux', data.get('lux', 0)))
            motion = int(data.get('motion_detected', 0))  # ✅ INTEGER, bukan boolean
            day_of_week = int(data.get('day_of_week', 0))
            time_of_day = int(data.get('time_of_day', 0))
            weather_condition = int(data.get('weather_condition', 1))
            
            print(f"🤖 AI Processing: lux={lux}, motion={motion}, day={day_of_week}, time={time_of_day}, weather={weather_condition}")
            
            # 🎯 PANGGIL AI MODEL - HARUS RETURN INTEGER (0,1,2)
            lighting_action_class = predict_lighting_action(
                lux, motion, day_of_week, time_of_day, weather_condition  # ✅ PARAMETER LANGSUNG
            )
            
            # ✅ VALIDASI OUTPUT AI (harus integer 0,1,2)
            if lighting_action_class not in [0, 1, 2]:
                raise ValueError(f"AI model return invalid value: {lighting_action_class} (expected 0,1,2)")
                
            print(f"🎯 AI Decision Class: {lighting_action_class}")
            
            # 🗃️ SIMPAN KE DATABASE - SESUAI MODEL BARU
            log_entry = LightingLog.objects.create(
                user=user,
                ambient_light_lux=lux,
                motion_detected=motion,  # ✅ INTEGER
                day_of_week=day_of_week,
                time_of_day=time_of_day,
                weather_condition=weather_condition,
                lighting_action_class=lighting_action_class  # ✅ INTEGER 0,1,2
                # ❌ TIDAK ADA lighting_action (string) lagi
            )
            
            # 📤 RETURN DATA UNTUK FRONTEND - SESUAI STRUCTURE YANG DIHARAPKAN
            return {
                'ambient_light_lux': lux,
                'motion_detected': motion,  # ✅ INTEGER
                'day_of_week': day_of_week,
                'time_of_day': time_of_day,
                'weather_condition': weather_condition,
                'lighting_action_class': lighting_action_class,  # ✅ INTEGER 0,1,2
                'timestamp': log_entry.timestamp.isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error processing sensor data: {e}")
            raise e

    @database_sync_to_async
    def get_default_user(self):
        """Dapatkan user default"""
        try:
            return User.objects.first()
        except:
            from django.contrib.auth.models import AnonymousUser
            return AnonymousUser()