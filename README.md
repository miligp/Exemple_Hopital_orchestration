# 🏥 Orchestration des Urgences - Agent RAG & Simulation

Ce projet est une plateforme de gestion des urgences hospitalières utilisant un **Agent intelligent** couplé à un système **RAG** (Retrieval-Augmented Generation). Il orchestre en temps réel le flux de patients, la surveillance des salles et les transferts vers les unités spécialisées en fonction des ressources disponibles.

## 🛠️ Configuration de l'environnement (`.env`)

L'application utilise l'API **Mistral AI** pour permettre au chatbot et à l'agent de prendre des décisions complexes basées sur les règles médicales chargées via le système RAG.

### 1. Créez un fichier nommé **`.env`** à la racine de votre projet.
### 2. Ajoutez-y votre clé API Mistral :
   ```env
   MISTRAL_API_KEY=votre_cle_api_ici
   ```
Note : Si cette clé est absente, l'application basculera automatiquement en mode DEMO (recherche par mots-clés simple).

##  🚀 Lancement de l'application
L'interface est propulsée par Streamlit. Pour garantir que tous les modules communiquent correctement, suivez ces étapes :

### 1. Installation des dépendances
Installez les bibliothèques critiques répertoriées dans le fichier requirements.txt :

```Bash
pip install -r requirements.txt
```

### 2. Démarrage de la Simulation
Lancez l'interface de simulation temps réel avec la commande suivante :

```Bash
streamlit run app_simulation.py
```

---
### 📂 Structure des Modules
- rag_systeme.py : Moteur RAG qui charge les règles JSON et gère l'historique des logs d'événements.

- agent.py : Cerveau du système gérant l'état du personnel, les décisions de tri et le cycle d'orchestration.

- chatbot.py : Interface conversationnelle pour interroger les règles hospitalières via le RAG.

- mcp_tools.py : Génère des scénarios de crise (afflux massif, saturation) pour tester le système.

- app_simulation.py : Interface Streamlit orchestrant la simulation visuelle et les interactions.
--- 
