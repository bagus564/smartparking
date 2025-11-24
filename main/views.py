from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from .models import CustomUser, Spot, Reservation, Car, RealTimeSpot, Announcement
from django.contrib import messages
import logging
from datetime import datetime, time, date, timedelta
from django.contrib.auth.decorators import login_required, user_passes_test
import paho.mqtt.publish as publish
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.utils.dateparse import parse_date
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import localdate, localtime, now as tz_now, make_aware
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt 
from django.contrib.admin.views.decorators import staff_member_required
from functools import wraps
import json
import csv
import re

logger = logging.getLogger(__name__)

# --- HELPER DECORATOR ---
def admin_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_logged_in'): 
            return redirect('adminlogin') 
        return view_func(request, *args, **kwargs)
    return wrapper


# ========== AUTH ==========
def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']
        phone_number = request.POST['phone_number']

        errors = {}

        if CustomUser.objects.filter(username=username).exists():
            errors['username'] = "* Username is already taken."

        if CustomUser.objects.filter(email=email).exists():
            errors['email'] = "* Email is already registered."

        if password != confirm_password:
            errors['password'] = "* Passwords do not match."

        if errors:
            return render(request, 'register.html', {
                'errors': errors,
                'input': request.POST
            })

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            phone_number=phone_number
        )
        login(request, user)
        return redirect('login')
    return render(request, 'register.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            logger.debug(f"User {user.username} logged in successfully")
            return redirect('home')
        else:
            return render(request, 'login.html', {
                'error': "* Invalid username or password.",
                'input': request.POST
            })
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def home_view(request):
    return render(request, 'home.html')


# ========== RESERVATION ==========
@login_required(login_url='login')
def reservation_view(request):
    today = date.today()
    two_weeks = today + timedelta(days=14)

    if request.method == 'POST':
        # Ambil data dari form
        date_str = request.POST.get('date')
        start_hour = request.POST.get('start_time')
        end_hour = request.POST.get('end_time')
        spot_number = request.POST.get('slot')

        if not all([date_str, start_hour, end_hour, spot_number]):
            messages.error(request, "Please fill all fields")
            return redirect('reservation')

        # Ambil spot
        try:
            spot = Spot.objects.get(spot_number=int(spot_number))
        except Spot.DoesNotExist:
            messages.error(request, "Selected slot not found.")
            return redirect('reservation')

        if spot.is_disabled:
            messages.error(request, "This parking slot is currently disabled by admin.")
            return redirect('reservation')

        # Konversi waktu
        try:
            # Perhatikan: Di sini Anda menggunakan format "%m/%d/%Y" untuk datepicker, ini mungkin perlu disesuaikan
            date_obj = datetime.strptime(date_str, "%m/%d/%Y") 
            formatted_date = date_obj.strftime("%Y-%m-%d")
            
            # Gabungkan tanggal dan waktu, lalu buat aware (karena model menyimpan waktu aware)
            start_datetime_naive = datetime.strptime(
                f"{formatted_date} {start_hour}:00", "%Y-%m-%d %H:%M:%S"
            )
            end_datetime_naive = datetime.strptime(
                f"{formatted_date} {end_hour}:00", "%Y-%m-%d %H:%M:%S"
            )
            
            # Jadikan timezone aware menggunakan timezone saat ini
            start_datetime = timezone.make_aware(start_datetime_naive)
            end_datetime = timezone.make_aware(end_datetime_naive)

        except ValueError:
            messages.error(request, "Invalid date or time format.")
            return redirect('reservation')

        # Validasi jam (end_time harus > start_time)
        if end_datetime <= start_datetime:
            messages.error(request, "End time must be later than start time.")
            return redirect('reservation')

        # Cek apakah user sudah punya reservasi aktif di tanggal tsb
        existing_reservation = Reservation.objects.filter(
            user=request.user,
            start_time__date=date_obj.date(),
            end_time__gte=timezone.now()
        ).exists()

        if existing_reservation:
            messages.error(request, "You already have an active reservation for this date.")
            return redirect('reservation')

        # Cek tabrakan jadwal di slot yang sama
        overlap = Reservation.objects.filter(
 spot=spot,
 start_time__lt=end_datetime,
 end_time__gt=start_datetime,
    status='active'
).exists()

        if overlap:
            messages.error(request, "This slot is already reserved for the selected time.")
            return redirect('reservation')

        # Simpan reservasi baru
        reservation = Reservation.objects.create(
          user=request.user,
          spot=spot,
          start_time=start_datetime,
          end_time=end_datetime,
          status='active' 
          )

        # Opsional: langsung tambah mobil
        brand = request.POST.get('dropdown1')
        model = request.POST.get('dropdown2')
        color = request.POST.get('color')
        plate1 = request.POST.get('plate1')
        plate2 = request.POST.get('plate2')
        plate3 = request.POST.get('plate3')
        uploaded_image = request.FILES.get('imageUpload')

        if all([brand, model, color, plate1, plate2, plate3]):
            license_plate = f"{plate1} {plate2} {plate3.strip().upper()}"
            # Pastikan Car.objects.get_or_create diatur dengan benar
            car, created = Car.objects.get_or_create(
                user=request.user,
                license_plate=license_plate,
                defaults={
                    "brand": brand,
                    "model": model,
                    "color": color,
                    "image": uploaded_image
                }
            )
            reservation.car = car
            reservation.save()

        return redirect('history')

    # GET request
    return render(request, 'reservation.html', {
        'today': today.strftime('%Y-%m-%d'),
        'two_weeks': two_weeks.strftime('%Y-%m-%d'),
        'spots': Spot.objects.all(),
        'slot_range': range(1, 21) 
    })


# ========== STATUS & REALTIME ==========
def status_view(request):
    spots = Spot.objects.all()
    return render(request, 'status.html', {"spots": spots})


def realtime_parking_view(request):
    # Order by spot_number penting agar slot berurutan
    spots = Spot.objects.all().order_by("spot_number") 
    return render(request, "realtime.html", {"spots": spots})


# ========== RESERVATION DETAILS ==========
@login_required(login_url='login')
def reservation_details_view(request, reservation_id):
    try:
        reservation = Reservation.objects.get(id=reservation_id, user=request.user) # Tambah user filter
    except Reservation.DoesNotExist:
        # Gunakan HttpResponseForbidden jika user mencoba akses reservasi milik orang lain
        return HttpResponseForbidden("Anda tidak memiliki akses ke reservasi ini.") 

    if request.method == 'POST':
        # Logika ini untuk menambahkan mobil ke reservasi yang sudah ada
        brand = request.POST.get('dropdown1')
        model = request.POST.get('dropdown2')
        color = request.POST.get('color')
        plate1 = request.POST.get('plate1')
        plate2 = request.POST.get('plate2')
        plate3 = request.POST.get('plate3')
        uploaded_image = request.FILES.get('imageUpload')

        if not all([brand, model, color, plate1, plate2, plate3]):
             messages.error(request, "Semua detail mobil harus diisi.")
             return redirect('reservation_details', reservation_id=reservation_id)

        license_plate = f"{plate1} {plate2} {plate3.strip().upper()}"

        # Dapatkan atau buat objek Car
        car, created = Car.objects.get_or_create(
            user=request.user,
            license_plate=license_plate,
            defaults={
                "brand": brand,
                "model": model,
                "color": color,
                "image": uploaded_image,
            }
        )

        reservation.car = car
        reservation.save()

        messages.success(request, "Detail mobil berhasil ditambahkan.")
        return redirect('history')

    return render(request, 'reservation_details.html', {'reservation': reservation})


# ========== ACCOUNT ==========
@login_required(login_url='login')
def account_view(request):
    return render(request, 'account.html')


def update_account_view(request):
    if request.method == 'POST':
        user = request.user
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        phone_number = request.POST.get('phone_number')

        errors = {}

        if CustomUser.objects.filter(username=username).exclude(id=user.id).exists():
            errors['username'] = "* Username is already taken."

        if password and password != confirm_password:
            errors['password'] = "* Passwords do not match."

        if errors:
            return render(request, 'account.html', {
                'errors': errors,
                'input': request.POST
            })

        user.username = username
        user.phone_number = phone_number

        if password:
            user.set_password(password)
            user.save()
            login(request, user)
        else:
            user.save()

        messages.success(request, "Akun berhasil diperbarui.")
        return redirect('account')

    return redirect('account')


# ========== RESERVATION MANAGEMENT ==========
@login_required(login_url='login')
def delete_reservation(request, reservation_id):
    try:
        reservation = Reservation.objects.get(id=reservation_id, user=request.user)
        reservation.delete()
        messages.success(request, "Reservasi berhasil dibatalkan.")
    except Reservation.DoesNotExist:
        messages.error(request, "Reservasi tidak ditemukan atau Anda tidak memiliki izin.")

    next_page = request.GET.get('next', 'history')
    return redirect(next_page)


@login_required(login_url='login')
def history_view(request):
    now = timezone.now()
    reservations = Reservation.objects.filter(
        user=request.user,
    ).order_by('-start_time').select_related('car')
    
    for r in reservations:
        # Status aktif adalah jika waktu belum berakhir DAN status di DB adalah 'active'
        is_active_by_time = r.end_time >= now
        r.is_active = is_active_by_time and r.status == 'active' 
        
        # Tentukan status tampilan
        if r.status == 'canceled':
            r.display_status = 'Dibatalkan'
        elif r.end_time < now and r.status == 'active':
            r.display_status = 'Finished' # Status "Selesai" di UI
            # Opsional: Jika Anda ingin status DB berubah otomatis setelah selesai:
            # Reservation.objects.filter(id=r.id).update(status='finished')
        elif r.status == 'active':
            r.display_status = 'Active'
        else:
            r.display_status = r.status.capitalize()
    
    return render(request, 'history.html', {
    'reservations': reservations,
    'now': now
})


# ========== GUIDE & CONTACT ==========
def guide_view(request):
    return render(request, 'guide.html')


def contact_view(request):
    return render(request, 'contact.html')


# ========== ADMIN SECTION ==========
def adminlogin_view(request):
    if request.method == 'POST':
        password = request.POST.get('password')
        if password == 'parkircerdas':
            request.session['admin_logged_in'] = True
            return redirect('adminhome')
        else:
            return render(request, 'adminlogin.html', {
                'error': 'Password salah. Coba lagi.'
            })
    return render(request, 'adminlogin.html')


def adminlogout_view(request):
    request.session.flush()
    return redirect('adminlogin')


@admin_login_required
def adminhome_view(request):
    return render(request, 'adminhome.html')


@admin_login_required
def adminreservation_view(request):
    now = timezone.now()
    reservations = Reservation.objects.filter(
        end_time__gte=now # Hanya tampilkan yang masih aktif/belum berakhir
    ).order_by('start_time').select_related('car', 'user')
    return render(request, 'adminreservation.html', {
        'reservations': reservations
    })


@admin_login_required
def adminmonitoring_view(request):
    return render(request, 'adminmonitoring.html')

@admin_login_required
def adminrealtime_view(request):
    return render(request, 'adminrealtime.html')

@admin_login_required
def adminallreservations_view(request):
    """Menampilkan SEMUA riwayat reservasi untuk Admin (aktif, selesai, dibatalkan)."""
    from_date_str = request.GET.get('from')
    to_date_str = request.GET.get('to')
    now = timezone.now()

    # Ambil SEMUA reservasi
    reservations = Reservation.objects.select_related('car', 'user', 'spot').order_by('-start_time')

    if from_date_str:
        d = parse_date(from_date_str)
        if d:
            start_dt = make_aware(datetime.combine(d, time.min))
            reservations = reservations.filter(start_time__gte=start_dt)
    
    if to_date_str:
        d = parse_date(to_date_str)
        if d:
            end_dt = make_aware(datetime.combine(d, time.max))
            reservations = reservations.filter(start_time__lte=end_dt)

    # Menentukan status tampilan
    for r in reservations:
        if r.status == 'canceled':
            r.display_status = 'Dibatalkan'
        elif r.end_time < now and r.status == 'active':
            r.display_status = 'Selesai'
            # Opsional: Bisa di-update statusnya ke 'finished' di sini jika mau
        elif r.status == 'active':
            r.display_status = 'Aktif'
        else:
            r.display_status = r.status.capitalize()
            
    return render(request, 'admin_all_reservations.html', {
        'reservations': reservations,
    })


@admin_login_required
@require_http_methods(["POST"])
def mass_delete_reservations(request):
    """Mengubah status reservasi yang dipilih menjadi 'canceled' (bukan menghapus)."""
    reservation_ids = request.POST.getlist('reservation_ids')
    
    if not reservation_ids:
        messages.error(request, "Tidak ada reservasi yang dipilih.")
        return redirect('adminallreservations')

    try:
        # KUNCI: Update status menjadi 'canceled'
        updated_count = Reservation.objects.filter(
            id__in=reservation_ids
        ).update(status='canceled')

        messages.success(request, f"{updated_count} reservasi berhasil dibatalkan (Status: Canceled).")
    
    except Exception as e:
        messages.error(request, f"Terjadi kesalahan: {e}")

    return redirect('adminallreservations')

# ========== API JSON (STATUS UNTUK USER) ==========
def spots_dynamic_status_json(request):
    """
    Menyediakan status slot (reserved/available/occupied) untuk halaman pemesanan.
    Logika penting: Pada HARI INI, reservasi dianggap 'reserved' hanya jika belum berakhir.
    """
    selected_date_str = request.GET.get('date')
    if not selected_date_str:
        return JsonResponse({'error': 'No date provided'}, status=400)

    selected_date = parse_date(selected_date_str)
    if not selected_date:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    today = localdate()
    # Waktu sekarang yang sudah disesuaikan dengan timezone lokal
    current_time = localtime(tz_now()) 
    
    result = []

    for spot in Spot.objects.all().order_by('spot_number'):
        if spot.is_disabled:
            status = "disabled"
        else:
            if selected_date == today:
                # 🟢 LOGIKA PERBAIKAN: HARI INI
                # Cek reservasi yang benar-benar masih aktif (end_time belum lewat dari waktu sekarang)
                has_active_reservation_now = Reservation.objects.filter(
                    spot=spot,
                    start_time__date=selected_date,
                    end_time__gte=current_time 
                ).exists()

                if spot.status == "occupied":
                    status = "occupied"
                elif has_active_reservation_now:
                    status = "reserved"
                else:
                    status = "available"
            
            else:
                # Tanggal lain (masa depan atau masa lalu): Cek apakah ada reservasi (waktu saat ini tidak relevan)
                reserved_on_date = Reservation.objects.filter(
                    spot=spot,
                    start_time__date=selected_date
                ).exists()
                status = "reserved" if reserved_on_date else "available"

        result.append({
            "spot_number": spot.spot_number,
            "status": status,
            "buzzer_active": spot.buzzer_active,
        })

    return JsonResponse(result, safe=False)


# ========== API JSON (INTERVAL WAKTU RESERVASI) ==========
def get_reserved_times(start, end):
    blocked = []
    current = start
    while current <= end:
        blocked.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return blocked


def reserved_intervals_view(request):
    date_str = request.GET.get('date')
    spot_id = request.GET.get('spot')

    if not date_str or not spot_id:
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        spot = Spot.objects.get(spot_number=spot_id)
    except Spot.DoesNotExist:
        return JsonResponse({'error': 'Spot not found'}, status=404)

    try:
        # Parse tanggal dengan timezone awareness
        naive_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_of_day_naive = datetime.combine(naive_date, datetime.min.time())
        end_of_day_naive = datetime.combine(naive_date, datetime.max.time())
        
        start_of_day = make_aware(start_of_day_naive)
        end_of_day = make_aware(end_of_day_naive)
        
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    reservations = Reservation.objects.filter(
        spot=spot,
        # Filter yang lebih akurat
        start_time__date=naive_date 
    )
    
    # Jika tanggal yang dipilih adalah hari ini, tambahkan filter waktu
    today = localdate()
    current_time = None

    if naive_date == today:
      current_time = localtime(tz_now())
      reservations = reservations.filter(end_time__gte=current_time)



    blocked_intervals = []
    for r in reservations:
        start = localtime(r.start_time)
        end = localtime(r.end_time)
        
        # Pastikan kita tidak menampilkan interval yang sudah lewat di hari ini
        if naive_date == today and end <= current_time:
            continue
            
        blocked_intervals.append({
            'start': start.strftime("%H:%M"),
            'end': end.strftime("%H:%M")
        })

    return JsonResponse({'blocked_intervals': blocked_intervals})


# ========== API JSON (STATUS UNTUK ADMIN) ==========
def admin_home_details_json(request):
    """
    Return JSON berisi status, username, dan time (hari ini) untuk tiap slot.
    Logika penting: Pada HARI INI, reservasi dianggap 'reserved' hanya jika belum berakhir.
    """
    date_str = request.GET.get('date')
    target_date = parse_date(date_str) if date_str else localdate()
    if target_date is None:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    today = localdate()
    current_time = localtime(tz_now()) # Waktu lokal sekarang
    result = []

    for spot in Spot.objects.all().order_by('spot_number'):
        data = {
            "spot_number": spot.spot_number,
            "status": "available",
            "username": "",
            "time": ""
        }

        if spot.is_disabled:
            data["status"] = "disabled"
        else:
            # 🟢 LOGIKA PERBAIKAN: Ambil QuerySet
            if target_date == today:
                # HARI INI: Filter reservasi yang masih aktif saat ini
                reservation_qs = Reservation.objects.filter(
                    spot=spot,
                    start_time__date=target_date,
                    end_time__gte=current_time # Kunci perbaikan
                ).order_by('start_time')
            else:
                # Tanggal lain: Filter reservasi berdasarkan tanggal saja
                reservation_qs = Reservation.objects.filter(
                    spot=spot,
                    start_time__date=target_date
                ).order_by('start_time')

            has_reservation = reservation_qs.exists()

            # 3. Tentukan status
            if target_date == today:
                if spot.status == "occupied":
                    data["status"] = "occupied"
                elif has_reservation: # Cek hasil filter yang sudah benar
                    data["status"] = "reserved"
                else:
                    data["status"] = "available"
            else:
                # Untuk tanggal masa depan, jika ada reservasi, statusnya reserved
                data["status"] = "reserved" if has_reservation else "available"

            # 4. Isi detail username & waktu
            if data["status"] == "reserved":
                r = reservation_qs.first()
                if r:
                    data["username"] = r.user.username
                    st = localtime(r.start_time).strftime("%H:%M")
                    et = localtime(r.end_time).strftime("%H:%M")
                    data["time"] = f"{st} - {et}"
            
            # Jika status "occupied", kita asumsikan tidak ada detail reservasi yang ditampilkan
            # jika mobil masuk tanpa reservasi aktif, statusnya tetap occupied, username/time kosong.

        result.append(data)

    return JsonResponse(result, safe=False)


# ========== ADMIN ACTIONS (INDIVIDUAL SPOT) ==========
@require_POST
@admin_login_required
@csrf_exempt
def toggle_spot_disable(request):
    """
    Toggle satu atau beberapa slot.
    """
    try:
        data = json.loads(request.body.decode())
        spot_nums = data.get("spot_numbers", [])
        disable = bool(data.get("disable", False))

        if not spot_nums:
            return JsonResponse({"error": "No spot numbers provided"}, status=400)

        for spot_number in spot_nums:
            try:
                spot = Spot.objects.get(spot_number=spot_number)
                spot.is_disabled = disable
                spot.status = 'disabled' if disable else 'available'
                spot.save()

                # Kirim MQTT
                topic = f"parkir/slot{spot_number}/buzzer"
                payload = "disabled" if disable else "enable"

                publish.single(
                    topic,
                    payload,
                    hostname="192.168.12.151",
                    port=1883,
                    timeout=2 
                )
                logger.info(f"[MQTT] Slot {spot_number} -> {payload.upper()} dikirim.")
            except Spot.DoesNotExist:
                logger.warning(f"Spot {spot_number} tidak ditemukan.")
            except Exception as mqtt_error:
                logger.warning(f"[MQTT] Gagal kirim ke slot {spot_number}: {mqtt_error}")

        return JsonResponse({
            "success": True,
            "state": "disabled" if disable else "enabled"
        })

    except Exception as e:
        logger.error(f"Toggle slot error: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)


# ====================================================
#                ADMIN MATIKAN BUZZER
# ====================================================
@require_POST
@admin_login_required
@csrf_exempt
def admin_turn_off_buzzer(request):
    if request.method == "POST":
        data = json.loads(request.body)
        slot_number = data.get("slot_number")

        try:
            spot = Spot.objects.get(spot_number=slot_number)
            spot.buzzer_active = False
            spot.save()

            topic = f"parkir/slot{slot_number}/buzzer"
            publish.single(
                topic,
                "off",
                hostname="192.168.12.151",
                port=1883
            )
            print(f"✅ Buzzer untuk slot {slot_number} dimatikan oleh admin.")
            return JsonResponse({"success": True})

        except Spot.DoesNotExist:
            return JsonResponse({"success": False, "error": "Slot tidak ditemukan"})

    return JsonResponse({"success": False, "error": "Metode bukan POST"})


# ====================================================
#                USER MATIKAN BUZZER
# ====================================================
@require_POST
@login_required
@csrf_exempt
def user_turn_off_buzzer(request):
    data = json.loads(request.body)
    slot_number = data.get("slot_number")

    try:
        spot = Spot.objects.get(spot_number=slot_number)

        # 💥 CEK apakah user punya reservasi aktif SEKARANG
        now = timezone.localtime()

        has_active = Reservation.objects.filter(
            user=request.user,
            spot=spot,
            start_time__lte=now,
            end_time__gte=now,  # masih aktif
        ).exists()

        if not has_active:
            return JsonResponse({
                "success": False,
                "error": "Anda tidak memiliki reservasi aktif saat ini."
            })

        # Jika lolos → boleh matikan buzzer
        spot.buzzer_active = False
        spot.save()

        topic = f"parkir/slot{slot_number}/buzzer"
        publish.single(
            topic,
            "off",
            hostname="192.168.12.151",
            port=1883
        )

        return JsonResponse({"success": True})

    except Spot.DoesNotExist:
        return JsonResponse({"success": False, "error": "Slot tidak ditemukan"})




# ========== ADMIN ACTIONS (ALL SPOTS) ==========
@csrf_exempt
@require_POST
@admin_login_required
def toggle_all_spots_disable(request):
    """
    Toggle global disable semua spot.
    """
    try:
        any_enabled = Spot.objects.filter(is_disabled=False).exists()

        if any_enabled:
            # 🔴 Disable semua spot
            Spot.objects.update(is_disabled=True, status='maintenance')
            new_state = 'disabled'
            mqtt_payload = "disabled"
            print("[ACTION] Semua slot akan dinonaktifkan.")

        else:
            # 🟢 Enable semua spot
            Spot.objects.filter(is_disabled=True).update(is_disabled=False)
            Spot.objects.filter(status='maintenance', is_disabled=False).update(status='available')
            new_state = 'enabled'
            mqtt_payload = "enable"
            print("[ACTION] Semua slot akan diaktifkan kembali.")

        # Kirim MQTT ke semua slot
        for spot in Spot.objects.all():
            topic = f"parkir/slot{spot.spot_number}/buzzer"
            try:
                publish.single(
                    topic,
                    mqtt_payload,
                    hostname="192.168.12.151",
                    port=1883,
                    keepalive=3,
                    timeout=3 
                )
                print(f"[MQTT ✅] Slot {spot.spot_number} -> {mqtt_payload.upper()}")
            except Exception as mqtt_err:
                print(f"[MQTT ⚠️] Slot {spot.spot_number} gagal: {mqtt_err}")

        return JsonResponse({'success': True, 'state': new_state})

    except Exception as e:
        logger.error(f"[ERROR] Toggle semua spot gagal: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@admin_login_required
def spots_state(request):
    """
    Return apakah semua spot saat ini disabled.
    """
    any_enabled = Spot.objects.filter(is_disabled=False).exists()
    return JsonResponse({'all_disabled': not any_enabled})


# ========== EXPORT RESERVATIONS (ADMIN) ==========
@admin_login_required
def export_reservations(request):
    """
    Export reservations as CSV. Optional GET param: ?date=YYYY-MM-DD
    """
    date_str = request.GET.get('date')
    qs = Reservation.objects.select_related('user', 'car', 'spot').order_by('start_time')

    if date_str:
        d = parse_date(date_str)
        if d:
            qs = qs.filter(start_time__date=d)

    filename = f"reservations_{date_str or 'all'}.csv"
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Username", "Date", "Start Time", "End Time", "Spot",
        "Phone", "Car Brand", "Car Model", "Car Color", "License Plate"
    ])

    for r in qs:
        writer.writerow([
            r.user.username,
            r.start_time.date().isoformat(),
            localtime(r.start_time).strftime("%H:%M"),
            localtime(r.end_time).strftime("%H:%M"),
            (r.spot.spot_number if r.spot else ""),
            (r.user.phone_number or ""),
            (r.car.brand if r.car else ""),
            (r.car.model if r.car else ""),
            (r.car.color if r.car else ""),
            (r.car.license_plate if r.car else ""),
        ])
    return response

# ---------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------

# Helper untuk sorting berdasarkan angka dalam spot_number
def spot_sort_key(spot):
    match = re.search(r'\d+', spot.spot_number)
    return int(match.group()) if match else 0

# ---------------------------------------------------
# VIEWS UNTUK PENGGUNA (Non-Admin)
# ---------------------------------------------------

def realtime_parking_view(request):
    """
    Merender halaman Realtime Parking untuk pengguna.
    """
    spots = sorted(RealTimeSpot.objects.all(), key=spot_sort_key)

    # Normalisasi status: hilangkan reservasi/status lain menjadi "Perbaikan/Acara"
    for spot in spots:
        if spot.status.lower() not in ["terisi", "kosong"]:
            spot.status = "Perbaikan/Acara"

    mid = len(spots) // 2
    left_row = spots[:mid]
    right_row = spots[mid:]

    return render(request, 'realtime.html', {
        'left_row': left_row,
        'right_row': right_row,
    })

def realtime_data(request):
    """
    API Polling Data Realtime untuk pengguna (Public).
    """
    spots = sorted(RealTimeSpot.objects.all(), key=spot_sort_key)
    data = []

    for spot in spots:
        status = spot.status
        # Normalisasi status (seperti di view render)
        if status.lower() not in ["terisi", "kosong"]:
            status = "Perbaikan/Acara"
            
        data.append({
            'spot_number': spot.spot_number,
            'distance': spot.distance,
            'status': status,
            'updated_at': spot.updated_at.strftime('%Y-%m-%d %H:%M:%S') if spot.updated_at else None,
        })

    return JsonResponse(data, safe=False)


# ---------------------------------------------------
# VIEWS UNTUK ADMIN (Client Data Center)
# ---------------------------------------------------


@admin_login_required
def adminrealtime_view(request):
    """
    Merender halaman Realtime Monitoring Admin.
    """
    spots = sorted(RealTimeSpot.objects.all(), key=spot_sort_key)
    return render(request, 'main/adminrealtime.html', {
        'slot_list': spots,
    })


@admin_login_required
def realtime_data_admin_api(request):
    """
    API Polling Data Realtime untuk Admin.
    Mengirim status yang dinormalisasi dan data lengkap.
    """
    if request.method == 'GET':
        try:
            spots = sorted(RealTimeSpot.objects.all(), key=spot_sort_key)
            data = []

            for spot in spots:
                status = spot.status
                # Normalisasi untuk tampilan Admin
                normalized_status = status
                if status.lower() not in ["terisi", "kosong", "disabled"]:
                    # Karena tidak ada reservasi, status lain dianggap Disabled
                    normalized_status = "Disabled"
                    
                data.append({
                    'spot_number': spot.spot_number,
                    'distance': spot.distance,
                    'status': normalized_status,
                    'buzzer_active': spot.buzzer_active, 
                    'updated_at': spot.updated_at.strftime('%Y-%m-%d %H:%M:%S') if spot.updated_at else None,
                })
            
            return JsonResponse(data, safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@admin_login_required
@require_POST
def admin_set_spot_status_api(request):
    """
    API untuk Admin mengubah status slot (mis. Set Disabled/Perbaikan).
    """
    try:
        data = json.loads(request.body)
        spot_numbers = data.get('spot_numbers', [])
        status = data.get('status') # Status target dari dropdown (Kosong, Terisi, Disabled)
        
        if not spot_numbers or not status:
            return JsonResponse({'success': False, 'error': 'Spot numbers atau status tidak valid.'}, status=400)

        # Pastikan status yang diterima adalah status yang valid di model
        valid_statuses = [c[0] for c in RealTimeSpot.STATUS_CHOICES]
        if status not in valid_statuses:
             return JsonResponse({'success': False, 'error': 'Status yang diminta tidak valid.'}, status=400)


        spots_to_update = RealTimeSpot.objects.filter(spot_number__in=spot_numbers)

        if not spots_to_update.exists():
            return JsonResponse({'success': False, 'error': 'Tidak ada spot yang ditemukan untuk diperbarui.'}, status=404)

        # Lakukan pembaruan massal
        spots_to_update.update(status=status)

        return JsonResponse({
            'success': True, 
            'message': f'Berhasil memperbarui {spots_to_update.count()} spot menjadi {status}.'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    
@csrf_exempt
@require_POST
def add_announcement(request):
    try:
        data = json.loads(request.body)
        
        # Simpan ke database
        Announcement.objects.create(
            title=data['title'],
            description=data.get('description', ''), # Menggunakan .get() jika deskripsi tidak ada
            slot_numbers=data['slot_numbers'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            label_color=data['color'],
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# 2.2 API untuk Mengambil Daftar Pengumuman (GET - Dipanggil oleh loadAnnouncements() di adminrealtime.html)
@require_GET
def get_announcements_list(request):
    announcements = Announcement.objects.all() # Ambil semua, Admin harus melihat semua
    data = [{
        'id': ann.id,
        'title': ann.title,
        'description': ann.description,
        'slot_numbers': ann.slot_numbers,
        'start_date': ann.start_date.strftime("%Y-%m-%d"),
        'end_date': ann.end_date.strftime("%Y-%m-%d"),
        'label_color': ann.label_color,
        'created_at': ann.created_at.strftime("%Y-%m-%d %H:%M"),
    } for ann in announcements]
    return JsonResponse(data, safe=False)


# 2.3 API untuk Mengambil Pengumuman AKTIF (GET - Dipanggil oleh loadAnnouncements() di realtime.html)
@require_GET
def get_active_announcements(request):
    today = date.today()
    
    # Filter pengumuman yang aktif hari ini
    announcements = Announcement.objects.filter(
        start_date__lte=today, 
        end_date__gte=today,
        is_active=True
    )

    data = [{
        'title': ann.title,
        'description': ann.description,
        'slot_numbers': ann.slot_numbers,
        'start_date': ann.start_date.strftime("%d-%m-%Y"),
        'end_date': ann.end_date.strftime("%d-%m-%Y"),
        'label_color': ann.label_color,
    } for ann in announcements]
    
    return JsonResponse({'announcements': data})

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_announcement(request, pk):
    try:
        announcement = Announcement.objects.get(pk=pk)
        announcement.delete()
        return JsonResponse({'success': True, 'message': f'Pengumuman ID {pk} berhasil dihapus.'})
    except Announcement.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Pengumuman tidak ditemukan.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    