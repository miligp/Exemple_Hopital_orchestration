"""
Chatbot: Répond aux questions en utilisant le RAG
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Dict, Any, Optional
import json
import os

# Import RAG
from rag_systeme import RAGSysteme

# Mistral (optionnel)
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

try:
    from mistralai import Mistral
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False


class ChatbotOrchestration:
    """
    Chatbot intelligent pour l'orchestration des urgences
    
    Utilise:
    - RAG pour accéder aux règles
    - Mistral API pour génération IA (optionnel)
    - Mode DEMO avec recherche mots-clés
    """
    
    def __init__(self, rag: Optional[RAGSysteme] = None):
        """
        Initialise le chatbot
        
        Args:
            rag: Instance RAG (partagée avec agent si besoin)
        """
        self.rag = rag if rag else RAGSysteme()
        
        # Client Mistral
        if MISTRAL_AVAILABLE and os.environ.get("MISTRAL_API_KEY"):
            self.client = Mistral(api_key=os.environ.get("MISTRAL_API_KEY"))
            self.mode = "API"
            self.model = "mistral-large-latest"
            print("✅ Chatbot en mode API Mistral")
        else:
            self.client = None
            self.mode = "DEMO"
            print("⚠️ Chatbot en mode DEMO (recherche mots-clés)")
        
        self.historique = []
    
    def repondre(self, question: str, contexte_etat: Optional[Dict] = None) -> str:
        """
        Répond à une question
        
        Args:
            question: Question utilisateur
            contexte_etat: État système optionnel (depuis Agent)
        
        Returns:
            Réponse formatée
        """
        # Ajouter à l'historique
        self.historique.append({
            "role": "user",
            "message": question,
            "timestamp": str(datetime.now())
        })
        
        if self.mode == "API":
            reponse = self._repondre_api(question, contexte_etat)
        else:
            reponse = self._repondre_demo(question, contexte_etat)
        
        # Ajouter réponse à l'historique
        self.historique.append({
            "role": "assistant",
            "message": reponse,
            "timestamp": str(datetime.now())
        })
        
        return reponse
    
    def _repondre_api(self, question: str, contexte_etat: Optional[Dict]) -> str:
        """Réponse avec Mistral API"""
        # Construire contexte depuis RAG
        regles = self.rag.get_regles_completes()
        logs = self.rag.charger_logs(limit=5)
        
        contexte = f"""RÈGLES D'ORCHESTRATION:
{json.dumps(regles, indent=2, ensure_ascii=False)}

"""
        
        if logs:
            contexte += f"""LOGS RÉCENTS:
{json.dumps(logs, indent=2, ensure_ascii=False)}

"""
        
        if contexte_etat:
            contexte += f"""ÉTAT ACTUEL:
{json.dumps(contexte_etat, indent=2, ensure_ascii=False)}

"""
        
        prompt = f"""{contexte}
Tu es un assistant expert en orchestration des urgences.
Réponds de manière claire et concise.
Base-toi UNIQUEMENT sur les règles et données fournies.

QUESTION: {question}

RÉPONSE:"""

        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ Erreur API: {e}\n\n{self._repondre_demo(question, contexte_etat)}"
    
    def _repondre_demo(self, question: str, contexte_etat: Optional[Dict]) -> str:
        """Réponse en mode démo - recherche mots-clés dans RAG"""
        q_lower = question.lower()
        
        # Chercher dans les règles via RAG
        if any(word in q_lower for word in ["priorité", "rouge", "jaune", "vert", "gris"]):
            regles = self.rag.get_regles_priorite()
            return f"""📖 **Règles de Priorité** (depuis RAG)

{json.dumps(regles, indent=2, ensure_ascii=False)}

💡 *Mode DEMO: Recherche par mots-clés*"""
        
        elif any(word in q_lower for word in ["360", "6h", "exception", "attente"]):
            regles = self.rag.get_regles_priorite()
            exception = regles.get("exception_temps_attente", {})
            return f"""📖 **Exception 360 minutes** (depuis RAG)

{json.dumps(exception, indent=2, ensure_ascii=False)}

⚠️ Si VERT attend >360min, il passe avant JAUNE (mais JAMAIS avant ROUGE)"""
        
        elif any(word in q_lower for word in ["personnel", "infirmière", "aide", "docteur"]):
            personnel = self.rag.get_personnel()
            return f"""📖 **Personnel** (depuis RAG)

{json.dumps(personnel, indent=2, ensure_ascii=False)}"""
        
        elif any(word in q_lower for word in ["salle", "capacité", "infrastructure"]):
            infra = self.rag.get_infrastructure()
            return f"""📖 **Infrastructure** (depuis RAG)

{json.dumps(infra, indent=2, ensure_ascii=False)}"""
        
        elif any(word in q_lower for word in ["contrainte"]):
            contraintes = self.rag.get_contraintes()
            return f"""📖 **Contraintes** (depuis RAG)

{json.dumps(contraintes, indent=2, ensure_ascii=False)}"""
        
        elif any(word in q_lower for word in ["log", "historique"]):
            logs = self.rag.charger_logs(limit=10)
            return f"""📊 **Logs Récents** (depuis RAG)

{json.dumps(logs, indent=2, ensure_ascii=False)}

Total: {len(logs)} événements"""
        
        elif any(word in q_lower for word in ["état", "actuel"]) and contexte_etat:
            return f"""📊 **État Actuel** (depuis Agent)

{json.dumps(contexte_etat, indent=2, ensure_ascii=False)}"""
        
        # Réponse générale
        sections = []
        for filename, regles_file in self.rag.get_regles_completes().items():
            if isinstance(regles_file, dict):
                sections.extend(regles_file.keys())
        
        return f"""📖 **Chatbot Orchestration Urgences**

**Sections disponibles:**
{chr(10).join(f"- {s}" for s in sorted(set(sections)))}

**Fichiers chargés:** {len(self.rag.regles)}

Posez une question spécifique!

💡 *Mode DEMO - Pour IA: configurez MISTRAL_API_KEY*"""
    
    def get_statistiques(self) -> Dict[str, Any]:
        """Statistiques depuis logs RAG"""
        logs = self.rag.charger_logs(limit=1000)
        
        return {
            "total_evenements": len(logs),
            "patients_accueillis": len([l for l in logs if l.get("event_type") == "PATIENT_ACCUEILLI"]),
            "patients_transferes": len([l for l in logs if l.get("event_type") == "PATIENT_TRANSFERE"]),
            "consultations": len([l for l in logs if l.get("event_type") == "CONSULTATION_DEMARREE"]),
            "violations": len([l for l in logs if "VIOLATION" in l.get("event_type", "")])
        }
    
    def clear_historique(self):
        """Efface l'historique de conversation"""
        self.historique = []


# Questions suggérées
QUESTIONS_SUGGEREES = [
    "Quelle est la priorité d'un patient VERT qui attend 7h?",
    "Combien d'infirmières sont disponibles?",
    "Quelles sont les contraintes de surveillance?",
    "Vers quelle unité envoyer un patient ROUGE cardiaque?",
    "Combien de patients ont été traités aujourd'hui?"
]


if __name__ == "__main__":
    from datetime import datetime
    
    print("=== Test Chatbot ===")
    
    # Créer chatbot (crée son propre RAG)
    chatbot = ChatbotOrchestration()
    
    # Tester
    questions = [
        "Quelle est la règle pour un patient VERT qui attend 360 minutes?",
        "Combien d'infirmières?"
    ]
    
    for q in questions:
        print(f"\n❓ {q}")
        reponse = chatbot.repondre(q)
        print(f"💬 {reponse[:300]}...")
    
    # Stats
    print(f"\n📊 Statistiques:")
    print(json.dumps(chatbot.get_statistiques(), indent=2))