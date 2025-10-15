from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import *
from .views import export_reservations, toggle_all_spots_disable, spots_state

urlpatterns = [
    # --- AUTH ---
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),

    # --- USER PAGES ---
    path("", home_view, name="home"),
    path("home/", home_view, name="home"),
    path("reservation/", reservation_view, name="reservation"),
    path("reservation/<int:reservation_id>/delete/", delete_reservation, name="delete_reservation"),
    path("account/", account_view, name="account"),
    path("update-account/", update_account_view, name="update_account"),
    path("history/", history_view, name="history"),
    path("guide/", guide_view, name="guide"),
    path("contact/", contact_view, name="contact"),
    path("status/", status_view, name="status"),
    path("realtimeparking/", realtime_parking_view, name="realtime_parking"),

    # --- API ---
    path("api/spots-dynamic-status/", spots_dynamic_status_json, name="spots_dynamic_status_json"),
    path("api/reserved-intervals/", reserved_intervals_view, name="reserved_intervals"),
    path("api/admin-home-details/", admin_home_details_json, name="admin_home_details_json"),
    path("api/toggle-spot-disable/", toggle_spot_disable, name="toggle_spot_disable"),
    path("api/admin-turn-off-buzzer/", admin_turn_off_buzzer, name="admin_turn_off_buzzer"),

    # --- ADMIN PAGES ---
    path("adminlogin/", adminlogin_view, name="adminlogin"),
    path("adminlogout/", adminlogout_view, name="adminlogout"),
    path("adminhome/", adminhome_view, name="adminhome"),
    path("adminreservation/", adminreservation_view, name="adminreservation"),
    path("adminmonitoring/", adminmonitoring_view, name="adminmonitoring"),

    # --- ADMIN ACTIONS (baru ditambahkan) ---
    path("adminreservation/export/", export_reservations, name="export_reservations"),
    path("adminreservation/toggle-all-spots/", toggle_all_spots_disable, name="toggle_all_spots_disable"),
    path("adminreservation/spots-state/", spots_state, name="spots_state"),
]

# Serve media during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
