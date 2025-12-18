from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
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
        
        if len(password) < 6:
            messages.error(request, "Password minimal 6 karakter.")
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username sudah terdaftar.")
            return redirect('register')

        # Validasi kompleksitas password
        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, ', '.join(e.messages))
            return redirect('register')

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        messages.success(request, "Registrasi berhasil! Silakan login.")
        return redirect('login')

    return render(request, 'pixel_app/register.html')


# ================================
# LOGIN & FORGOT PASSWORD VIEW
# ================================
def login_view(request):
    """
    Menangani login dan reset password dalam satu view
    """
    if request.method == 'POST':
        # Cek apakah ini request reset password
        if 'reset_password' in request.POST:
            # PROSES RESET PASSWORD
            username = request.POST.get('reset_username', '').strip()
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            
            # Validasi input reset password
            if not username or not new_password or not confirm_password:
                messages.error(request, "Semua field harus diisi.")
                return render(request, 'pixel_app/login.html')
            
            if new_password != confirm_password:
                messages.error(request, "Password baru dan konfirmasi tidak cocok.")
                return render(request, 'pixel_app/login.html')
            
            if len(new_password) < 6:
                messages.error(request, "Password minimal 6 karakter.")
                return render(request, 'pixel_app/login.html')
            
            # Validasi kompleksitas password
            try:
                validate_password(new_password)
            except ValidationError as e:
                messages.error(request, ', '.join(e.messages))
                return render(request, 'pixel_app/login.html')
            
            # Cari user berdasarkan username
            try:
                user = User.objects.get(username=username)
                # Update password
                user.set_password(new_password)
                user.save()
                
                # Kirim pesan sukses
                messages.success(
                    request, 
                    f"Password untuk '{username}' berhasil direset! Silakan login dengan password baru."
                )
                return redirect('login')
                
            except User.DoesNotExist:
                messages.error(request, "Username tidak cocok.")
                return render(request, 'pixel_app/login.html')
        
        else:
            # PROSES LOGIN BIASA
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

    # GET request - tampilkan halaman login
    return render(request, 'pixel_app/login.html')


# ================================
# SIMPLE FORGOT PASSWORD VIEW (Alternatif)
# ================================
def forgot_password_view(request):
    """
    View alternatif jika ingin halaman lupa password terpisah
    """
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validasi input
        if not username or not new_password or not confirm_password:
            messages.error(request, "Semua field harus diisi.")
            return render(request, 'pixel_app/forgot_password.html')
        
        if new_password != confirm_password:
            messages.error(request, "Password baru dan konfirmasi tidak cocok.")
            return render(request, 'pixel_app/forgot_password.html')
        
        if len(new_password) < 6:
            messages.error(request, "Password minimal 6 karakter.")
            return render(request, 'pixel_app/forgot_password.html')
        
        # Validasi kompleksitas password
        try:
            validate_password(new_password)
        except ValidationError as e:
            messages.error(request, ', '.join(e.messages))
            return render(request, 'pixel_app/forgot_password.html')
        
        # Cari user berdasarkan username
        try:
            user = User.objects.get(username=username)
            # Update password
            user.set_password(new_password)
            user.save()
            
            messages.success(
                request, 
                f"Password untuk '{username}' berhasil direset! Silakan login dengan password baru."
            )
            return redirect('login')
            
        except User.DoesNotExist:
            messages.error(request, "Username tidak ditemukan dalam database.")
            return render(request, 'pixel_app/forgot_password.html')
    
    return render(request, 'pixel_app/forgot_password.html')


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


# ================================
# HELPER FUNCTIONS
# ================================
def validate_user_input(username, password, confirm_password=None):
    """
    Helper function untuk validasi input user
    """
    errors = []
    
    if not username or len(username) < 3:
        errors.append("Username minimal 3 karakter.")
    
    if not password or len(password) < 6:
        errors.append("Password minimal 6 karakter.")
    
    if confirm_password is not None and password != confirm_password:
        errors.append("Password dan konfirmasi password tidak cocok.")
    
    return errors


def check_username_exists(username):
    """
    Helper function untuk mengecek apakah username sudah terdaftar
    """
    return User.objects.filter(username=username).exists()