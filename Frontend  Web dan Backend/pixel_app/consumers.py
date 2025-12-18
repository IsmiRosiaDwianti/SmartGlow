import json
import logging
import numpy as np
import asyncio
from datetime import datetime

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import LightingLog, LightState
from .ai_model import predict_lighting_action

logger = logging.getLogger("lighting")


# =====================================================
# JSON SAFE
# =====================================================
def json_safe(val):
    if isinstance(val, dict):
        return {k: json_safe(v) for k, v in val.items()}
    if isinstance(val, list):
        return [json_safe(v) for v in val]
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    return val


# =====================================================
# CEK APAKAH LOG BARU PERLU DISIMPAN
# =====================================================
def should_save_log(lux, motion, state_mode, last_log):
    if not last_log:
        return True
    if state_mode != last_log.control_mode:
        return True
    if lux is not None and (
        last_log.ambient_light_lux != lux
        or last_log.motion_detected != motion
    ):
        return True
    return False


# =====================================================
# CONSUMER
# =====================================================
class SensorDataConsumer(AsyncWebsocketConsumer):

    last_sensor_timestamp = None

    # ================= CONNECT =================
    async def connect(self):
        await self.channel_layer.group_add("dashboard_clients", self.channel_name)
        await self.accept()

        await self.send_initial_data()
        self.timeout_task = asyncio.create_task(self.check_sensor_timeout())

        logger.info("🟢 WebSocket connected")

    async def disconnect(self, close_code):
        if hasattr(self, "timeout_task"):
            self.timeout_task.cancel()
        await self.channel_layer.group_discard("dashboard_clients", self.channel_name)
        logger.info("🔴 WebSocket disconnected")

    # ================= RECEIVE =================
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)

            if data.get("type") == "get_state":
                await self.send_current_state()

            elif data.get("type") == "set_mode":
                await self.set_mode(data.get("mode"))

            elif data.get("type") == "manual_command":
                await self.manual_command(data.get("command"))

            elif "ambient_light_lux" in data:
                if data.get("ambient_light_lux") is None:
                    return
                await self.process_sensor_data(data)

        except Exception as e:
            logger.error("❌ Receive error: %s", e)

    # ================= INITIAL DATA =================
    async def send_initial_data(self):
        state = await self.get_light_state()
        logs = await self.get_recent_logs()

        await self.send(text_data=json.dumps(json_safe({
            "type": "initial_data",
            "control_mode": state["mode"].lower(),
            "light_status": state["status"].lower(),
            "data": logs,
            "timestamp": datetime.now().isoformat()
        })))

    async def send_current_state(self):
        state = await self.get_light_state()
        await self.send(text_data=json.dumps(json_safe({
            "type": "current_state",
            "control_mode": state["mode"].lower(),
            "light_status": state["status"].lower(),
            "timestamp": datetime.now().isoformat()
        })))

    # ================= SENSOR PROCESS =================
    async def process_sensor_data(self, data):
        lux = float(data["ambient_light_lux"])
        SensorDataConsumer.last_sensor_timestamp = datetime.now()

        now = datetime.now()
        state = await self.get_light_state()

        motion = 1 if lux < 100 else 0
        weather = 0 if lux > 200 else 1
        day = now.weekday()
        tod = self.get_time_of_day(now.hour)

        if state["mode"] == "AUTO":
            action = int(predict_lighting_action(lux, motion, day, tod, weather))
            new_status = "ON" if action == 1 else "OFF"
            await self.update_light_status(new_status)
            is_manual = False
        else:
            new_status = state["status"]
            action = 1 if new_status == "ON" else 0
            is_manual = True

        last_log = await self.get_last_log()
        if should_save_log(lux, motion, state["mode"], last_log):
            log = await self.save_log(
                lux, motion, day, tod, weather,
                action, state["mode"], is_manual, "sensor"
            )
            await self.channel_layer.group_send(
                "dashboard_clients",
                {"type": "sensor_update", "data": [log]}
            )

    # ================= TIMEOUT =================
    async def check_sensor_timeout(self):
        while True:
            try:
                if self.last_sensor_timestamp:
                    delta = (datetime.now() - self.last_sensor_timestamp).seconds
                    state = await self.get_light_state()
                    if delta > 15 and state["status"] != "OFF":
                        await self.update_light_status("OFF")
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

    # ================= EVENTS =================
    async def sensor_update(self, event):
        await self.send(text_data=json.dumps(json_safe(event)))

    async def control_mode_update(self, event):
        await self.send(text_data=json.dumps(json_safe(event)))

    async def manual_command_update(self, event):
        await self.send(text_data=json.dumps(json_safe(event)))

    # 🔧 FIX ERROR: handler yang HILANG
    async def control_update(self, event):
        await self.send(text_data=json.dumps(json_safe(event)))

    # ================= CONTROL =================
    async def set_mode(self, mode):
        if not mode:
            return

        await self.update_control_mode(mode.upper())
        state = await self.get_light_state()

        await self.channel_layer.group_send(
            "dashboard_clients",
            {
                "type": "control_mode_update",
                "control_mode": state["mode"],
                "light_status": state["status"],
                "timestamp": datetime.now().isoformat()
            }
        )

    async def manual_command(self, command):
        state = await self.get_light_state()
        if state["mode"] != "MANUAL":
            return

        new_status = "ON" if int(command) == 1 else "OFF"
        await self.update_light_status(new_status)

        # 🔥 broadcast biar app & web langsung update
        await self.channel_layer.group_send(
            "dashboard_clients",
            {
                "type": "manual_command_update",
                "light_status": new_status.lower(),
                "timestamp": datetime.now().isoformat()
            }
        )

    # ================= HELPERS =================
    def get_time_of_day(self, hour):
        if 6 <= hour < 12: return 1
        if 12 <= hour < 18: return 2
        if 18 <= hour < 24: return 3
        return 0

    @database_sync_to_async
    def get_light_state(self):
        state = LightState.objects.first()
        if not state:
            state = LightState.objects.create(mode="AUTO", status="OFF")
        return {"mode": state.mode, "status": state.status}

    @database_sync_to_async
    def update_light_status(self, status):
        state = LightState.objects.first()
        if not state:
            LightState.objects.create(mode="AUTO", status=status)
        else:
            state.status = status
            state.save()

    @database_sync_to_async
    def update_control_mode(self, mode):
        state = LightState.objects.first()
        if not state:
            LightState.objects.create(mode=mode, status="OFF")
        else:
            state.mode = mode
            state.save()

    @database_sync_to_async
    def get_last_log(self):
        return LightingLog.objects.order_by("-timestamp").first()

    @database_sync_to_async
    def save_log(self, lux, motion, day, tod, weather, action, mode, is_manual, source):
        log = LightingLog.objects.create(
            ambient_light_lux=lux,
            motion_detected=motion,
            day_of_week=day,
            time_of_day=tod,
            weather_condition=weather,
            lighting_action_class=action,
            control_mode=mode,
            is_manual=is_manual,
            source=source
        )
        return {
            "ambient_light_lux": lux,
            "motion_detected": motion,
            "day_of_week": day,
            "time_of_day": tod,
            "weather_condition": weather,
            "lighting_action_class": action,
            "control_mode": mode.lower(),
            "is_manual": is_manual,
            "timestamp": log.timestamp.isoformat(),
            "source": source
        }

    @database_sync_to_async
    def get_recent_logs(self):
        logs = LightingLog.objects.order_by("-timestamp")[:20]
        return [{
            "ambient_light_lux": l.ambient_light_lux,
            "motion_detected": l.motion_detected,
            "day_of_week": l.day_of_week,
            "time_of_day": l.time_of_day,
            "weather_condition": l.weather_condition,
            "lighting_action_class": l.lighting_action_class,
            "control_mode": l.control_mode.lower(),
            "is_manual": l.is_manual,
            "timestamp": l.timestamp.isoformat(),
            "source": l.source
        } for l in logs]
