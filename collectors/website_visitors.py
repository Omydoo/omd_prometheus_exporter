from datetime import timedelta

from odoo import fields

from .base import Metric, register


@register
def collect_website_visitors(env):
    """Compter les visiteurs récents du site public, s'il est installé."""
    if "website.visitor" not in env:
        return []
    fenetre = int(
        env["ir.config_parameter"].sudo().get_param("omd_prometheus_exporter.website_visitor_window_seconds", "300")
    )
    depuis = fields.Datetime.now() - timedelta(seconds=fenetre)
    visiteurs = env["website.visitor"].sudo()

    tous = visiteurs.search_count([("last_connection_datetime", ">=", depuis)])
    identifies = visiteurs.search_count([("last_connection_datetime", ">=", depuis), ("partner_id", "!=", False)])

    m_actifs = Metric(
        name="odoo_website_visitors_active", help="Visiteurs du site public actifs dans la fenêtre récente.", type="gauge"
    )
    m_actifs.add(tous, kind="all")
    m_actifs.add(identifies, kind="signed")
    m_actifs.add(tous - identifies, kind="anonymous")
    return [m_actifs]
