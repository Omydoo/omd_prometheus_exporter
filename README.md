# omd_prometheus_exporter

Module Odoo qui expose des métriques Prometheus au collecteur de la plateforme OmydooSH.

## Métriques

| Famille | Contenu |
|---|---|
| `odoo_users_connected`, `odoo_users_idle`, `odoo_users_seen_24h` | présence des utilisateurs (si `mail` est installé) |
| `odoo_cron_total`, `odoo_cron_active`, `odoo_cron_last_call_timestamp`, `odoo_cron_next_call_delta_seconds` | tâches planifiées |
| `odoo_website_visitors_active` | visiteurs récents du site (si `website` est installé) |
| `omd_exporter_collector_failed` | collecteur en échec lors de la dernière collecte |

## Accès

`GET /metrics`, réservé au collecteur :

- jeton lu dans la variable d'environnement `OMD_METRICS_TOKEN` du pod (Secret Kubernetes posé par la
  plateforme), jamais en base ; sans elle la route répond 503 ;
- jeton présenté en `Authorization: Bearer …` ou `X-Prometheus-Token`, comparé à temps constant ;
- toute requête portant un en-tête de mandataire (`X-Forwarded-*`, `X-Real-Ip`, `Forwarded`) reçoit
  404 : une requête passée par l'ingress n'est jamais servie ;
- la plateforme bloque aussi `/metrics` à l'ingress et n'ouvre le port d'Odoo qu'au namespace du
  collecteur.

Réglages (`ir.config_parameter`) : `omd_prometheus_exporter.cache_ttl_seconds` (30),
`omd_prometheus_exporter.idle_threshold_seconds` (900),
`omd_prometheus_exporter.website_visitor_window_seconds` (300).

## Branches et tests

Une branche par série Odoo, de `14.0` à `20.0`, au même code ; seule la version du manifest
change. La plateforme attache le module aux instances d'une série seulement si la branche existe.
Le code reste compatible avec Python 3.7 (image Odoo 14) et lit ses réglages par `get_int`
quand `get_param` n'existe plus (Odoo 20).

```bash
./tester_image.sh 19.0                           # base seule ; toute série de 14.0 à 20.0
MODULES_EN_PLUS=mail,website ./tester_image.sh 19.0
```
