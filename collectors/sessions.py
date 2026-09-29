from datetime import timedelta

from odoo import fields

from .base import Metric, lire_entier, register

# `bus.presence` (jusqu'en Odoo 17) est devenu `mail.presence` en Odoo 18.
_MODELES_PRESENCE = ("mail.presence", "bus.presence")


@register
def collect_sessions(env):
    """Compter les utilisateurs connectés, inactifs et vus dans les dernières 24 h."""
    seuil_inactivite = lire_entier(env, "omd_prometheus_exporter.idle_threshold_seconds", 900)
    presence = next((env[nom].sudo() for nom in _MODELES_PRESENCE if nom in env), None)
    if presence is None:
        return []
    maintenant = fields.Datetime.now()

    connectes = presence.search_count([("status", "=", "online")])
    absents = presence.search_count([("status", "=", "away")])
    inactifs_par_appel = presence.search_count(
        [
            ("status", "=", "online"),
            ("last_poll", "<", maintenant - timedelta(minutes=1)),
            ("last_poll", ">=", maintenant - timedelta(seconds=seuil_inactivite)),
        ]
    )
    vus_24h = presence.search_count([("last_poll", ">=", maintenant - timedelta(days=1))])

    m_connectes = Metric(name="odoo_users_connected", help="Utilisateurs connectés (présence online).", type="gauge")
    m_connectes.add(connectes)
    m_inactifs = Metric(
        name="odoo_users_idle",
        help="Utilisateurs présents mais inactifs (away, ou dernier appel ancien dans la fenêtre).",
        type="gauge",
    )
    m_inactifs.add(absents + inactifs_par_appel)
    m_vus = Metric(name="odoo_users_seen_24h", help="Utilisateurs vus au moins une fois en 24 h.", type="gauge")
    m_vus.add(vus_24h)
    return [m_connectes, m_inactifs, m_vus]
