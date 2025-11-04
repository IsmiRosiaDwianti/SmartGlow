from django.urls import path, include
from rest_framework import routers
from . import views
from .apiviews import (
    LightingLogViewSet,
    register_user,
    login_user,
    lighting_decision_api
)

# Router untuk endpoint API model LightingLog
router = routers.DefaultRouter()
router.register(r'lighting-log', LightingLogViewSet, basename='lightinglog')

urlpatterns = [
    # 🔹 Halaman frontend (HTML views)
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),

    # 🔹 Endpoint API untuk model LightingLog
    path('api/', include(router.urls)),

    # 🔹 Endpoint API untuk autentikasi (register & login)
    path('api/register/', register_user, name='api_register'),
    path('api/login/', login_user, name='api_login'),

    # 🔹 Endpoint API untuk keputusan AI (IoT)
    path('api/lighting-decision/', lighting_decision_api, name='lighting_decision_api'),
]
