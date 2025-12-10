import json
import logging
import numpy as np
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import LightingLog, LightState
from .ai_model import predict_lighting_action

logger = logging.getLogger("lighting")

# ===================================================
# 🔧 UTILITY — FIX numpy types → native JSON safe
# ===================================================
def to_native(value):
    if isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    if isinstance(value, (np.floating, np.float32, np.float64)):
        return float(value)
    return value


class SensorDataConsumer(AsyncWebsocketConsumer):

    # ===================================================
    # CONNECT
    # ===================================================
    async def connect(self):
        await self.channel_layer.group_add("dashboard_clients", self.channel_name)
        await self.accept()
        await self.send_initial_data()
        logger.info("🟢 WebSocket connected")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("dashboard_clients", self.channel_name)
        logger.info("🔴 WebSocket disconnected")

    # ===================================================
    # INITIAL DATA - FIXED FORMAT
    # ===================================================
    async def send_initial_data(self):
        try:
            logs = await self.get_recent_logs()
            state = await self.get_light_state()

            # ✅ FIXED: Format sesuai yang diharapkan dashboard
            response = {
                "type": "initial_data",
                "control_mode": state["mode"].lower(),  # 'auto' atau 'manual'
                "light_status": state["status"].lower(),  # 'on' atau 'off'
                "data": logs,  # Array of sensor data
                "timestamp": datetime.now().isoformat(),
                "message": "Initial data loaded successfully"
            }
            
            await self.send(text_data=json.dumps(response))
            logger.info(f"📤 Sent initial data: {len(logs)} logs")
            
        except Exception as e:
            logger.error(f"❌ Error sending initial data: {e}")
            await self.send(text_data=json.dumps({
                "type": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }))

    # ===================================================
    # RECEIVE - FIXED HANDLING
    # ===================================================
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            logger.info(f"📨 Received message type: {data.get('type')}")

            if data.get("type") == "get_state":
                await self.send_current_state()
                
            elif data.get("type") == "set_mode":
                await self.set_mode(data.get("mode", "AUTO"))
                
            elif data.get("type") == "manual_command":
                await self.manual_command(data.get("command"))
                
            elif "ambient_light_lux" in data:
                # Sensor data from IoT
                await self.process_sensor_data(data)
                
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
            await self.send(text_data=json.dumps({
                "type": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }))

    # ===================================================
    # PROCESS SENSOR DATA - FIXED BROADCAST
    # ===================================================
    async def process_sensor_data(self, data):
        try:
            lux = float(data.get("ambient_light_lux", 0))
            state = await self.get_light_state()

            now = datetime.now()
            day_of_week = now.weekday()
            time_of_day = self.get_time_of_day(now.hour)

            motion = 1 if lux < 100 else 0
            weather = 0 if lux > 200 else 1

            # -------------------------------
            # AUTO MODE → AI ACTIVE
            # -------------------------------
            if state["mode"] == "AUTO":
                action = predict_lighting_action(lux, motion, day_of_week, time_of_day, weather)
                action = to_native(action)
                new_status = "ON" if action == 1 else "OFF"
                await self.update_light_status(new_status)
                is_manual = False
                logger.info(f"🤖 AI Decision: lux={lux} → action={action}")

            else:
                # MANUAL MODE → KEEP CURRENT
                action = 1 if state["status"] == "ON" else 0
                new_status = state["status"]
                is_manual = True
                logger.info(f"🕹️ Manual Mode: lux={lux}, status={new_status}")

            # ===================================================
            # SAVE LOG
            # ===================================================
            user = await self.get_default_user()
            log = await self.save_log(
                user=user,
                lux=lux,
                motion=motion,
                day_of_week=day_of_week,
                time_of_day=time_of_day,
                weather=weather,
                action=action,
                mode=state["mode"],
                is_manual=is_manual
            )

            # ✅ FIXED: Broadcast dengan format yang BENAR untuk dashboard
            # Dashboard mengharapkan: {type: "sensor_update", data: [array_of_data]}
            sensor_update = {
                "type": "sensor_update",
                "data": [log],  # ❗PENTING: WRAP IN ARRAY
                "timestamp": datetime.now().isoformat(),
                "source": "websocket",
                "message": f"Sensor data processed: lux={lux}"
            }
            
            await self.channel_layer.group_send(
                "dashboard_clients",
                {
                    "type": "broadcast_sensor_update",  # Gunakan handler khusus
                    "message": sensor_update
                }
            )
            
            logger.info(f"📤 Broadcasted sensor data: lux={lux}, action={action}")

        except Exception as e:
            logger.error(f"❌ Error processing sensor data: {e}")
            await self.send(text_data=json.dumps({
                "type": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }))

    # ===================================================
    # STATE - FIXED FORMAT
    # ===================================================
    async def send_current_state(self):
        try:
            state = await self.get_light_state()
            
            # ✅ FIXED: Format sesuai yang diharapkan dashboard
            response = {
                "type": "current_state",
                "control_mode": state["mode"].lower(),
                "light_status": state["status"].lower(),
                "timestamp": datetime.now().isoformat(),
                "message": "Current system state"
            }
            
            await self.send(text_data=json.dumps(response))
            logger.info(f"📤 Sent current state: mode={state['mode']}, status={state['status']}")
            
        except Exception as e:
            logger.error(f"❌ Error sending current state: {e}")

    # ===================================================
    # DATABASE - TAMBAHKAN FIELD YANG DIPERLUKAN
    # ===================================================
    @database_sync_to_async
    def get_light_state(self):
        state, _ = LightState.objects.get_or_create(defaults={"mode": "AUTO", "status": "OFF"})
        return {"mode": state.mode, "status": state.status}

    @database_sync_to_async
    def update_light_status(self, status):
        state, _ = LightState.objects.get_or_create(defaults={"mode": "AUTO", "status": "OFF"})
        state.status = status
        state.save()
        logger.info(f"💡 Updated light status: {status}")

    @database_sync_to_async
    def get_default_user(self):
        return User.objects.first()

    @database_sync_to_async
    def save_log(self, user, lux, motion, day_of_week, time_of_day, weather, action, mode, is_manual):
        log = LightingLog.objects.create(
            user=user,
            ambient_light_lux=lux,
            motion_detected=motion,
            day_of_week=day_of_week,
            time_of_day=time_of_day,
            weather_condition=weather,
            lighting_action_class=action,
            control_mode=mode,
            is_manual=is_manual,
            source="websocket",
        )

        # ✅ FIXED: Return data dengan semua field yang dibutuhkan dashboard
        return {
            "id": log.id,
            "ambient_light_lux": to_native(lux),
            "motion_detected": to_native(motion),
            "day_of_week": to_native(day_of_week),
            "time_of_day": to_native(time_of_day),
            "weather_condition": to_native(weather),
            "lighting_action_class": to_native(action),
            "control_mode": mode.lower(),
            "is_manual": is_manual,
            "is_test": False,
            "timestamp": log.timestamp.isoformat(),
            "source": "websocket"
        }

    # ===================================================
    # MODE MANAGEMENT - FIXED BROADCAST
    # ===================================================
    async def set_mode(self, mode):
        try:
            mode = mode.upper()
            if mode not in ["AUTO", "MANUAL"]:
                return

            await self.update_control_mode(mode)
            
            # Get updated state
            state = await self.get_light_state()
            
            # ✅ FIXED: Broadcast dengan format yang BENAR
            mode_update = {
                "type": "control_mode",
                "control_mode": state["mode"].lower(),
                "light_status": state["status"].lower(),
                "source": "websocket",
                "timestamp": datetime.now().isoformat(),
                "message": f"Mode changed to {mode}"
            }
            
            await self.channel_layer.group_send(
                "dashboard_clients",
                {
                    "type": "broadcast_control_mode",  # Gunakan handler khusus
                    "message": mode_update
                }
            )
            
            logger.info(f"📤 Broadcasted mode change: {mode}")
            
        except Exception as e:
            logger.error(f"❌ Error setting mode: {e}")

    @database_sync_to_async
    def update_control_mode(self, mode):
        state, _ = LightState.objects.get_or_create(defaults={"mode": "AUTO", "status": "OFF"})
        state.mode = mode
        state.save()
        logger.info(f"🔄 Updated control mode: {mode}")

    # ===================================================
    # MANUAL COMMAND - FIXED BROADCAST
    # ===================================================
    async def manual_command(self, command):
        try:
            state = await self.get_light_state()

            if state["mode"] != "MANUAL":
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "error": "Cannot send manual command in AUTO mode",
                    "timestamp": datetime.now().isoformat()
                }))
                return

            # Convert command to status
            new_status = "ON" if command == 1 else "OFF"
            await self.update_light_status(new_status)
            
            # ✅ FIXED: Broadcast dengan format yang BENAR
            manual_update = {
                "type": "manual_command",
                "command": command,
                "status": new_status.lower(),
                "source": "dashboard",
                "timestamp": datetime.now().isoformat(),
                "message": f"Manual command executed: {new_status}"
            }
            
            await self.channel_layer.group_send(
                "dashboard_clients",
                {
                    "type": "broadcast_manual_command",  # Gunakan handler khusus
                    "message": manual_update
                }
            )
            
            logger.info(f"📤 Broadcasted manual command: {new_status}")
            
        except Exception as e:
            logger.error(f"❌ Error processing manual command: {e}")

    # ===================================================
    # TIME HELPER
    # ===================================================
    def get_time_of_day(self, hour):
        if 6 <= hour < 12: return 1  # Morning
        if 12 <= hour < 18: return 2  # Afternoon
        if 18 <= hour < 24: return 3  # Evening
        return 0  # Night

    @database_sync_to_async
    def get_recent_logs(self):
        """Get recent logs for initial data"""
        logs = LightingLog.objects.all().order_by("-timestamp")[:20]  # Last 20 logs
        
        result = []
        for log in logs:
            result.append({
                "ambient_light_lux": to_native(log.ambient_light_lux),
                "motion_detected": to_native(log.motion_detected),
                "day_of_week": to_native(log.day_of_week),
                "time_of_day": to_native(log.time_of_day),
                "weather_condition": to_native(log.weather_condition),
                "lighting_action_class": to_native(log.lighting_action_class),
                "control_mode": log.control_mode.lower() if hasattr(log, 'control_mode') else 'auto',
                "is_manual": getattr(log, 'is_manual', False),
                "is_test": False,
                "timestamp": log.timestamp.isoformat(),
                "source": getattr(log, 'source', 'unknown')
            })
        
        return result

    # ===================================================
    # ✅ FIXED HANDLERS - UNTUK BROADCAST MESSAGES
    # ===================================================
    
    async def broadcast_sensor_update(self, event):
        """Handler untuk broadcast sensor data"""
        message = event.get("message", {})
        await self.send(text_data=json.dumps(message))
        logger.debug(f"📤 Sent sensor update: {message.get('type')}")

    async def broadcast_control_mode(self, event):
        """Handler untuk broadcast control mode"""
        message = event.get("message", {})
        await self.send(text_data=json.dumps(message))
        logger.debug(f"📤 Sent control mode: {message.get('type')}")

    async def broadcast_manual_command(self, event):
        """Handler untuk broadcast manual command"""
        message = event.get("message", {})
        await self.send(text_data=json.dumps(message))
        logger.debug(f"📤 Sent manual command: {message.get('type')}")

    # ===================================================
    # LEGACY HANDLERS (untuk kompatibilitas)
    # ===================================================
    async def sensor_update(self, event):
        """Legacy handler - untuk backward compatibility"""
        # Konversi format lama ke format baru
        sensor_data = {
            "type": "sensor_update",
            "data": [event.get("data", {})],  # Wrap in array
            "timestamp": event.get("timestamp", datetime.now().isoformat()),
            "source": "websocket_legacy"
        }
        await self.send(text_data=json.dumps(sensor_data))

    async def control_mode_update(self, event):
        """Legacy handler - untuk backward compatibility"""
        mode_data = {
            "type": "control_mode",
            "control_mode": event.get("mode", "auto"),
            "light_status": "off",  # Default
            "timestamp": event.get("timestamp", datetime.now().isoformat()),
            "source": "websocket_legacy"
        }
        await self.send(text_data=json.dumps(mode_data))

    async def manual_command_update(self, event):
        """Legacy handler - untuk backward compatibility"""
        command_data = {
            "type": "manual_command",
            "command": event.get("command"),
            "status": event.get("status", "off"),
            "timestamp": event.get("timestamp", datetime.now().isoformat()),
            "source": "websocket_legacy"
        }
        await self.send(text_data=json.dumps(command_data))