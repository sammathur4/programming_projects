import os

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path
from django.views.static import serve as static_serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    # Vision board: the standalone HTML board is copied into server/vision_board
    # and served here so phones/web builds can open it (file:// is blocked there).
    re_path(
        r"^vision-board/(?P<path>.*)$",
        static_serve,
        {"document_root": settings.VISION_BOARD_DIR},
        name="vision-board",
    ),

    # Server-rendered WhatsApp check-in page (check-in board):
    # /checkin/ → index.html, /checkin/<asset> for anything else in the dir.
    re_path(
        r"^checkin/$",
        static_serve,
        {"document_root": settings.CHECKIN_BOARD_DIR, "path": "index.html"},
        name="checkin",
    ),
    re_path(
        r"^checkin/(?P<path>.*)$",
        static_serve,
        {"document_root": settings.CHECKIN_BOARD_DIR},
        name="checkin-asset",
    ),
]

# ---------------------------------------------------------------------------
# Flutter web app: served as the site root so the app and the API share an
# origin. The SPA fallback returns index.html for any unknown path (needed for
# deep links). Only enabled when the build directory actually exists.
# ---------------------------------------------------------------------------
WEB_DIR = getattr(settings, "FLUTTER_WEB_DIR", "")
INDEX = os.path.join(WEB_DIR, "index.html")

if WEB_DIR and os.path.isfile(INDEX):

    def spa(request, path=""):
        """Serve a real file if it exists, otherwise the app shell."""
        target = os.path.normpath(os.path.join(WEB_DIR, path))
        # never let a crafted path escape the build directory
        if not target.startswith(os.path.abspath(WEB_DIR)):
            raise Http404("bad path")
        if path and os.path.isfile(target):
            return static_serve(request, path, document_root=WEB_DIR)
        return FileResponse(open(INDEX, "rb"), content_type="text/html")

    urlpatterns += [
        re_path(r"^ui_mockup/(?P<path>.*)$", static_serve,
                {"document_root": os.path.join(WEB_DIR, "ui_mockup")}),
        re_path(r"^(?P<path>.*)$", spa, name="flutter-web"),
    ]
