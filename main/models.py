from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.exceptions import ValidationError

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
    
    STATUS_CHOICES = [
        ('available', 'Tersedia'),
        ('reserved', 'Reservasi'),
        ('occupied', 'Tidak Tersedia'),
        ('maintenance', 'Perbaikan'), 
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_disabled = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)
    buzzer_active = models.BooleanField(default=False)

    def update_status_from_distance(self, distance_cm):
        """
        Update status kendaraan berdasarkan jarak sensor.
        Hanya save jika status berubah.
        """
        if self.is_disabled:
            new_status = 'maintenance'
        else:
            new_status = 'occupied' if distance_cm < 100 else 'available'
        
        if new_status != self.status:
            self.status = new_status
            self.buzzer_active = (new_status == 'occupied')
            self.save(update_fields=['status', 'buzzer_active', 'last_updated'])

    def get_color(self):
        """Kembalikan warna sesuai status (buat realtime UI)"""
        colors = {
            'available': 'bg-blue-500',      # Tersedia
            'reserved': 'bg-green-500',      # Reservasi
            'occupied': 'bg-red-500',        # Tidak Tersedia
            'maintenance': 'bg-yellow-400',  # Perbaikan
        }
        return colors.get(self.status, 'bg-gray-300')

    def __str__(self):
        return f"Spot {self.spot_number} - {self.status}"


# -----------------------------
# Reservation
# -----------------------------
class Reservation(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    spot = models.ForeignKey(Spot, on_delete=models.CASCADE)
    car = models.ForeignKey(Car, on_delete=models.SET_NULL, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def __str__(self):
        return f"Reservation by {self.user.username} from {self.start_time} to {self.end_time}"

    def is_active(self):
        now = timezone.now()
        return self.start_time <= now <= self.end_time

    def clean(self):
        # Validasi waktu
        if self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time.")
        
        # Validasi tumpang tindih
        overlapping = Reservation.objects.filter(
            spot=self.spot,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError("This spot is already reserved for the selected time.")

    def save(self, *args, **kwargs):
        # Jalankan validasi sebelum save
        self.clean()
        super().save(*args, **kwargs)
