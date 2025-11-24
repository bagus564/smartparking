from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import *
from .views import export_reservations, toggle_all_spots_disable, spots_state, delete_announcement

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
    path('realtime-data/', realtime_data, name='realtime_data'),

    # --- API ---
    path("api/spots-dynamic-status/", spots_dynamic_status_json, name="spots_dynamic_status_json"),
    path("api/reserved-intervals/", reserved_intervals_view, name="reserved_intervals"),
    path("api/admin-home-details/", admin_home_details_json, name="admin_home_details_json"),
    path("api/toggle-spot-disable/", toggle_spot_disable, name="toggle_spot_disable"),
    path("api/admin-turn-off-buzzer/", admin_turn_off_buzzer, name="admin_turn_off_buzzer"),
    path("api/user-turn-off-buzzer/", user_turn_off_buzzer, name="user_turn_off_buzzer"),
    path('api/admin-set-spot-status/', admin_set_spot_status_api, name='admin_set_spot_status'),
    path('api/realtime/admin/data/', realtime_data_admin_api, name='realtime_data_admin'),
    path('api/add-announcement/', add_announcement, name='add_announcement'),
    path('api/get-announcement/', get_announcements_list, name='get_announcements_list'),
    path('api/announcements/', get_active_announcements, name='get_active_announcements'),
    path('api/announcement/delete/<int:pk>/', delete_announcement, name='delete_announcement'),


    # --- ADMIN PAGES ---
    path("adminlogin/", adminlogin_view, name="adminlogin"),
    path("adminlogout/", adminlogout_view, name="adminlogout"),
    path("adminhome/", adminhome_view, name="adminhome"),
    path("adminreservation/", adminreservation_view, name="adminreservation"),
    path("adminmonitoring/", adminmonitoring_view, name="adminmonitoring"),
    path('adminrealtime/', adminrealtime_view, name='adminrealtime'),
    

    # --- ADMIN ACTIONS (baru ditambahkan) ---
    path("adminreservation/export/", export_reservations, name="export_reservations"),
    path("adminreservation/toggle-all-spots/", toggle_all_spots_disable, name="toggle_all_spots_disable"),
    path("adminreservation/spots-state/", spots_state, name="spots_state"),
    path('admin/mass-cancel-reservations/', mass_delete_reservations, name='mass_delete_reservations'),
    path('admin/all-reservations/', adminallreservations_view, name='adminallreservations'),
]

# Serve media during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
