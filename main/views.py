from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from .models import CustomUser, Spot, Reservation, Car
from django.contrib import messages
import logging
from datetime import datetime, date, timedelta
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.utils.timezone import localdate, make_aware, localtime
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import paho.mqtt.publish as publish
from functools import wraps
import json

logger = logging.getLogger(__name__)


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
            date_obj = datetime.strptime(date_str, "%m/%d/%Y")
            formatted_date = date_obj.strftime("%Y-%m-%d")
            start_datetime = datetime.strptime(
                f"{formatted_date} {start_hour}:00", "%Y-%m-%d %H:%M:%S"
            )
            end_datetime = datetime.strptime(
                f"{formatted_date} {end_hour}:00", "%Y-%m-%d %H:%M:%S"
            )
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
            end_time__gt=start_datetime
        ).exists()

        if overlap:
            messages.error(request, "This slot is already reserved for the selected time.")
            return redirect('reservation')

        # Simpan reservasi baru
        reservation = Reservation.objects.create(
            user=request.user,
            spot=spot,
            start_time=start_datetime,
            end_time=end_datetime
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
        'slot_range': range(1, 21)  # tampilkan slot 01–20
    })


# ========== STATUS & REALTIME ==========
def status_view(request):
    spots = Spot.objects.all()
    return render(request, 'status.html', {"spots": spots})


def realtime_parking_view(request):
    spots = Spot.objects.all().order_by("spot_number")
    left_row = spots[:10]
    right_row = spots[10:20]
    return render(request, "realtime.html", {"left_row": left_row, "right_row": right_row})


# ========== RESERVATION DETAILS ==========
@login_required(login_url='login')
def reservation_details_view(request, reservation_id):
    try:
        reservation = Reservation.objects.get(id=reservation_id)
    except Reservation.DoesNotExist:
        return render(request, 'reservation_details.html', {'error': 'Reservation not found'})

    if request.method == 'POST':
        brand = request.POST.get('dropdown1')
        model = request.POST.get('dropdown2')
        color = request.POST.get('color')
        plate1 = request.POST.get('plate1')
        plate2 = request.POST.get('plate2')
        plate3 = request.POST.get('plate3')
        uploaded_image = request.FILES.get('imageUpload')

        license_plate = f"{plate1} {plate2} {plate3.strip().upper()}"

        car = Car.objects.create(
            user=request.user,
            brand=brand,
            model=model,
            color=color,
            license_plate=license_plate,
            image=uploaded_image,
        )

        reservation.car = car
        reservation.save()

        return redirect('account')

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
def delete_reservation(request, reservation_id):
    reservation = Reservation.objects.get(id=reservation_id)
    reservation.delete()
    next_page = request.GET.get('next', 'history')
    return redirect(next_page)


def history_view(request):
    now = timezone.now()
    reservations = Reservation.objects.filter(
        user=request.user,
        end_time__gte=now
    ).order_by('-start_time').select_related('car')
    return render(request, 'history.html', {
        'reservations': reservations
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


def admin_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_logged_in'):
            return redirect('adminlogin')
        return view_func(request, *args, **kwargs)
    return wrapper


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
        end_time__gte=now
    ).order_by('-start_time').select_related('car', 'user')
    return render(request, 'adminreservation.html', {
        'reservations': reservations
    })


@admin_login_required
def adminmonitoring_view(request):
    return render(request, 'adminmonitoring.html')


# ========== API JSON ==========
def spots_dynamic_status_json(request):
    selected_date_str = request.GET.get('date')
    if not selected_date_str:
        return JsonResponse({'error': 'No date provided'}, status=400)

    selected_date = parse_date(selected_date_str)
    if not selected_date:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    today = localdate()
    result = []

    for spot in Spot.objects.all().order_by('spot_number'):
        if spot.is_disabled:
            status = "disabled"
        else:
            reserved_on_date = Reservation.objects.filter(
                spot=spot,
                start_time__date=selected_date
            ).exists()

            if selected_date == today:
                if spot.status == "occupied":
                    status = "occupied"
                elif reserved_on_date:
                    status = "reserved"
                else:
                    status = "available"
            else:
                status = "reserved" if reserved_on_date else "available"

        result.append({
            "spot_number": spot.spot_number,
            "status": status,
            "buzzer_active": spot.buzzer_active,
        })

    return JsonResponse(result, safe=False)


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
        naive_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_of_day = make_aware(datetime.combine(naive_date, datetime.min.time()))
        end_of_day = start_of_day + timedelta(days=1)
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)

    reservations = Reservation.objects.filter(
        spot=spot,
        start_time__gte=start_of_day,
        start_time__lt=end_of_day
    )

    blocked_intervals = []
    for r in reservations:
        start = localtime(r.start_time)
        end = localtime(r.end_time)
        blocked_intervals.append({
            'start': start.strftime("%H:%M"),
            'end': end.strftime("%H:%M")
        })

    return JsonResponse({'blocked_intervals': blocked_intervals})


def admin_home_details_json(request):
    date_str = request.GET.get('date')
    target_date = parse_date(date_str) if date_str else localdate()
    if target_date is None:
        return JsonResponse({'error': 'Invalid date'}, status=400)

    today = localdate()
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
            reservation_qs = Reservation.objects.filter(
                spot=spot,
                start_time__date=target_date
            ).order_by('start_time')

            has_reservation = reservation_qs.exists()

            if target_date == today:
                if spot.status == "occupied":
                    data["status"] = "occupied"
                elif has_reservation:
                    data["status"] = "reserved"
                else:
                    data["status"] = "available"
            else:
                data["status"] = "reserved" if has_reservation else "available"

            if data["status"] == "reserved":
                r = reservation_qs.first()
                if r:
                    data["username"] = r.user.username
                    st = localtime(r.start_time).strftime("%H:%M")
                    et = localtime(r.end_time).strftime("%H:%M")
                    data["time"] = f"{st} - {et}"

        result.append(data)

    return JsonResponse(result, safe=False)


@require_POST
def toggle_spot_disable(request):
    try:
        body = json.loads(request.body.decode())
        spot_nums = body.get("spot_numbers", [])
        disable = bool(body.get("disable", False))

        Spot.objects.filter(spot_number__in=spot_nums).update(is_disabled=disable)

        for slot_number in spot_nums:
            topic = f"parkir/slot{slot_number}/buzzer"
            if disable:
                Spot.objects.filter(spot_number=slot_number).update(status='disabled')
                payload = "disabled"
                print(f"[MQTT] 🚫 Slot {slot_number} dinonaktifkan → kirim 'disabled'")
            else:
                Spot.objects.filter(spot_number=slot_number, status='disabled').update(status='available')
                payload = "enable"
                print(f"[MQTT] ✅ Slot {slot_number} diaktifkan kembali → kirim 'enable'")

            publish.single(
                topic,
                payload,
                hostname="192.168.12.151",
                port=1883
            )

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


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
