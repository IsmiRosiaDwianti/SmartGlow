import logging
from datetime import datetime

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.serializers import ModelSerializer, CharField, ValidationError

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import LightingLog, LightState
from .serializers import LightingLogSerializer
from .ai_model import predict_lighting_action

logger = logging.getLogger(__name__)


# ---------------------------
# Helper: Broadcast ke WebSocket
# ---------------------------
def broadcast_to_websocket(event_type, data):
    """
    Broadcast sederhana ke grup 'dashboard_clients'.
    event_type: 'control_mode' | 'sensor_data' | 'manual_command'
    data: dict sesuai event
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.debug("No channel_layer available, skipping broadcast")
            return

        if event_type == 'control_mode':
            async_to_sync(channel_layer.group_send)(
                "dashboard_clients",
                {
                    "type": "control_mode_update",
                    "mode": data.get('mode', 'AUTO'),
                    "status": data.get('status', 'OFF'),
                    "source": data.get('source', 'api'),
                    "timestamp": datetime.now().isoformat(),
                    "message": data.get('message', 'Control mode updated')
                }
            )
            logger.info(f"📤 Broadcasted control_mode: mode={data.get('mode')}, status={data.get('status')}")

        elif event_type == 'sensor_data':
            async_to_sync(channel_layer.group_send)(
                "dashboard_clients",
                {
                    "type": "sensor_update",
                    "data": data.get('data', []),
                    "source": data.get('source', 'sensor'),
                    "timestamp": datetime.now().isoformat()
                }
            )
            logger.info(f"📤 Broadcasted sensor_data: {len(data.get('data', []))} items")

        elif event_type == 'manual_command':
            async_to_sync(channel_layer.group_send)(
                "dashboard_clients",
                {
                    "type": "manual_command_update",
                    "command": data.get('command'),
                    "status": data.get('status', 'OFF'),
                    "source": data.get('source', 'api'),
                    "timestamp": datetime.now().isoformat()
                }
            )
            logger.info(f"📤 Broadcasted manual_command: command={data.get('command')}")

    except Exception as e:
        logger.error(f"❌ WebSocket broadcast failed: {e}")
        # jangan raise, hanya log saja


# ---------------------------
# Helper: Ambil atau buat LightState default
# ---------------------------
def get_or_create_state():
    state = LightState.objects.first()
    if not state:
        state = LightState.objects.create(mode="AUTO", status="OFF")
        logger.info("🆕 Created new LightState")
    return state


# ============================================================
# API 1: IoT MENGIRIM LUX → AI MEMUTUSKAN (HANYA MODE AUTO)
# ============================================================
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def lighting_decision_api(request):
    """
    IoT mengirim data sensor lux, backend memutuskan lampu.
    Payload:
    {
        "ambient_light_lux": 75.5
    }
    Keluaran: action class (0=OFF,1=ON,2=DIM) dan update state jika AUTO.
    """
    try:
        data = request.data
        lux = float(data.get('ambient_light_lux', 0))

        logger.info(f"🔦 Sensor data received: lux={lux}")

        # generate fitur tambahan
        motion = 1 if lux < 100 else 0
        weather = 0 if lux > 200 else 1
        now = datetime.now()
        time_of_day = (
            1 if 6 <= now.hour < 12 else
            2 if 12 <= now.hour < 18 else
            3 if 18 <= now.hour < 24 else 0
        )
        day = now.weekday()

        # Ambil state lampu global
        state = get_or_create_state()
        logger.info(f"📊 Current state: mode={state.mode}, status={state.status}")

        # Jika mode MANUAL -> hanya simpan data sensor & broadcast sensor data, AI diabaikan
        if state.mode == "MANUAL":
            logger.info("📱 Mode MANUAL: Simpan log sensor tanpa AI decision")
            try:
                lighting_action = 1 if state.status == "ON" else 0
                log_entry = LightingLog.objects.create(
                    ambient_light_lux=lux,
                    motion_detected=motion,
                    day_of_week=day,
                    time_of_day=time_of_day,
                    weather_condition=weather,
                    lighting_action_class=lighting_action,
                    source='sensor',
                    control_mode='MANUAL',
                    is_manual=True
                )
                logger.info(f"💾 Saved manual log: ID={log_entry.id}, Action={lighting_action}")
            except Exception as e:
                logger.error(f"❌ Error saving manual log: {e}")

            # Broadcast control_mode dan sensor_data
            broadcast_to_websocket('control_mode', {
                'mode': state.mode,
                'status': state.status,
                'source': 'sensor_api',
                'message': f'Sensor received (lux={lux}) but mode is MANUAL'
            })

            sensor_data = {
                'ambient_light_lux': lux,
                'motion_detected': motion,
                'day_of_week': day,
                'time_of_day': time_of_day,
                'weather_condition': weather,
                'lighting_action_class': 1 if state.status == "ON" else 0,
                'control_mode': 'manual',
                'is_manual': True,
                'timestamp': datetime.now().isoformat()
            }
            broadcast_to_websocket('sensor_data', {'data': [sensor_data], 'source': 'sensor_api'})

            return Response({
                "success": True,
                "mode": state.mode,
                "lamp_status": state.status,
                "lux_value": lux,
                "message": "Mode MANUAL: Using manual control",
                "database_saved": True
            })

        # Mode AUTO: jalankan AI
        logger.info("🤖 Mode AUTO: Running AI prediction")
        logger.info(f"🤖 AI Input: lux={lux}, motion={motion}, day={day}, time={time_of_day}, weather={weather}")
        prediction_class = predict_lighting_action(lux, motion, day, time_of_day, weather)

        if prediction_class not in [0, 1, 2]:
            logger.warning("⚠️ Invalid AI prediction, defaulting to OFF (0)")
            prediction_class = 0

        logger.info(f"🤖 AI Prediction: class={prediction_class}")

        # Konversi class ke status lampu (sederhana: 1->ON, else OFF)
        new_status = "ON" if prediction_class == 1 else "OFF"
        old_status = state.status
        state.status = new_status
        state.save()
        logger.info(f"💡 AI Decision: {old_status} -> {new_status} (class={prediction_class})")

        # Simpan log AI decision
        try:
            log_entry = LightingLog.objects.create(
                ambient_light_lux=lux,
                motion_detected=motion,
                day_of_week=day,
                time_of_day=time_of_day,
                weather_condition=weather,
                lighting_action_class=prediction_class,
                source='ai_decision',
                control_mode='AUTO',
                is_manual=False
            )
            logger.info(f"💾 Saved AI log: ID={log_entry.id}")
        except Exception as e:
            logger.error(f"❌ Error saving AI log: {e}")

        # Broadcast perubahan state dan data sensor
        broadcast_to_websocket('control_mode', {
            'mode': state.mode,
            'status': state.status,
            'source': 'ai_decision',
            'message': f'AI decision: {old_status} → {new_status} (lux={lux})'
        })

        sensor_data = {
            'ambient_light_lux': lux,
            'motion_detected': motion,
            'day_of_week': day,
            'time_of_day': time_of_day,
            'weather_condition': weather,
            'lighting_action_class': prediction_class,
            'control_mode': 'auto',
            'is_manual': False,
            'timestamp': datetime.now().isoformat()
        }
        broadcast_to_websocket('sensor_data', {'data': [sensor_data], 'source': 'sensor_api'})

        return Response({
            "success": True,
            "mode": state.mode,
            "lamp_status": state.status,
            "lighting_action_class": prediction_class,
            "lux_value": lux,
            "ai_input": {"lux": lux, "motion": motion, "day_of_week": day, "time_of_day": time_of_day, "weather": weather},
            "message": f"AI decided: {new_status} (lux={lux})",
            "broadcast": "sent_to_dashboard",
            "database_saved": True
        })

    except Exception as e:
        logger.error(f"❌ Error in lighting_decision_api: {e}")
        return Response({"success": False, "error": str(e), "message": "Internal server error"}, status=400)


# ============================================================
# API 2: GET STATUS LAMPU (DIGUNAKAN OLEH IOT & DASHBOARD)
# ============================================================
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_light_status(request):
    try:
        state = get_or_create_state()

        # Ambil recent logs
        recent_logs = LightingLog.objects.all().order_by('-timestamp')[:5]
        logs_summary = []
        for log in recent_logs:
            logs_summary.append({
                'lux': getattr(log, 'ambient_light_lux', None),
                'action': getattr(log, 'lighting_action_class', None),
                'time': log.timestamp.strftime("%H:%M:%S") if hasattr(log, 'timestamp') else str(log)
            })

        response_data = {
            "mode": state.mode,
            "status": state.status,
            "updated_at": getattr(state, 'updated_at', None),
            "timestamp": datetime.now().isoformat(),
            "recent_logs": logs_summary,
            "total_logs": LightingLog.objects.count()
        }
        logger.info(f"📊 get_light_status: mode={state.mode}, status={state.status}")
        return Response(response_data)
    except Exception as e:
        logger.error(f"❌ Error in get_light_status: {e}")
        return Response({"success": False, "error": str(e)}, status=400)


# ============================================================
# API 3: SET STATUS LAMPU / MODE (DARI DASHBOARD MANUAL)
# ============================================================
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def set_light_status(request):
    """
    Payload contoh:
    { "mode": "MANUAL", "status": "ON" }
    atau { "mode": "AUTO" }
    """
    try:
        data = request.data
        mode = (data.get("mode") or "").upper()
        status_val = (data.get("status") or "").upper()  # ON / OFF

        logger.info(f"🎛️ set_light_status called: mode={mode}, status={status_val}")

        state = get_or_create_state()
        old_mode = state.mode
        old_status = state.status

        if mode in ["AUTO", "MANUAL"]:
            state.mode = mode
            logger.info(f"🔄 Mode changed: {old_mode} → {mode}")

        # Update status hanya jika mode MANUAL
        if state.mode == "MANUAL" and status_val in ["ON", "OFF"]:
            state.status = status_val
            logger.info(f"💡 Status changed: {old_status} → {status_val}")
        elif state.mode == "AUTO":
            # Reset ke OFF — AI yang akan menentukan selanjutnya
            state.status = "OFF"
            logger.info("🔄 Mode AUTO: Reset status to OFF (AI will decide)")

        state.save()
        logger.info(f"💾 Saved LightState: mode={state.mode}, status={state.status}")

        # Broadcast
        broadcast_data = {
            'mode': state.mode,
            'status': state.status,
            'source': 'api_postman',
            'message': f'Updated via API: {old_mode}→{state.mode}, {old_status}→{state.status}'
        }
        broadcast_to_websocket('control_mode', broadcast_data)

        # Jika manual command, broadcast manual_command
        if state.mode == "MANUAL" and status_val:
            command = 1 if status_val == "ON" else 0
            broadcast_to_websocket('manual_command', {'command': command, 'status': status_val, 'source': 'api_postman'})

        # Simpan log perubahan mode
        try:
            LightingLog.objects.create(
                ambient_light_lux=0,
                motion_detected=0,
                day_of_week=datetime.now().weekday(),
                time_of_day=1 if 6 <= datetime.now().hour < 12 else 2 if 12 <= datetime.now().hour < 18 else 3 if 18 <= datetime.now().hour < 24 else 0,
                weather_condition=0,
                lighting_action_class=1 if state.status == "ON" else 0,
                source='mode_change',
                control_mode=state.mode,
                is_manual=(state.mode == "MANUAL")
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not save mode change log: {e}")

        return Response({
            "success": True,
            "message": "Light state updated successfully AND broadcasted to dashboard",
            "mode": state.mode,
            "status": state.status,
            "old_mode": old_mode,
            "old_status": old_status,
            "broadcast": "sent_to_dashboard",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Error in set_light_status: {e}")
        return Response({"success": False, "error": str(e)}, status=400)


# ============================================================
# API 4: SEND TEST DATA (UNTUK TESTING DASHBOARD)
# ============================================================
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def send_test_data(request):
    """
    Payload contoh:
    { "lux": 75.5, "mode": "AUTO" }
    """
    try:
        data = request.data
        lux = float(data.get('lux', 50.0))
        mode = (data.get('mode') or 'AUTO').upper()

        logger.info(f"🧪 Test data: lux={lux}, mode={mode}")

        state = get_or_create_state()

        if mode == "AUTO":
            # Simulate AI decision via same simple mapping (atau bisa panggil AI)
            motion = 1 if lux < 100 else 0
            weather = 0 if lux > 200 else 1
            now = datetime.now()
            time_of_day = 1 if 6 <= now.hour < 12 else 2 if 12 <= now.hour < 18 else 3 if 18 <= now.hour < 24 else 0
            day = now.weekday()
            lighting_action = predict_lighting_action(lux, motion, day, time_of_day, weather)
            if lighting_action not in [0, 1, 2]:
                lighting_action = 0
            status = "ON" if lighting_action == 1 else "OFF"
        else:
            lighting_action = 1 if state.status == "ON" else 0
            status = state.status

        sensor_data = {
            'ambient_light_lux': lux,
            'motion_detected': 1 if lux < 100 else 0,
            'day_of_week': datetime.now().weekday(),
            'time_of_day': 1 if 6 <= datetime.now().hour < 12 else 2 if 12 <= datetime.now().hour < 18 else 3 if 18 <= datetime.now().hour < 24 else 0,
            'weather_condition': 0 if lux > 200 else 1,
            'lighting_action_class': lighting_action,
            'control_mode': mode.lower(),
            'is_manual': (mode == "MANUAL"),
            'is_test': True,
            'timestamp': datetime.now().isoformat()
        }

        broadcast_to_websocket('sensor_data', {'data': [sensor_data], 'source': 'test_api'})

        if mode != state.mode:
            broadcast_to_websocket('control_mode', {'mode': mode, 'status': status, 'source': 'test_api', 'message': f'Test mode change: {state.mode}→{mode}'})

        return Response({
            "success": True,
            "message": "Test data sent to dashboard",
            "lux": lux,
            "mode": mode,
            "lighting_action": lighting_action,
            "status": status,
            "broadcast": "sent_to_dashboard",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Error in send_test_data: {e}")
        return Response({"success": False, "error": str(e)}, status=400)


# ============================================================
# API 5: GET CURRENT LOGS (UNTUK DEBUGGING)
# ============================================================
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_current_logs(request):
    """
    Get recent logs untuk debugging
    Params:
      - limit: jumlah log (default 10)
      - mode: filter by mode (AUTO/MANUAL)
    """
    try:
        limit = int(request.GET.get('limit', 10))
        mode_filter = (request.GET.get('mode') or '').upper()

        queryset = LightingLog.objects.all().order_by('-timestamp')
        if mode_filter in ['AUTO', 'MANUAL']:
            queryset = queryset.filter(control_mode=mode_filter)

        logs = queryset[:limit]
        serializer = LightingLogSerializer(logs, many=True)

        # state summary
        state = LightState.objects.first()
        state_data = {
            'mode': state.mode if state else 'AUTO',
            'status': state.status if state else 'OFF',
            'updated': getattr(state, 'updated_at', None)
        }

        return Response({
            "success": True,
            "logs_count": len(serializer.data),
            "logs": serializer.data,
            "current_state": state_data,
            "total_logs": LightingLog.objects.count(),
            "auto_logs": LightingLog.objects.filter(control_mode='AUTO').count(),
            "manual_logs": LightingLog.objects.filter(control_mode='MANUAL').count(),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Error in get_current_logs: {e}")
        return Response({"success": False, "error": str(e)}, status=400)


# ============================================================
# API 6: SYSTEM STATUS & HEALTH CHECK
# ============================================================
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def system_status(request):
    try:
        state = LightState.objects.first()
        log_count = LightingLog.objects.count()

        # Check AI model quick call
        try:
            ai_test = predict_lighting_action(50, 1, 1, 2, 0)
            ai_status = "WORKING"
        except Exception as e:
            ai_status = f"ERROR: {e}"
            ai_test = None

        status_data = {
            "status": "OK",
            "timestamp": datetime.now().isoformat(),
            "database": {
                "light_state_exists": state is not None,
                "light_state": {"mode": state.mode if state else "N/A", "status": state.status if state else "N/A"},
                "log_count": log_count,
                "connection": "OK"
            },
            "ai_model": {"status": ai_status, "test_result": ai_test},
            "system": {"django_version": "3.2+", "api_endpoints": [
                "/api/lighting-decision/",
                "/api/light-status/",
                "/api/set-light/",
                "/api/send-test-data/",
                "/api/get-current-logs/",
                "/api/system-status/"
            ]}
        }
        return Response(status_data)
    except Exception as e:
        logger.error(f"❌ Error in system_status: {e}")
        return Response({"status": "ERROR", "error": str(e), "timestamp": datetime.now().isoformat()}, status=500)


# ============================================================
# USER REGISTER + LOGIN (untuk dashboard)
# ============================================================
class RegisterSerializer(ModelSerializer):
    password = CharField(write_only=True)
    password2 = CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2')

    def validate(self, data):
        if data.get('password') != data.get('password2'):
            raise ValidationError("Password tidak sama.")
        return data

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data.get('username'),
            email=validated_data.get('email'),
            password=validated_data.get('password')
        )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        logger.info(f"👤 New user registered: {user.username}")
        return Response({"success": True, "message": "Registrasi berhasil!", "username": user.username}, status=status.HTTP_201_CREATED)
    logger.warning(f"⚠️ Registration failed: {serializer.errors}")
    return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(request, username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        logger.info(f"✅ User logged in: {username}")
        return Response({'success': True, 'refresh': str(refresh), 'access': str(refresh.access_token), 'username': user.username, 'message': 'Login berhasil'})
    logger.warning(f"⚠️ Login failed for user: {username}")
    return Response({'success': False, 'error': 'Username atau password salah'}, status=401)


# ============================================================
# LOG VIEWSET (WEB DASHBOARD)
# ============================================================
class LightingLogViewSet(viewsets.ModelViewSet):
    queryset = LightingLog.objects.all().order_by('-timestamp')
    serializer_class = LightingLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Hanya tampilkan log milik user yang login
        return LightingLog.objects.filter(user=self.request.user).order_by('-timestamp')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        logger.info(f"📝 Log created by user: {self.request.user.username}")
        # Broadcast new log
        try:
            log_data = serializer.data
            broadcast_to_websocket('sensor_data', {'data': [log_data], 'source': 'dashboard_api'})
        except Exception as e:
            logger.warning(f"⚠️ Could not broadcast new log: {e}")

    def list(self, request, *args, **kwargs):
        logger.info(f"📋 Logs requested by user: {request.user.username}")
        return super().list(request, *args, **kwargs)
