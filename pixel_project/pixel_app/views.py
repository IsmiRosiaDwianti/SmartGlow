from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from .models import LightingLog
import joblib
import os


# ================================
# REGISTER VIEW
# ================================
def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')

        if not username or not password or not confirm:
            messages.error(request, "Semua kolom harus diisi.")
            return redirect('register')

        if password != confirm:
            messages.error(request, "Password tidak cocok.")
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username sudah terdaftar.")
            return redirect('register')

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        messages.success(request, "Registrasi berhasil! Silakan login.")
        return redirect('login')

    return render(request, 'pixel_app/register.html')


# ================================
# LOGIN VIEW
# ================================
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Selamat datang, {username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Username atau password salah.")
            return redirect('login')

    return render(request, 'pixel_app/login.html')


# ================================
# LOGOUT VIEW
# ================================
def logout_view(request):
    logout(request)
    messages.success(request, "Anda telah logout.")
    return redirect('login')


# ================================
# DASHBOARD VIEW
# ================================
def dashboard_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "Silakan login terlebih dahulu.")
        return redirect('login')

    logs = LightingLog.objects.filter(user=request.user).order_by('-timestamp')[:10]

    # Load data pkl (opsional)
    pkl_data = []
    pkl_path = os.path.join(
        os.path.dirname(__file__), 
        'processed_data',
        'smart_lighting_processed_2024.pkl'
    )

    if os.path.exists(pkl_path):
        try:
            data = joblib.load(pkl_path)
            pkl_data = data.tail(5).to_dict(orient='records')
        except Exception as e:
            messages.error(request, f"Gagal memuat data dari file: {str(e)}")

    context = {
        'logs': logs,
        'pkl_data': pkl_data
    }

    return render(request, 'pixel_app/dashboard.html', context)
