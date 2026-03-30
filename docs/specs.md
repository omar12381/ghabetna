# GHABETNA — CAHIER DES CHARGES SUMMARY
> Projet de Fin d'Études | Étudiant : Omar Hellel | Entreprise : Smart For Green
> Année universitaire : 2025-2026 | Date CDC : 17 février 2026

---

## 1. CONTEXTE & PROBLÉMATIQUE

**Domaine :** Surveillance forestière et sécuritaire en Tunisie
**Périmètre :** 1,3 million d'hectares de forêts tunisiennes

**Menaces couvertes :**
- Environnementales : incendies, coupes illégales, dépôts de déchets, maladies végétales
- Sécuritaires : refuges terroristes, trafic d'antiquités, contrebande d'armes, activités illicites

**Système actuel (à remplacer) :**
- Patrouilles manuelles sans coordination centralisée
- Communications radio/téléphoniques non structurées
- Rapports papier ou Excel/Word
- Aucune analyse statistique des incidents
- Aucun système de scoring ou évaluation des agents
- Pas de gestion centralisée de l'affectation des agents

---

## 2. OBJECTIFS

**Objectif principal :** Plateforme web + mobile intelligente pour moderniser la surveillance et le signalement des incidents forestiers/sécuritaires via IA, notifications automatiques et workflows structurés.

**Objectifs spécifiques :**
- Application mobile intuitive agents : signalement rapide incidents variés
- Système de notification urgence (WhatsApp/Telegram) vers Protection Civile
- Analyse statistique avancée IA : tendances et patterns (par forêt, zone, type)
- Algorithme scoring fiabilité agents forestiers
- Dashboard web supervision : gestion incidents, agents, statistiques
- Génération rapports analytiques automatiques
- Gestion affectation agents aux zones forestières

---

## 3. ACTEURS DU SYSTÈME

| Acteur | Rôle | Accès |
|---|---|---|
| Agent forestier | Terrain : surveillance et signalement | App mobile Flutter |
| Superviseur | Gestion opérationnelle incidents + équipes | Dashboard web Flutter |
| Administrateur | Configuration système + gestion comptes | Dashboard web Flutter (panel admin) |
| Protection Civile | Réception alertes urgences critiques | Telegram/WhatsApp (passif) |

### Besoins Agent forestier
- S'authentifier sur l'app mobile
- Signaler incidents avec photo + géolocalisation GPS
- Catégoriser incidents (feu, coupe, refuge suspect, trafic, etc.)
- Ajouter notes/commentaires
- Voir son score de fiabilité en temps réel
- Consulter historique de ses signalements
- Consulter sa zone d'affectation
- Recevoir notifications push

### Besoins Superviseur
- Dashboard supervision avec vue tous incidents temps réel
- Visualiser incidents sur carte
- Valider, commenter ou rejeter incidents
- Affecter agents aux zones forestières
- Consulter scores de tous ses agents
- Visualiser statistiques avancées (par forêt, zone, temps, type)
- Générer rapports d'analyse
- Identifier zones à risque
- Gérer priorités d'intervention

### Besoins Administrateur
- Créer et gérer tous les comptes utilisateurs
- Valider comptes nouveaux agents
- Activer/désactiver comptes
- Gérer rôles et permissions
- Configurer paramètres système + seuils d'alerte
- Accéder logs système et d'audit
- Gérer zones forestières (création, modification)

### Besoins Protection Civile
- Recevoir alertes automatiques Telegram/WhatsApp pour incidents critiques
- Accéder détails complets (photo, GPS, description, priorité)
- Consulter localisation exacte sur carte

---

## 4. BESOINS NON FONCTIONNELS

| Catégorie | Exigences clés |
|---|---|
| Performance | Réponse < 2s. Notification urgence < 10s. Stats < 5s. 100+ agents simultanés |
| Sécurité | JWT access+refresh. RBAC strict. Anti-injection SQL/XSS. Rate limiting. Logs audit |
| Disponibilité | 99%. Retry automatique. Redondance notifications critiques |
| Scalabilité | Architecture modulaire microservices. Redis cache+queues. Celery async |
| Compatibilité | Android 8.0+ / iOS 12+. Chrome/Firefox/Safari/Edge. Responsive tablettes |
| Maintenabilité | PEP8 + conventions Dart. Tests > 70% couverture. Swagger/OpenAPI. Doc FR |
| Utilisabilité | Interface intuitive. Messages erreur français. Mode sombre/clair. Apprentissage < 30min |

---

## 5. STACK TECHNOLOGIQUE IMPOSÉE

| Composant | Technologie |
|---|---|
| Mobile + Web | Flutter (Dart) |
| Backend | FastAPI (Python) |
| Analyse statistique | Python : Pandas, NumPy, scikit-learn |
| Visualisation | Plotly / Chart.js |
| Notifications urgence | WhatsApp Business API / Telegram Bot API |
| Cache & Queues | Redis |
| Base de données | PostgreSQL + PostGIS |
| Analyse images (Phase 2) | YOLOv11 — priorité BASSE |

---

## 6. ARCHITECTURE SYSTÈME (CDC)

**Pattern :** Microservices modulaire avec API Gateway (point d'entrée unique obligatoire)

**Services définis :**
- API Gateway : entrée unique toutes requêtes
- Service authentification : JWT + sessions multi-rôles
- Service gestion incidents : CRUD + géolocalisation
- Service notification : WhatsApp/Telegram urgences
- Service analyse statistique : calculs + rapports
- Service scoring : scores fiabilité agents
- Service gestion zones : affectation agents aux forêts

---

## 7. SYSTÈME DE SCORING DE FIABILITÉ

```
Score_global = 0.6 × Score_auto + 0.4 × Score_eval

Score_auto = 100 × (Incidents_traités / Total_incidents_signalés)
Score_eval = 100 × (Note_superviseur_1_à_5 / 5)
```

| Score | Catégorie | Badge |
|---|---|---|
| 90–100 | Excellent | Or |
| 75–89 | Très bon | Argent |
| 60–74 | Bon | Bronze |
| 40–59 | Moyen | À améliorer |
| 0–39 | Faible | Formation requise |

**Modes calcul :**
- Score glissant 30j : classement temps réel + gamification
- Score historique cumulé : évaluations annuelles + promotions

**Tech :** Python + Pandas. Recalcul temps réel + batch nocturne. Table `agent_scores` + Redis cache.

---

## 8. ANALYSE STATISTIQUE INTELLIGENTE

### Analyses à implémenter

**Temporelle :** Série temporelle incidents/jour/semaine/mois. Patterns saisonniers. Heures critiques. Prédiction moyennes mobiles. Tech : Pandas, Plotly, Prophet.

**Géographique :** Heatmaps incidents par zone. Clustering zones risque (DBSCAN). Stats comparatives par forêt. Couverture géographique par agent. Tech : PostGIS, GeoPandas, Folium.

**Par type incident :** Distribution % types. Corrélations types/zones/périodes. Tendances par catégorie. Menaces dominantes par zone.

**Performance équipe :** Top 10 agents par score. Vue d'ensemble superviseur. Taux validation incidents. Délais moyens signalement par agent/zone.

### Rapports PDF automatiques
- Fréquence : hebdomadaire + mensuel
- Contenu : résumé exécutif + graphiques tendances + carte zones risque + classement agents + recommandations auto
- Tech : ReportLab + Jinja2

### Endpoints analytics (CDC)
```
GET  /analytics/temporal?period=30d
GET  /analytics/geographic?forest=X
GET  /analytics/incidents-by-type
GET  /analytics/team-performance
POST /analytics/generate-report
```
Cache Redis TTL 5min. Background jobs Celery pour rapports lourds.

---

## 9. PRODUCT BACKLOG COMPLET

### Échelle Story Points
| SP | Complexité |
|---|---|
| 1 | Très simple |
| 2 | Simple |
| 3 | Plusieurs étapes |
| 5 | Moyen, logique métier modérée |
| 8 | Complexe |
| 13 | Très complexe, incertitudes fortes |

### EPIC 1 — Authentification & Gestion Utilisateurs

| ID | Titre | Priorité | SP |
|---|---|---|---|
| US1 | Auth agent mobile (email+password) | Critique | 3 |
| US2 | Auth admin/superviseur web | Critique | 3 |
| US3 | Refresh token automatique | Critique | 2 |
| US4 | Déconnexion | Critique | 1 |
| US5 | Activation compte via lien email | Haute | 3 |
| US6 | Gestion utilisateurs (admin) : créer/modifier/désactiver | Haute | 5 |

### EPIC 2 — Gestion Forêts & Affectations

| ID | Titre | Priorité | SP |
|---|---|---|---|
| US7 | Gestion forêts (admin) : CRUD | Haute | 5 |
| US8 | Affectation superviseur → forêt (admin) | Haute | 2 |
| US9 | Affectation agents → forêts (superviseur) | Haute | 3 |

### EPIC 3 — Signalement Incidents (Mobile)

| ID | Titre | Priorité | SP |
|---|---|---|---|
| US10 | Signalement incident + photo + GPS auto | Critique | 8 |
| US11 | Catégorisation incidents | Critique | 3 |
| US12 | Profil agent + historique + score | Moyenne | 5 |

### EPIC 4 — Gestion Incidents (Superviseur)

| ID | Titre | Priorité | SP |
|---|---|---|---|
| US13 | Dashboard superviseur : incidents temps réel sur carte | Haute | 8 |
| US14 | Mise à jour statut incidents (en_cours / traité) | Critique | 5 |
| US15 | Détails incident + commentaires superviseur | Moyenne | 3 |

### EPIC 5 — Notifications d'Urgence

| ID | Titre | Priorité | SP |
|---|---|---|---|
| US16 | Notification Telegram/WhatsApp Protection Civile incidents critiques | Critique | 13 |
| US17 | Configuration seuils et alertes (admin) | Moyenne | 5 |
| US18 | Notifications push mobile agent | Basse | 5 |

### EPIC 6 — Système de Scoring

| ID | Titre | Priorité | SP |
|---|---|---|---|
| US19 | Attribution note étoiles superviseur → agent | Haute | 13 |
| US20 | Affichage score agent temps réel + détails composantes | Moyenne | 3 |
| US21 | Classement agents par score (superviseur) | Haute | 5 |

### EPIC 7 — Analyse Statistique & Visualisation

| ID | Titre | Priorité | SP |
|---|---|---|---|
| US22 | Analyse temporelle incidents (jour/semaine/mois) | Haute | 8 |
| US23 | Analyse géographique : carte + heatmaps | Haute | 13 |
| US24 | Statistiques par type incident | Haute | 5 |
| US25 | Statistiques comparatives par forêt | Haute | 5 |
| US26 | Génération rapports PDF automatiques | Moyenne | 8 |
| US27 | Dashboard analytics KPIs temps réel | Haute | 8 |

### EPIC 8 — Fonctionnalités Avancées

| ID | Titre | Priorité | SP |
|---|---|---|---|
| US28 | Recherche et filtres avancés multicritères | Moyenne | 5 |
| US29 | Export données CSV/Excel | Basse | 3 |

### EPIC 9 — IA Images (Phase 2 — Priorité BASSE)

| ID | Titre | Priorité | SP |
|---|---|---|---|
| US30 | Analyse auto image YOLO (détection type incident) | Basse | 13 |
| US31 | Génération rapport textuel via Ollama | Basse | 13 |

**TOTAL SP Critique+Haute+Moyenne : 163 SP**
**TOTAL avec Phase 2 : 189 SP**

---

## 10. PLANIFICATION SPRINTS (CDC)

| Sprint | Période | US couvertes | SP | Charge |
|---|---|---|---|---|
| Sprint 0 | 1–14 fév | — | — | Setup + Design + CI/CD |
| Sprint 1 | 15 fév–7 mars | US1–7 | 22 SP | Normale |
| Sprint 2 | 8–28 mars | US8–10 | 16 SP | Normale |
| Sprint 3 | 29 mars–18 avril | US11–17 | 47 SP | **Très Haute** |
| Sprint 4 | 19 avril–9 mai | US18–20 | 21 SP | Normale |
| Sprint 5 | 10–23 mai | US21–28 | 57 SP | **Très Haute** |
| Sprint 6 | 24–31 mai | US29 + QA | 3 SP | Normale |
| Phase 2 | Post-soutenance | US30–31 | 26 SP | Haute |

**Total MVP : 163 SP | Durée : 18 semaines | 1 fév → 31 mai 2026**

---

## 11. CONTRAINTES

**Délai :** 4 mois. Analyse images IA (YOLO) = priorité BASSE. Focus MVP : analyse statistique + scoring + notifications + visualisations.

**Techniques imposées :** Stack définie section 5. Architecture microservices. API Gateway obligatoire.

---

## 12. INNOVATIONS CLÉS (ARGUMENTS SOUTENANCE)

1. Extension surveillance au-delà environnemental → menaces sécuritaires (terrorisme, contrebande)
2. Notifications urgence automatiques WhatsApp/Telegram Protection Civile < 10s
3. Scoring composite objectif agents (Score_auto 60% + Score_eval 40%)
4. Analyse statistique intelligente : patterns temporels + géographiques DBSCAN + thématiques
5. Séparation claire rôles : Admin système vs Superviseur opérationnel
6. Visualisations interactives : heatmaps, graphiques temporels, dashboards décisionnels
7. Gamification : badges or/argent/bronze, classements, incentive terrain
8. Rapports PDF automatiques hebdomadaires/mensuels avec recommandations IA

---

## 13. MAPPING CDC → IMPLÉMENTATION RÉELLE

| CDC | Implémentation retenue |
|---|---|
| WhatsApp Business API | → Telegram Bot API (gratuit, 5min setup, même fonctionnalité) |
| Celery pour tâches async | → FastAPI BackgroundTasks (suffisant pour MVP, zéro config) |
| DB unique mentionnée implicitement | → DB séparée par microservice (vraie architecture microservices) |
| Affectation agent → forêt | → Affectation agent → parcelle (plus précis, rattachement GPS ST_Contains) |
| Scoring 4 composantes (précision, réactivité, couverture, contribution) | → Simplifié : Score_auto (60%) + Score_eval (40%) selon formule CDC section 4 |
| Prophet pour prédiction | → Phase 2 si temps, pandas resample suffit pour MVP |
