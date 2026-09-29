import hmac
import logging
import os
import time

from odoo import http
from odoo.http import Response, request

from ..collectors import base as collecteurs

_logger = logging.getLogger(__name__)

TYPE_CONTENU = "text/plain; version=0.0.4; charset=utf-8"
# Le jeton vient de l'environnement du pod (Secret Kubernetes), jamais de la base : un
# administrateur de l'instance ne le lit pas, et il ne voyage pas avec une copie ou une sauvegarde.
VARIABLE_JETON = "OMD_METRICS_TOKEN"
# Traefik pose ces en-têtes sur toute requête venue d'Internet ; le collecteur, lui, joint le pod en
# direct. Leur présence suffit à refuser, même si le blocage de /metrics manquait à l'ingress.
ENTETES_MANDATAIRE = ("X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto", "X-Real-Ip", "Forwarded")

_CACHE = {"corps": None, "expire_le": 0.0}


class ExporteurPrometheus(http.Controller):
    @http.route("/metrics", type="http", auth="public", methods=["GET"], csrf=False, save_session=False)
    def metrics(self, **kwargs):
        """Rendre les métriques au collecteur authentifié, au format d'exposition Prometheus."""
        entetes = request.httprequest.headers
        if any(nom in entetes for nom in ENTETES_MANDATAIRE):
            return Response("not found\n", status=404, content_type="text/plain")

        attendu = os.environ.get(VARIABLE_JETON, "")
        if not attendu:
            _logger.warning("omd_prometheus_exporter : %s absent, /metrics désactivé", VARIABLE_JETON)
            return Response("token non configuré\n", status=503, content_type="text/plain")
        if not _jeton_valide(_jeton_fourni(entetes), attendu):
            return Response("unauthorized\n", status=401, content_type="text/plain")

        maintenant = time.monotonic()
        if _CACHE["corps"] is not None and _CACHE["expire_le"] > maintenant:
            return Response(_CACHE["corps"], status=200, content_type=TYPE_CONTENU)

        parametres = request.env["ir.config_parameter"].sudo()
        ttl = int(parametres.get_param("omd_prometheus_exporter.cache_ttl_seconds", "30"))
        corps = collecteurs.render_all(collecteurs.collect_all(request.env))
        _CACHE["corps"] = corps
        _CACHE["expire_le"] = maintenant + max(ttl, 1)
        return Response(corps, status=200, content_type=TYPE_CONTENU)


def _jeton_fourni(entetes):
    """Rendre le jeton présenté (`Authorization: Bearer` ou `X-Prometheus-Token`), ou une chaîne vide."""
    autorisation = entetes.get("Authorization", "")
    if autorisation.startswith("Bearer "):
        return autorisation.removeprefix("Bearer ").strip()
    return entetes.get("X-Prometheus-Token", "")


def _jeton_valide(fourni, attendu):
    """Comparer à temps constant, en octets : un jeton non ASCII est un refus, pas une erreur 500."""
    if not fourni:
        return False
    return hmac.compare_digest(fourni.encode("utf-8"), attendu.encode("utf-8"))
