# 0001 — Uniquement des API officielles, authentifiées par clé

Date : 2026-11-18. Statut : accepté.

## Contexte

Beaucoup de fournisseurs d'IA affichent la consommation dans leur console web sans l'exposer par
une API. Il est techniquement possible de relire ces consoles avec un cookie ou un jeton de
session. Ces canaux ne sont pas documentés : ils changent sans préavis, les jetons expirent au
bout de quelques heures ou de quelques jours, et leur usage peut contrevenir aux conditions
d'utilisation et exposer le compte.

## Décision

L'outil n'interroge que des points d'accès officiels et documentés, authentifiés par une clé
d'API que l'utilisateur fournit par variable d'environnement. Un fournisseur sans API de
consommation n'est pas pris en charge. Seule exception, locale : le volume de jetons Claude Code,
lu dans les fichiers de transcription que l'outil écrit sur la machine de l'utilisateur.

## Conséquences

- La liste des fournisseurs est plus courte, mais chaque sonde est stable et vérifiable.
- Aucun secret de session n'est manipulé ; une clé absente désactive simplement la sonde.
- Ajouter un fournisseur suppose de citer son endpoint officiel (voir `AGENTS.md`).
