from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.frontend import views as frontend_views

urlpatterns = [
    path('admin/login/', frontend_views.admin_login_view, name='admin_login'),
    path('admin/logout/', frontend_views.admin_logout_view, name='admin_logout'),
    re_path(r'^admin/?$', frontend_views.admin_gateway, name='admin_gateway'),
    path('django-admin/', admin.site.urls),
    path('api/v1/', include('apps.api.urls')),
    path('', include('apps.frontend.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
