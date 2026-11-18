# 0002 — Pas de pourcentage sans plafond connu

Date : 2026-11-18. Statut : accepté.

## Contexte

Une barre de progression se lit en une seconde, d'où la tentation d'en mettre partout. Mais
plusieurs mesures n'ont pas de plafond publié : un solde prépayé (Deepgram), des heures
transcrites (Gladia), des minutes de réunion sans limite déclarée (Fireflies), un volume de jetons
(Claude Code). Y afficher un pourcentage oblige à inventer un dénominateur ; la barre paraît
précise et elle est fausse.

## Décision

Un pourcentage n'est calculé que si le fournisseur publie le plafond dans sa réponse, ou si
l'utilisateur le déclare explicitement (`FIREFLIES_MONTHLY_MINUTES`). Sinon la mesure est un
solde (montant restant) ou un volume (compte brut), et la page l'affiche comme tel. La prévision
ne s'applique qu'aux quotas (vers 100 %) et aux soldes (vers zéro).

## Conséquences

- Chaque mesure porte un genre explicite : `quota`, `balance`, `volume` ou `rate`.
- Un solde reçoit une date d'épuisement prévue, pas une jauge.
- Un volume n'a ni jauge ni prévision ; la carte le dit en clair.
