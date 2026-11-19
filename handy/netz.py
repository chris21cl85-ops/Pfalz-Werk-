"""Handy im WLAN: Schalter im Datenordner, IP-Adresse des PCs, QR-Code (ohne Zusatzpakete)."""
import socket

from django.conf import settings

PORT = 8000


def an() -> bool:
    return settings.HANDY_SCHALTER.exists()


def schalten(ein: bool):
    if ein:
        settings.HANDY_SCHALTER.write_text("an – PFALZ-WERK ist im Betriebsnetz erreichbar\n", encoding="utf-8")
    elif settings.HANDY_SCHALTER.exists():
        settings.HANDY_SCHALTER.unlink()


def eigene_ip() -> str:
    """IP-Adresse des PCs im lokalen Netz (ohne Verbindung ins Internet: UDP-Trick ohne Senden)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def handy_adresse() -> str:
    return f"http://{eigene_ip()}:{PORT}/handy/"


def bindeadresse() -> str:
    return f"0.0.0.0:{PORT}" if an() else f"127.0.0.1:{PORT}"


def qr_svg(text: str, groesse=220) -> str:
    from reportlab.graphics import renderSVG
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    w = QrCodeWidget(text)
    x1, y1, x2, y2 = w.getBounds()
    d = Drawing(groesse, groesse, transform=[groesse / (x2 - x1), 0, 0, groesse / (y2 - y1), 0, 0])
    d.add(w)
    svg = renderSVG.drawToString(d)
    return svg[svg.find("<svg"):]
