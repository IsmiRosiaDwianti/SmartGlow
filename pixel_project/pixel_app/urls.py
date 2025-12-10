from django.urls import path, include
from rest_framework import routers
from . import views
from .apiviews import (
    LightingLogViewSet,
    register_user,
    login_user,
    lighting_decision_api,
    get_light_status,
    set_light_status,
)

router = routers.DefaultRouter()
router.register(r'lighting-log', LightingLogViewSet, basename='lightinglog')

urlpatterns = [
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),

    path('api/', include(router.urls)),

    path('api/register/', register_user),
    path('api/login/', login_user),

    # IoT + AI
    path('api/lighting-decision/', lighting_decision_api),

    # Manual Control
    path('api/light-status/', get_light_status),
    path('api/set-light/', set_light_status),
]
