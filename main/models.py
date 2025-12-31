from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.http import JsonResponse

# -----------------------------
# Custom User
# -----------------------------
class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('user', 'User'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')

    def __str__(self):
        return self.username


# -----------------------------
# Car
# -----------------------------
class Car(models.Model):
    license_plate = models.CharField(max_length=20, unique=True)
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    color = models.CharField(max_length=100)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='cars')
    image = models.ImageField(upload_to='car_image/', null=True, blank=True)

    def __str__(self):
        return f"{self.brand} {self.model} ({self.license_plate})"


# -----------------------------
# Spot (gabungan ParkingSlot)
# -----------------------------
class Spot(models.Model):
    spot_number = models.CharField(max_length=20, unique=True)
    buzzer_muted = models.BooleanField(default=False)

    STATUS_CHOICES = [
        ('available', 'Tersedia'),
        ('reserved', 'Reservasi'),
        ('occupied', 'Tidak Tersedia'),
        ('maintenance', 'Perbaikan'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available'
    )
    is_disabled = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)
    buzzer_active = models.BooleanField(default=False)

    # ==========================================
    # UPDATE STATUS DARI SENSOR (FINAL LOGIC)
    # ==========================================
    def update_status_from_distance(self, distance_cm):
        if self.is_disabled:
            new_status = 'maintenance'
        else:
            new_status = 'occupied' if distance_cm < 10 else 'available'

        # 🚗 MOBIL BARU MASUK
        if (
            self.status == 'available'
            and new_status == 'occupied'
            and not self.buzzer_muted
        ):
            self.buzzer_active = True

        # 🚗 MOBIL KELUAR
        if self.status == 'occupied' and new_status == 'available':
            self.buzzer_active = False
            self.buzzer_muted = False

        if new_status != self.status:
            self.status = new_status

        self.save(update_fields=[
            'status',
            'buzzer_active',
            'buzzer_muted',
            'last_updated'
        ])

    # ==========================================
    # WARNA UI
    # ==========================================
    def get_color(self):
        colors = {
            'available': 'bg-blue-500',
            'reserved': 'bg-green-500',
            'occupied': 'bg-red-500',
            'maintenance': 'bg-yellow-400',
        }
        return colors.get(self.status, 'bg-gray-300')

    def __str__(self):
        return f"Spot {self.spot_number} - {self.status}"


# -----------------------------
# Reservation (DITAMBAH FIELD STATUS)
# -----------------------------
class Reservation(models.Model):
    # 🟢 DEFINISI PILIHAN STATUS BARU
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('canceled', 'Canceled'),
        ('finished', 'Finished'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    spot = models.ForeignKey(Spot, on_delete=models.CASCADE)
    car = models.ForeignKey(Car, on_delete=models.SET_NULL, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    # 🟢 FIELD STATUS BARU
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active' 
    )
    # -----------------------------

    def __str__(self):
        # Diperbarui untuk menampilkan status
        return f"Reservation by {self.user.username} from {self.start_time} to {self.end_time} ({self.status})"

    def is_active(self):
        now = timezone.now()
        # Diperbarui: Reservasi aktif jika statusnya 'active' dan belum berakhir waktunya
        return self.status == 'active' and self.end_time > now

    def clean(self):
        # Validasi waktu
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time.")
        
        # Validasi tumpang tindih
        # Diperbarui: Hanya cek tumpang tindih dengan reservasi yang masih 'active'
        overlapping = Reservation.objects.filter(
            spot=self.spot,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
            status='active'
        ).exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError("This spot is already reserved for the selected time.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class RealTimeSpot(models.Model):
    spot_number = models.CharField(max_length=10, unique=True)
    distance = models.FloatField(default=0, help_text="Jarak objek ke sensor")
    
    # Pilihan Status Dibatasi: Hanya untuk Realtime & Maintenance
    STATUS_CHOICES = [
        ('Kosong', 'Kosong'),
        ('Terisi', 'Terisi'),
        ('Disabled', 'Perbaikan/Acara'), 
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Kosong')
    
    buzzer_active = models.BooleanField(default=False) 
    updated_at = models.DateTimeField(auto_now=True)

    def update_status_from_distance(self, new_distance):
        self.distance = new_distance
        
        # Lindungi status "Disabled" (Perbaikan/Acara)
        if self.status == 'Disabled':
            self.save(update_fields=['distance', 'updated_at'])
            return 
            
        # Logika pembaruan status berdasarkan sensor
        THRESHOLD = 10.0 
        
        new_status = self.status
        
        if new_distance < THRESHOLD:
            new_status = "Terisi"
        else:
            new_status = "Kosong"
            
        # Simpan hanya jika ada perubahan pada status atau distance
        if self.status != new_status or self.distance != new_distance:
             self.status = new_status
             self.save()

    def __str__(self):
        return f"{self.spot_number} - {self.status}"
    
class Announcement(models.Model):
    SLOT_CHOICES = (
        ('yellow', 'Kuning'),
        ('red', 'Merah'),
        ('gray', 'Abu-abu'),
          )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    slot_numbers = models.CharField(max_length=200, help_text="Contoh: 1, 2, 5-8")
    start_date = models.DateField()
    end_date = models.DateField()
    label_color = models.CharField(max_length=10, choices=SLOT_CHOICES, default='yellow')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.start_date} - {self.end_date})"
    