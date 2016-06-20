from django.conf.urls import url, include
from django.contrib import admin


urlpatterns = [
    url(r'^', include('dashboard.urls', namespace='dashboard')),
    url(r'^admin/', admin.site.urls),

]

handler404 = 'dashboard.views.custom_404'
handler500 = 'dashboard.views.custom_500'
handler400 = 'dashboard.views.custom_400'
