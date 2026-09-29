import os
from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from ..collectors import base as collecteurs
from ..controllers import metrics as controleur

_JETON = "jeton-de-test-0123456789abcdef"


@tagged("omydoo", "post_install", "-at_install")
class TestMetrics(HttpCase):
    def setUp(self):
        """Repartir d'un cache vide : sinon un test lirait la collecte du précédent."""
        super().setUp()
        controleur._CACHE.update(corps=None, expire_le=0.0)

    def _lire(self, headers=None, jeton=_JETON):
        """Appeler /metrics avec le jeton d'environnement donné (None : variable absente)."""
        environnement = {controleur.VARIABLE_JETON: jeton} if jeton is not None else {}
        with patch.dict(os.environ, environnement, clear=False):
            if jeton is None:
                os.environ.pop(controleur.VARIABLE_JETON, None)
            return self.url_open("/metrics", headers=headers or {})

    def test_sans_jeton_configure_la_route_est_fermee(self):
        """Refuser en 503 tant que le pod n'a pas reçu de jeton."""
        reponse = self._lire({"Authorization": f"Bearer {_JETON}"}, jeton=None)
        self.assertEqual(reponse.status_code, 503)

    def test_sans_jeton_ou_avec_un_mauvais_c_est_401(self):
        """Refuser un appel sans jeton, avec un mauvais, ou avec un jeton non ASCII."""
        self.assertEqual(self._lire().status_code, 401)
        self.assertEqual(self._lire({"Authorization": "Bearer autre-jeton"}).status_code, 401)
        self.assertEqual(self._lire({"X-Prometheus-Token": "jeton-é"}).status_code, 401)
        self.assertEqual(self._lire({"Authorization": _JETON}).status_code, 401)

    def test_le_bon_jeton_rend_les_metriques(self):
        """Rendre les familles attendues au format d'exposition."""
        reponse = self._lire({"Authorization": f"Bearer {_JETON}"})
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.headers["Content-Type"].startswith("text/plain; version=0.0.4"))
        for famille in ("odoo_cron_total", "odoo_cron_active", "omd_exporter_collector_failed"):
            self.assertIn(f"# TYPE {famille} gauge", reponse.text)
        self.assertIn('odoo_cron_total{state="inactive"}', reponse.text)
        self.assertIn('omd_exporter_collector_failed{collector="collect_sessions"} 0', reponse.text)
        if "mail.presence" in self.env:
            for famille in ("odoo_users_connected", "odoo_users_idle", "odoo_users_seen_24h"):
                self.assertIn(f"# TYPE {famille} gauge", reponse.text)
        else:
            self.assertNotIn("odoo_users_connected", reponse.text)

    def test_l_entete_x_prometheus_token_est_admis(self):
        """Accepter le jeton dans l'en-tête dédié."""
        self.assertEqual(self._lire({"X-Prometheus-Token": _JETON}).status_code, 200)

    def test_une_requete_passee_par_l_ingress_est_refusee_meme_avec_le_jeton(self):
        """Répondre 404 à toute requête portant un en-tête de mandataire."""
        for entete in controleur.ENTETES_MANDATAIRE:
            reponse = self._lire({"Authorization": f"Bearer {_JETON}", entete: "203.0.113.7"})
            self.assertEqual(reponse.status_code, 404, entete)

    def test_seul_get_est_admis(self):
        """Refuser toute autre méthode que GET."""
        with patch.dict(os.environ, {controleur.VARIABLE_JETON: _JETON}):
            reponse = self.url_open("/metrics", data={"x": "1"}, headers={"Authorization": f"Bearer {_JETON}"})
        self.assertNotEqual(reponse.status_code, 200)

    def test_un_collecteur_en_echec_est_signale_sans_bloquer_les_autres(self):
        """Signaler le collecteur qui lève et rendre quand même les autres familles."""

        def collecteur_casse(env):
            """Lever à chaque collecte."""
            raise RuntimeError("panne simulée")

        with patch.object(collecteurs, "_REGISTRE", [*collecteurs._REGISTRE, collecteur_casse]):
            reponse = self._lire({"Authorization": f"Bearer {_JETON}"})
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('omd_exporter_collector_failed{collector="collecteur_casse"} 1', reponse.text)
        self.assertIn('omd_exporter_collector_failed{collector="collect_crons"} 0', reponse.text)

    def test_les_valeurs_d_etiquette_sont_echappees(self):
        """Échapper guillemets, barres obliques inverses et sauts de ligne des étiquettes."""
        metrique = collecteurs.Metric(name="m", help="aide\nsur deux lignes", type="gauge")
        metrique.add(1, cron_name='a"b\\c\nd')
        rendu = metrique.render()
        self.assertIn('m{cron_name="a\\"b\\\\c\\nd"} 1', rendu)
        self.assertIn("# HELP m aide\\nsur deux lignes", rendu)
