from pathlib import Path
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.static import serve as static_serve

_FRONTEND_DIST = Path(settings.BASE_DIR).parent / 'frontend' / 'dist'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve o frontend React buildado (gerado por ./start.sh build).
# Quando o build existe, https://borderomni.ngrok.app abre o app completo.
if _FRONTEND_DIST.exists():
    urlpatterns += [
        # Arquivos estáticos do build (JS, CSS, imagens)
        re_path(r'^assets/(?P<path>.*)$', static_serve,
                {'document_root': str(_FRONTEND_DIST / 'assets')}),
        # Qualquer outra rota não-API entrega o index.html (React Router)
        re_path(r'^(?!api/|admin/|media/|static/).*$',
                TemplateView.as_view(template_name='index.html')),
    ]
