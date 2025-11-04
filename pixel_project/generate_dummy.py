import os
import django
import random
from faker import Faker
from django.utils import timezone
from datetime import timedelta

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pixel_project.settings')
django.setup()

from pixel_app.models import Room, LightStatus

fake = Faker('id_ID')

def create_light_status():
    """Buat data dummy LightStatus untuk dashboard"""
    # Hapus data lama biar fresh
    LightStatus.objects.all().delete()
    
    # Pastikan ada room
    room, created = Room.objects.get_or_create(
        name="Ruang Utama",
        device_id="ESP32-MAIN-01",
        defaults={"description": "Ruangan utama dengan sensor cahaya"}
    )
    
    print(f"💡 Membuat data sensor:")
    
    # Buat 50 data dengan variasi waktu dan kondisi
    for i in range(50):
        # Tentukan waktu - data terbaru sampai 48 jam kebelakang
        hours_ago = random.randint(0, 48)
        minutes_ago = random.randint(0, 59)
        
        timestamp = timezone.now() - timedelta(hours=hours_ago, minutes=minutes_ago)
        hour = timestamp.hour
        
        # Logika berdasarkan waktu
        if hour >= 18 or hour <= 6:  # Malam hari
            lux = round(random.uniform(10, 100), 2)
            is_on = True  # Malam hari lampu biasanya hidup
        else:  # Siang hari
            lux = round(random.uniform(300, 800), 2)
            is_on = False  # Siang hari lampu biasanya mati
        
        # Tambahkan sedikit variasi
        if random.random() < 0.1:  # 10% chance untuk kondisi tidak biasa
            if is_on:
                lux = round(random.uniform(150, 300), 2)  # Lux sedang, lampu hidup
            else:
                lux = round(random.uniform(50, 150), 2)   # Lux rendah, lampu mati
        
        status_text = "HIDUP" if is_on else "MATI"
        
        # Simpan data
        LightStatus.objects.create(
            room=room,
            lux_value=lux,
            is_on=is_on,
            timestamp=timestamp
        )
        
        if i < 5:  # Print sample data
            print(f"   - {timestamp.strftime('%H:%M')} | Lux: {lux} | {status_text}")
    
    print(f"✅ 50 data sensor berhasil dibuat")

if __name__ == "__main__":
    print("🚀 Membuat data dummy...")
    create_light_status()
    print("🎉 Data dummy berhasil dibuat!")