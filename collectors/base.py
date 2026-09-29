import logging
from dataclasses import dataclass, field

_logger = logging.getLogger(__name__)

_REGISTRE = []


@dataclass
class Metric:
    """Une famille de métriques Prometheus : nom, aide, type et échantillons."""

    name: str
    help: str
    type: str
    samples: list = field(default_factory=list)

    def add(self, value, **labels):
        """Ajouter un échantillon avec ses étiquettes."""
        self.samples.append((labels, float(value)))

    def render(self):
        """Rendre la famille au format d'exposition texte de Prometheus."""
        lignes = [f"# HELP {self.name} {_echapper_aide(self.help)}", f"# TYPE {self.name} {self.type}"]
        for labels, value in self.samples:
            if labels:
                etiquettes = ",".join(f'{k}="{_echapper(str(v))}"' for k, v in labels.items())
                lignes.append(f"{self.name}{{{etiquettes}}} {_formater(value)}")
            else:
                lignes.append(f"{self.name} {_formater(value)}")
        return "\n".join(lignes)


def _echapper(texte):
    """Échapper une valeur d'étiquette (barre oblique inverse, guillemet, saut de ligne)."""
    return texte.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _echapper_aide(texte):
    """Échapper un texte d'aide (barre oblique inverse et saut de ligne)."""
    return texte.replace("\\", "\\\\").replace("\n", "\\n")


def _formater(valeur):
    """Rendre une valeur sans décimales inutiles."""
    if valeur == int(valeur):
        return str(int(valeur))
    return f"{valeur:.6f}".rstrip("0").rstrip(".")


def lire_entier(env, cle, defaut):
    """Lire un réglage entier de `ir.config_parameter`, quelle que soit la série d'Odoo."""
    parametres = env["ir.config_parameter"].sudo()
    # Odoo 20 a remplacé `get_param` par des lecteurs typés.
    if hasattr(parametres, "get_int"):
        return parametres.get_int(cle, defaut)
    return int(parametres.get_param(cle, str(defaut)))


def register(fn):
    """Enregistrer une fonction de collecte `fn(env) -> list[Metric]`."""
    _REGISTRE.append(fn)
    return fn


def collect_all(env):
    """Exécuter tous les collecteurs ; un collecteur qui échoue est signalé, les autres continuent."""
    metriques = []
    en_echec = Metric(
        name="omd_exporter_collector_failed",
        help="Collecteur en échec lors de la dernière collecte (1 = échec).",
        type="gauge",
    )
    for fn in _REGISTRE:
        try:
            metriques.extend(fn(env) or [])
            en_echec.add(0, collector=fn.__name__)
        except Exception as exc:
            _logger.warning("Collecteur %s en échec (%s)", fn.__name__, type(exc).__name__)
            en_echec.add(1, collector=fn.__name__)
    metriques.append(en_echec)
    return metriques


def render_all(metriques):
    """Rendre toutes les familles, terminées par un saut de ligne."""
    return "\n".join(m.render() for m in metriques) + "\n"
