from django.urls import path

from housing.views import (
    AssignBedAPIView,
    BedChangeLogListAPIView,
    BedDetailAPIView,
    BedListCreateAPIView,
    BuildingDetailAPIView,
    BuildingListCreateAPIView,
    CampusDetailAPIView,
    CampusListCreateAPIView,
    CheckOutAPIView,
    DashboardTopBuildingsAPIView,
    EnergyBuildingRankingAPIView,
    EnergyMonthlyTrendAPIView,
    EnergyRoomRankingAPIView,
    FloorDetailAPIView,
    FloorListCreateAPIView,
    HousingTreeAPIView,
    MyStayCurrentAPIView,
    MyStayHistoryAPIView,
    RoomDetailAPIView,
    RoomListCreateAPIView,
    RoomMigrateAPIView,
    StayRecordListAPIView,
)

urlpatterns = [
    path('tree/', HousingTreeAPIView.as_view(), name='housing-tree'),

    path('campus/', CampusListCreateAPIView.as_view(), name='campus-list'),
    path('campus/<int:pk>/', CampusDetailAPIView.as_view(), name='campus-detail'),

    path('buildings/', BuildingListCreateAPIView.as_view(), name='building-list'),
    path('buildings/<int:pk>/', BuildingDetailAPIView.as_view(), name='building-detail'),

    path('floors/', FloorListCreateAPIView.as_view(), name='floor-list'),
    path('floors/<int:pk>/', FloorDetailAPIView.as_view(), name='floor-detail'),

    path('rooms/', RoomListCreateAPIView.as_view(), name='room-list'),
    path('rooms/<int:pk>/', RoomDetailAPIView.as_view(), name='room-detail'),
    path('rooms/migrate/', RoomMigrateAPIView.as_view(), name='room-migrate'),

    path('beds/', BedListCreateAPIView.as_view(), name='bed-list'),
    path('beds/<int:pk>/', BedDetailAPIView.as_view(), name='bed-detail'),

    path('stays/assign/', AssignBedAPIView.as_view(), name='stay-assign'),
    path('stays/checkout/', CheckOutAPIView.as_view(), name='stay-checkout'),
    path('stays/my/current/', MyStayCurrentAPIView.as_view(), name='my-stay-current'),
    path('stays/my/history/', MyStayHistoryAPIView.as_view(), name='my-stay-history'),
    path('stays/', StayRecordListAPIView.as_view(), name='stay-list'),
    path('stays/change-logs/', BedChangeLogListAPIView.as_view(), name='bed-change-logs'),

    path('energy/room-ranking/', EnergyRoomRankingAPIView.as_view(), name='energy-room-ranking'),
    path('energy/building-ranking/', EnergyBuildingRankingAPIView.as_view(), name='energy-building-ranking'),
    path('energy/monthly-trend/', EnergyMonthlyTrendAPIView.as_view(), name='energy-monthly-trend'),
    path('energy/top-buildings/', DashboardTopBuildingsAPIView.as_view(), name='energy-top-buildings'),
]
