from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework.serializers import ModelSerializer, CharField, ValidationError

from .models import LightingLog
from .serializers import LightingLogSerializer
from .ai_model import predict_lighting_action  # Pastikan sudah diperbaiki!

# ============================================================
# SERIALIZER UNTUK REGISTER USER
# ============================================================
class RegisterSerializer(ModelSerializer):
    password = CharField(write_only=True)
    password2 = CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2')

    def validate(self, data):
        if data['password'] != data['password2']:
            raise ValidationError("Password tidak sama.")
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

# ============================================================
# VIEWSET UNTUK LOG LIGHTING
# ============================================================
class LightingLogViewSet(viewsets.ModelViewSet):
    queryset = LightingLog.objects.all().order_by('-timestamp')
    serializer_class = LightingLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LightingLog.objects.filter(user=self.request.user).order_by('-timestamp')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

# ============================================================
# REGISTER ENDPOINT
# ============================================================
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "Registrasi berhasil! Silakan login untuk mendapatkan token."},
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ============================================================
# LOGIN ENDPOINT (JWT)
# ============================================================
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_user(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({'error': 'Username dan password harus diisi'}, status=400)

    user = authenticate(request, username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'username': user.username,
        }, status=status.HTTP_200_OK)

    return Response({'error': 'Username atau password salah'}, status=status.HTTP_401_UNAUTHORIZED)

# ============================================================
# AI DECISION ENDPOINT (IoT) - ✅ SUDAH DIPERBAIKI
# ============================================================
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def lighting_decision_api(request):
    try:
        data = request.data

        # 🔹 Validasi fitur wajib
        required_features = ["ambient_light_lux", "day_of_week", "time_of_day", "weather_condition"]
        missing = [f for f in required_features if f not in data]
        if missing:
            return Response({"error": f"Fitur wajib hilang: {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)

        # 🔹 Ambil fitur
        lux = float(data["ambient_light_lux"])
        motion = int(data.get("motion_detected", 0))
        day = int(data["day_of_week"])
        time_of_day = int(data["time_of_day"])
        weather = int(data["weather_condition"])

        # 🔹 Prediksi - DAPATKAN NUMBER (0,1,2) ✅
        prediction_class = predict_lighting_action(lux, motion, day, time_of_day, weather)
        
        print(f"🎯 AI Prediction Result: {prediction_class} (type: {type(prediction_class)})")

        # 🔹 Simpan log - HANYA lighting_action_class ✅
        LightingLog.objects.create(
            user=request.user,
            ambient_light_lux=lux,
            motion_detected=motion,
            day_of_week=day,
            time_of_day=time_of_day,
            weather_condition=weather,
            lighting_action_class=prediction_class  # ✅ SIMPAN NUMBER LANGSUNG
        )

        return Response({
            "message": "Data sensor tersimpan dan diproses oleh AI.",
            "lighting_action_class": prediction_class,  # ✅ KIRIM NUMBER 0,1,2
            "ambient_light_lux": lux,
            "motion_detected": motion,
            "day_of_week": day,
            "time_of_day": time_of_day,
            "weather_condition": weather
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)