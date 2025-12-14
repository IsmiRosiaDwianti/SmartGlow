import logging
from datetime import datetime

from django.core.cache import cache
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.serializers import ModelSerializer, CharField, ValidationError

from rest_framework_simplejwt.tokens import RefreshToken

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import LightingLog, LightState
from .serializers import LightingLogSerializer
from .ai_model import predict_lighting_action

logger = logging.getLogger(__name__)

# =========================================================
# WEBSOCKET BROADCAST
# =========================================================
def broadcast_to_websocket(event_type, data):
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        payload = {"type": event_type, **data, "timestamp": datetime.now().isoformat()}
        async_to_sync(channel_layer.group_send)("dashboard_clients", payload)

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

# =========================================================
# STATE HELPER
# =========================================================
def get_or_create_state():
    state = LightState.objects.first()
    if not state:
        state = LightState.objects.create(mode="AUTO", status="OFF")
    return state

# =========================================================
# LOG FILTER
# =========================================================
def should_save_log(lux, motion, mode):
    last = LightingLog.objects.order_by('-timestamp').first()
    if not last:
        return True

    if last.control_mode != mode:
        return True

    if lux is not None:
        if last.ambient_light_lux != lux or last.motion_detected != motion:
            return True

    return False

# =========================================================
# API 1 — SENSOR → AI (AUTO ONLY)
# =========================================================
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def lighting_decision_api(request):
    try:
        # ❌ TIDAK ADA LUX → JANGAN LOG, JANGAN AI
        if 'ambient_light_lux' not in request.data:
            return Response({
                "success": True,
                "skipped": True,
                "message": "No lux data. State unchanged."
            })

        lux = float(request.data.get('ambient_light_lux'))
        now = datetime.now()

        day = now.weekday()
        time_of_day = (
            1 if 6 <= now.hour < 12 else
            2 if 12 <= now.hour < 18 else
            3 if 18 <= now.hour < 24 else 0
        )

        # MOTION (simple)
        prev_lux = cache.get("prev_lux")
        motion = 1 if prev_lux and abs(lux - prev_lux) > 20 else 0
        cache.set("prev_lux", lux, 3600)

        weather = 0 if lux > 200 else 1
        state = get_or_create_state()

        # =========================
        # MODE MANUAL
        # =========================
        if state.mode == "MANUAL":
            if should_save_log(lux, motion, "MANUAL"):
                LightingLog.objects.create(
                    ambient_light_lux=lux,
                    motion_detected=motion,
                    day_of_week=day,
                    time_of_day=time_of_day,
                    weather_condition=weather,
                    lighting_action_class=1 if state.status == "ON" else 0,
                    control_mode="MANUAL",
                    is_manual=True,
                    source="sensor"
                )

            broadcast_to_websocket("control_update", {
                "mode": state.mode,
                "status": state.status
            })

            return Response({
                "success": True,
                "mode": state.mode,
                "lamp_status": state.status,
                "lux": lux,
                "motion": motion,
                "message": "MANUAL mode — AI skipped"
            })

        # =========================
        # MODE AUTO → AI
        # =========================
        prediction = predict_lighting_action(lux, motion, day, time_of_day, weather)
        new_status = "ON" if prediction == 1 else "OFF"

        state.status = new_status
        state.save()

        if should_save_log(lux, motion, "AUTO"):
            LightingLog.objects.create(
                ambient_light_lux=lux,
                motion_detected=motion,
                day_of_week=day,
                time_of_day=time_of_day,
                weather_condition=weather,
                lighting_action_class=prediction,
                control_mode="AUTO",
                is_manual=False,
                source="ai"
            )

        broadcast_to_websocket("control_update", {
            "mode": "AUTO",
            "status": new_status
        })

        return Response({
            "success": True,
            "mode": "AUTO",
            "lamp_status": new_status,
            "lux": lux,
            "motion": motion,
            "ai_result": prediction
        })

    except Exception as e:
        logger.error(e)
        return Response({"success": False, "error": str(e)}, status=400)

# =========================================================
# API 2 — GET STATUS
# =========================================================
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_light_status(request):
    state = get_or_create_state()
    return Response({
        "mode": state.mode,
        "status": state.status
    })

# =========================================================
# API 3 — MANUAL CONTROL (NO LUX REQUIRED)
# =========================================================
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def set_light_status(request):
    state = get_or_create_state()
    old_mode, old_status = state.mode, state.status

    mode = (request.data.get("mode") or "").upper()
    status = (request.data.get("lamp_status") or "").upper()

    if mode in ["AUTO", "MANUAL"]:
        state.mode = mode

    if status in ["ON", "OFF"]:
        state.status = status

    state.save()

    broadcast_to_websocket("control_update", {
        "mode": state.mode,
        "status": state.status
    })

    # ❗ TANPA LUX → JANGAN SIMPAN LOG
    return Response({
        "success": True,
        "old_mode": old_mode,
        "old_status": old_status,
        "mode": state.mode,
        "status": state.status,
        "message": "State updated (no sensor log)"
    })

# =========================================================
# LOG VIEW
# =========================================================
class LightingLogViewSet(viewsets.ModelViewSet):
    queryset = LightingLog.objects.all().order_by('-timestamp')
    serializer_class = LightingLogSerializer
    permission_classes = [permissions.AllowAny]

# =========================================================
# AUTH
# =========================================================
class RegisterSerializer(ModelSerializer):
    password = CharField(write_only=True)
    password2 = CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2')

    def validate(self, data):
        if data['password'] != data['password2']:
            raise ValidationError("Password tidak sama")
        return data

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({"success": True, "username": user.username})
    return Response(serializer.errors, status=400)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_user(request):
    user = authenticate(
        username=request.data.get("username"),
        password=request.data.get("password")
    )
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        })
    return Response({"error": "Login gagal"}, status=401)
