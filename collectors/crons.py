from odoo import fields

from .base import Metric, register


@register
def collect_crons(env):
    """Exposer l'état des tâches planifiées : actives, dernier appel, retard sur le prochain."""
    taches = env["ir.cron"].sudo().with_context(active_test=False).search([])
    maintenant = fields.Datetime.now()

    m_total = Metric(name="odoo_cron_total", help="Nombre de tâches planifiées par état.", type="gauge")
    m_active = Metric(name="odoo_cron_active", help="Tâche planifiée active (1) ou désactivée (0).", type="gauge")
    m_dernier = Metric(
        name="odoo_cron_last_call_timestamp",
        help="Horodatage Unix du dernier appel connu (0 si jamais exécutée).",
        type="gauge",
    )
    m_retard = Metric(
        name="odoo_cron_next_call_delta_seconds",
        help="Secondes jusqu'au prochain appel (négatif : en retard).",
        type="gauge",
    )
    actives = 0
    for tache in taches:
        etiquettes = {"cron_name": tache.cron_name or tache.name or f"id_{tache.id}", "cron_id": str(tache.id)}
        m_active.add(1 if tache.active else 0, **etiquettes)
        actives += 1 if tache.active else 0
        m_dernier.add(tache.lastcall.timestamp() if tache.lastcall else 0, **etiquettes)
        if tache.active and tache.nextcall:
            m_retard.add((tache.nextcall - maintenant).total_seconds(), **etiquettes)
    m_total.add(actives, state="active")
    m_total.add(len(taches) - actives, state="inactive")
    return [m_total, m_active, m_dernier, m_retard]
