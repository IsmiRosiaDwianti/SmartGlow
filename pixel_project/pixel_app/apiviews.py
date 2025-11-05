from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework.serializers import ModelSerializer, CharField, ValidationError
from datetime import datetime

from .models import LightingLog
from .serializers import LightingLogSerializer
from .ai_model import predict_lighting_action

# ================= REGISTER =================
class RegisterSerializer(ModelSerializer):
    password = CharField(write_only=True)
    password2 = CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username','email','password','password2')

    def validate(self, data):
        if data['password'] != data['password2']:
            raise ValidationError("Password tidak sama.")
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
        serializer.save()
        return Response({"message":"Registrasi berhasil!"}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ================= LOGIN =================
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_user(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(request, username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({'refresh': str(refresh),'access': str(refresh.access_token),'username': user.username})
    return Response({'error':'Username atau password salah'}, status=401)

# ================= AI ENDPOINT =================
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def lighting_decision_api(request):
    try:
        data = request.data
        lux = float(data.get('ambient_light_lux', 0))

        # Generate fitur lain dari logika
        motion = 1 if lux < 100 else 0
        weather = 0 if lux > 200 else 1
        now = datetime.now()
        time_of_day = (lambda h: 1 if 6<=h<12 else 2 if 12<=h<18 else 3 if 18<=h<24 else 0)(now.hour)
        day = now.weekday()

        prediction_class = predict_lighting_action(lux, motion, day, time_of_day, weather)
        if prediction_class not in [0,1,2]:
            prediction_class = 0

        LightingLog.objects.create(
            user=request.user,
            ambient_light_lux=lux,
            motion_detected=motion,
            day_of_week=day,
            time_of_day=time_of_day,
            weather_condition=weather,
            lighting_action_class=prediction_class
        )

        return Response({
            'ambient_light_lux': lux,
            'motion_detected': motion,
            'day_of_week': day,
            'time_of_day': time_of_day,
            'weather_condition': weather,
            'lighting_action_class': prediction_class
        })

    except Exception as e:
        return Response({"error": str(e)}, status=400)

# ================= LOG VIEWSET =================
class LightingLogViewSet(viewsets.ModelViewSet):
    queryset = LightingLog.objects.all().order_by('-timestamp')
    serializer_class = LightingLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LightingLog.objects.filter(user=self.request.user).order_by('-timestamp')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
