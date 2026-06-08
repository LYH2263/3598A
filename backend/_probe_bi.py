import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'campus_pay.settings')
django.setup()

from django.contrib.auth.models import User
from billing.services.bi_analytics_service import BIAnalyticsService

admin = User.objects.filter(profile__role='admin').first()
stu = User.objects.get(username='student_3598')

print("=== by_category (admin) ===")
print(BIAnalyticsService.by_category({}, admin)['summary'])
print("=== by_time_trend day ===")
print(BIAnalyticsService.by_time_trend({}, admin, 'day')['summary'])
print("=== by_channel ===")
print(BIAnalyticsService.by_channel({}, admin)['summary'])
print("=== top_students ===")
print(len(BIAnalyticsService.top_students({}, admin, 10)['data']), "students")
print("=== by_building_room ===")
print(BIAnalyticsService.by_building_room({}, admin)['summary'])
print("=== by_time_period ===")
print(BIAnalyticsService.by_time_period({}, admin)['summary'])
print("=== compare_periods ===")
fa = {'start_date': None, 'end_date': None}
fb = {'start_date': None, 'end_date': None}
print(BIAnalyticsService.compare_periods(fa, fb, admin, 'day')['growth_rate'])
print("=== student_profile ===")
sp = BIAnalyticsService.student_profile(stu)
print("water%", sp['category_breakdown']['water']['percentage'], "elec%", sp['category_breakdown']['electricity']['percentage'], "peak", sp['peak_period_label'])
print("=== dimension_options ===")
print(BIAnalyticsService.get_dimension_options(admin)['date_range'])
print("ALL OK")
