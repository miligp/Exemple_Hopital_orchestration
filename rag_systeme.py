"""
RAG PUR: Chargement et Accès aux Règles JSON
Ne fait QUE charger les règles et les rendre disponibles
"""
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from glob import glob


class RAGSysteme:
    """
    RAG pur pour charger et accéder aux règles JSON
    
    Responsabilités:
    ✅ Charger les fichiers JSON de règles
    ✅ Fournir accès aux règles via get_*()
    ✅ Gérer logs JSON (événements)
    ✅ Calculer métriques ARIMA
    
    Ne fait PAS:
    ❌ Répondre à des questions (→ Chatbot)
    ❌ Valider des décisions (→ Agent)
    ❌ Orchestration (→ Agent)
    ❌ Appels API Mistral (→ Chatbot)
    """
    
    def __init__(
        self,
        rules_dir: str = "mini_claude/data/rules",
        logs_dir: str = "mini_claude/data/logs"
    ):
        """Initialize RAG - JUSTE chargement règles"""
        # Auto-détection chemins
        if not os.path.isabs(rules_dir):
            script_dir = Path(__file__).parent.parent
            rules_dir = os.path.join(script_dir, rules_dir)
            logs_dir = os.path.join(script_dir, logs_dir)
        
        self.rules_dir = rules_dir
        self.logs_dir = logs_dir
        self.regles = self._load_all_rules()
        
        Path(self.logs_dir).mkdir(parents=True, exist_ok=True)
    
    def _load_all_rules(self) -> Dict[str, Any]:
        """Charge TOUS les fichiers JSON"""
        regles_combinees = {}
        json_files = glob(os.path.join(self.rules_dir, "*.json"))
        
        if not json_files:
            print(f"⚠️ Aucun fichier JSON dans {self.rules_dir}")
            return {}
        
        print(f"📚 Chargement {len(json_files)} fichier(s) de règles...")
        
        for filepath in json_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    filename = os.path.basename(filepath)
                    regles_combinees[filename] = data
                    print(f"  ✅ {filename}")
            except Exception as e:
                print(f"  ❌ Erreur {filepath}: {e}")
        
        return regles_combinees
    
    # ========== ACCÈS AUX RÈGLES ==========
    
    def get_regles_completes(self) -> Dict[str, Any]:
        """Toutes les règles chargées"""
        return self.regles
    
    def get_section(self, section_path: str) -> Optional[Any]:
        """
        Récupère une section spécifique
        Ex: get_section("regles_orchestration.json/regles_priorite")
        """
        parts = section_path.split('/')
        current = self.regles
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    
    def get_regles_priorite(self) -> Dict[str, Any]:
        """Règles de priorité"""
        for regles_file in self.regles.values():
            if isinstance(regles_file, dict) and "regles_priorite" in regles_file:
                return regles_file["regles_priorite"]
        return {}
    
    def get_personnel(self) -> Dict[str, Any]:
        """Configuration personnel"""
        for regles_file in self.regles.values():
            if isinstance(regles_file, dict) and "personnel" in regles_file:
                return regles_file["personnel"]
        return {}
    
    def get_infrastructure(self) -> Dict[str, Any]:
        """Configuration infrastructure"""
        for regles_file in self.regles.values():
            if isinstance(regles_file, dict) and "infrastructure" in regles_file:
                return regles_file["infrastructure"]
        return {}
    
    def get_unites_transfert(self) -> List[Dict]:
        """Unités de transfert"""
        for regles_file in self.regles.values():
            if isinstance(regles_file, dict) and "unites_transfert" in regles_file:
                return regles_file["unites_transfert"].get("unites", [])
        return []
    
    def get_contraintes(self) -> Dict[str, Any]:
        """Contraintes opérationnelles"""
        for regles_file in self.regles.values():
            if isinstance(regles_file, dict) and "contraintes_principales" in regles_file:
                return regles_file["contraintes_principales"]
        return {}
    
    def get_regles_speciales(self) -> Dict[str, Any]:
        """Règles spéciales (GRIS, ROUGE, etc.)"""
        for regles_file in self.regles.values():
            if isinstance(regles_file, dict) and "regles_speciales" in regles_file:
                return regles_file["regles_speciales"]
        return {}
    
    def chercher_mot_cle(self, mot_cle: str) -> List[Dict]:
        """
        Cherche sections contenant le mot-clé
        Retourne: [{fichier, section, contenu}, ...]
        """
        resultats = []
        mot_cle_lower = mot_cle.lower()
        
        for filename, regles_file in self.regles.items():
            if not isinstance(regles_file, dict):
                continue
            
            for section_nom, section_contenu in regles_file.items():
                if mot_cle_lower in section_nom.lower():
                    resultats.append({
                        "fichier": filename,
                        "section": section_nom,
                        "contenu": section_contenu
                    })
        
        return resultats
    
    # ========== LOGS JSON ==========
    
    def enregistrer_log(self, event_type: str, data: Dict[str, Any], 
                       metriques_instant: Optional[Dict] = None) -> str:
        """Enregistre un événement dans logs JSON"""
        timestamp = datetime.now()
        
        log_entry = {
            "timestamp": timestamp.isoformat(),
            "timestamp_unix": timestamp.timestamp(),
            "event_type": event_type,
            "data": data,
            "metriques_instant": metriques_instant or {}
        }
        
        date_str = timestamp.strftime("%Y-%m-%d")
        log_file = os.path.join(self.logs_dir, f"urgences_{date_str}.json")
        
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        else:
            logs = []
        
        logs.append(log_entry)
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        
        return log_file
    
    def charger_logs(self, date: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Charge les logs d'une date"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        log_file = os.path.join(self.logs_dir, f"urgences_{date}.json")
        
        if not os.path.exists(log_file):
            return []
        
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = json.load(f)
        
        return logs[-limit:]
    
    def calculer_metriques_arima(self, heures: int = 24) -> Dict[str, Any]:
        """Calcule métriques pour modèle ARIMA"""
        from collections import defaultdict
        from datetime import timedelta
        
        logs_periode = []
        for i in range(heures // 24 + 1):
            date = datetime.now()
            if i > 0:
                date = date - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            logs_periode.extend(self.charger_logs(date_str, limit=100000))
        
        metriques = {
            "periode_heures": heures,
            "total_events": len(logs_periode),
            "series_temporelles": {
                "taux_saturation_par_heure": [],
                "flux_arrivees_par_heure": [],
                "flux_sorties_par_heure": [],
                "temps_attente_moyen_par_heure": []
            }
        }
        
        par_heure = defaultdict(list)
        for log in logs_periode:
            timestamp = datetime.fromisoformat(log["timestamp"])
            heure_key = timestamp.strftime("%Y-%m-%d %H:00")
            par_heure[heure_key].append(log)
        
        for heure, events in sorted(par_heure.items()):
            arrivees = len([e for e in events if e.get("event_type") == "PATIENT_ACCUEILLI"])
            sorties = len([e for e in events if e.get("event_type") == "PATIENT_TRANSFERE"])
            
            saturations = [e.get("metriques_instant", {}).get("taux_saturation", 0) 
                          for e in events if e.get("metriques_instant")]
            taux_sat_moyen = sum(saturations) / len(saturations) if saturations else 0
            
            temps_attente = [e.get("metriques_instant", {}).get("temps_attente_moyen", 0) 
                            for e in events if e.get("metriques_instant")]
            temps_moyen = sum(temps_attente) / len(temps_attente) if temps_attente else 0
            
            metriques["series_temporelles"]["taux_saturation_par_heure"].append({
                "heure": heure,
                "taux": round(taux_sat_moyen, 2),
                "arrivees": arrivees,
                "sorties": sorties
            })
            metriques["series_temporelles"]["flux_arrivees_par_heure"].append(arrivees)
            metriques["series_temporelles"]["flux_sorties_par_heure"].append(sorties)
            metriques["series_temporelles"]["temps_attente_moyen_par_heure"].append(round(temps_moyen, 2))
        
        return metriques


if __name__ == "__main__":
    rag = RAGSysteme()
    
    print("\n=== RAG PUR ===")
    print(f"Règles chargées: {list(rag.regles.keys())}")
    print(f"\nPriorités: {bool(rag.get_regles_priorite())}")
    print(f"Personnel: {bool(rag.get_personnel())}")
    print(f"Infrastructure: {bool(rag.get_infrastructure())}")