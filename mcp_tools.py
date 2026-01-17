"""
MCP Tools: Outils pour enrichir et modifier le scénario
Utilise RAG + Agent
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import json

from rag_systeme import RAGSysteme
from agent import AgentOrchestration, Patient, Gravite


class MCPTools:
    """
    Outils MCP pour enrichir le système
    
    Utilise:
    - RAG pour accéder aux règles
    - Agent pour modifier l'état
    """
    
    def __init__(self, rag: RAGSysteme, agent: AgentOrchestration):
        """
        Args:
            rag: Instance RAG partagée
            agent: Instance Agent partagée
        """
        self.rag = rag
        self.agent = agent
        print("✅ MCP Tools initialisé")
    
    # ========== GÉNÉRATION PATIENTS ==========
    
    def generer_patient_aleatoire(self, id_suffix: Optional[str] = None) -> Patient:
        """Génère un patient aléatoire"""
        prenoms = ["Marie", "Jean", "Sophie", "Pierre", "Lucie", "Thomas", "Emma", "Lucas"]
        noms = ["Dupont", "Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Simon", "Michel"]
        
        gravites_pool = [
            Gravite.ROUGE,
            Gravite.JAUNE, Gravite.JAUNE,
            Gravite.VERT, Gravite.VERT, Gravite.VERT,
            Gravite.GRIS, Gravite.GRIS
        ]
        
        maladies_par_gravite = {
            Gravite.ROUGE: [["cardiaque"], ["respiratoire"], ["neurologique"], ["AVC"]],
            Gravite.JAUNE: [["fracture"], ["entorse"], ["douleur thoracique"]],
            Gravite.VERT: [["entorse"], ["coupure"], ["fievre"]],
            Gravite.GRIS: [["rhume"], ["fatigue"]]
        }
        
        gravite = random.choice(gravites_pool)
        
        patient_id = id_suffix or f"P{random.randint(1000, 9999)}"
        
        return Patient(
            id=patient_id,
            prenom=random.choice(prenoms),
            nom=random.choice(noms),
            gravite=gravite,
            type_maladie=random.choice(maladies_par_gravite[gravite]),
            heure_arrivee=datetime.now()
        )
    
    def ajouter_patients_masse(
        self,
        nombre: int,
        distribution: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Ajoute N patients selon distribution
        
        Args:
            nombre: Nombre de patients
            distribution: {"ROUGE": 0.1, "JAUNE": 0.3, ...}
        
        Returns:
            Résultat avec patients ajoutés
        """
        if distribution is None:
            distribution = {
                "ROUGE": 0.1,
                "JAUNE": 0.25,
                "VERT": 0.5,
                "GRIS": 0.15
            }
        
        patients_ajoutes = []
        patients_refuses = []
        
        for i in range(nombre):
            # Déterminer gravité selon distribution
            rand = random.random()
            cumul = 0
            gravite_choisie = Gravite.VERT
            
            for grav_str, prob in distribution.items():
                cumul += prob
                if rand <= cumul:
                    gravite_choisie = Gravite[grav_str]
                    break
            
            # Créer patient
            patient = self.generer_patient_aleatoire(f"PMASSE{i+1:03d}")
            patient.gravite = gravite_choisie
            
            # Accueillir via Agent
            resultat = self.agent.accueillir_patient(patient)
            
            if resultat["success"]:
                patients_ajoutes.append(patient.id)
            else:
                patients_refuses.append(patient.id)
        
        return {
            "total_generes": nombre,
            "ajoutes": len(patients_ajoutes),
            "refuses": len(patients_refuses),
            "patients_ajoutes": patients_ajoutes,
            "patients_refuses": patients_refuses,
            "taux_saturation_apres": self.agent._calculer_metriques_instant()["taux_saturation"]
        }
    
    # ========== SCÉNARIOS PRÉDÉFINIS ==========
    
    def creer_scenario_afflux(self) -> Dict[str, Any]:
        """
        Scénario: Afflux massif de patients
        Simule accident de la route ou événement majeur
        """
        print("🚨 Scénario: AFFLUX MASSIF")
        
        # 3 ROUGE, 5 JAUNE, 2 VERT
        patients_scenario = [
            (Gravite.ROUGE, ["traumatisme"], "Accident grave"),
            (Gravite.ROUGE, ["fracture"], "Polytraumatisme"),
            (Gravite.ROUGE, ["neurologique"], "Traumatisme crânien"),
            (Gravite.JAUNE, ["fracture"], "Fracture bras"),
            (Gravite.JAUNE, ["fracture"], "Fracture jambe"),
            (Gravite.JAUNE, ["entorse"], "Entorse sévère"),
            (Gravite.JAUNE, ["coupure"], "Plaie profonde"),
            (Gravite.JAUNE, ["douleur"], "Douleurs thoraciques"),
            (Gravite.VERT, ["coupure"], "Coupure superficielle"),
            (Gravite.VERT, ["contusion"], "Contusion"),
        ]
        
        resultats = []
        
        for i, (gravite, maladies, desc) in enumerate(patients_scenario):
            patient = Patient(
                id=f"AFFLUX{i+1:02d}",
                prenom=f"Victime",
                nom=f"{i+1}",
                gravite=gravite,
                type_maladie=maladies,
                heure_arrivee=datetime.now()
            )
            
            resultat = self.agent.accueillir_patient(patient)
            resultats.append({
                "patient": patient.id,
                "gravite": gravite.value,
                "description": desc,
                "accueilli": resultat["success"]
            })
        
        return {
            "scenario": "AFFLUX_MASSIF",
            "patients_generes": len(patients_scenario),
            "resultats": resultats,
            "metriques_apres": self.agent._calculer_metriques_instant()
        }
    
    def creer_scenario_exception_360(self) -> Dict[str, Any]:
        """
        Scénario: Tester exception 360 minutes
        Crée patient VERT qui attend depuis 7h
        """
        print("⏱️  Scénario: EXCEPTION 360 MINUTES")
        
        # Patient VERT avec 7h d'attente
        patient_vert = Patient(
            id="VERT_7H",
            prenom="Patient",
            nom="Longue Attente",
            gravite=Gravite.VERT,
            type_maladie=["entorse"],
            heure_arrivee=datetime.now() - timedelta(hours=7)
        )
        
        # Patient JAUNE récent
        patient_jaune = Patient(
            id="JAUNE_RECENT",
            prenom="Patient",
            nom="Récent",
            gravite=Gravite.JAUNE,
            type_maladie=["fracture"],
            heure_arrivee=datetime.now()
        )
        
        # Accueillir
        self.agent.accueillir_patient(patient_vert)
        self.agent.accueillir_patient(patient_jaune)
        
        # Vérifier priorités
        file = self.agent.calculer_file_priorite()
        
        return {
            "scenario": "EXCEPTION_360",
            "patient_vert": {
                "id": patient_vert.id,
                "attente_minutes": patient_vert.temps_attente_minutes(),
                "priorite_effective": patient_vert.priorite_effective()
            },
            "patient_jaune": {
                "id": patient_jaune.id,
                "attente_minutes": patient_jaune.temps_attente_minutes(),
                "priorite_effective": patient_jaune.priorite_effective()
            },
            "file_priorite": [
                {
                    "id": p.id,
                    "gravite": p.gravite.value,
                    "priorite": p.priorite_effective()
                }
                for p in file
            ],
            "exception_activee": patient_vert.priorite_effective() < patient_jaune.priorite_effective()
        }
    
    def creer_scenario_saturation(self) -> Dict[str, Any]:
        """
        Scénario: Saturation progressive
        Ajoute patients jusqu'à saturation
        """
        print("📊 Scénario: SATURATION")
        
        capacite_totale = sum(s.capacite for s in self.agent.salles)
        occupation_initiale = sum(len(s.patients) for s in self.agent.salles)
        places_restantes = capacite_totale - occupation_initiale
        
        # Ajouter jusqu'à 100% + 5
        nombre_a_ajouter = places_restantes + 5
        
        resultats = self.ajouter_patients_masse(nombre_a_ajouter)
        
        return {
            "scenario": "SATURATION",
            "capacite_totale": capacite_totale,
            "occupation_initiale": occupation_initiale,
            "patients_ajoutes": resultats["ajoutes"],
            "patients_refuses": resultats["refuses"],
            "taux_saturation_final": resultats["taux_saturation_apres"],
            "saturation_atteinte": resultats["taux_saturation_apres"] >= 100
        }
    
    # ========== MODIFICATIONS SYSTÈME ==========
    
    def modifier_capacite_salle(self, numero_salle: int, nouvelle_capacite: int) -> Dict[str, Any]:
        """Modifie capacité d'une salle"""
        salle = next((s for s in self.agent.salles if s.numero == numero_salle), None)
        
        if not salle:
            return {"success": False, "message": f"Salle {numero_salle} introuvable"}
        
        ancienne_capacite = salle.capacite
        salle.capacite = nouvelle_capacite
        
        # Logger
        self.rag.enregistrer_log(
            "MODIFICATION_CAPACITE",
            {
                "salle": numero_salle,
                "ancienne_capacite": ancienne_capacite,
                "nouvelle_capacite": nouvelle_capacite
            },
            self.agent._calculer_metriques_instant()
        )
        
        return {
            "success": True,
            "salle": numero_salle,
            "ancienne_capacite": ancienne_capacite,
            "nouvelle_capacite": nouvelle_capacite,
            "occupation_actuelle": len(salle.patients)
        }
    
    def ajouter_personnel_temporaire(self, type_personnel: str, nom: str) -> Dict[str, Any]:
        """Ajoute personnel temporaire"""
        from agents.agent import Personnel, StatutPersonnel
        
        nouveau = Personnel(
            id=f"temp_{nom}",
            nom=f"{nom} (Temporaire)",
            type="MOBILE"
        )
        
        if type_personnel == "infirmiere":
            self.agent.infirmieres.append(nouveau)
        elif type_personnel == "aide_soignant":
            self.agent.aides_soignants.append(nouveau)
        else:
            return {"success": False, "message": f"Type {type_personnel} invalide"}
        
        return {
            "success": True,
            "type": type_personnel,
            "nom": nouveau.nom,
            "total_apres": len(self.agent.infirmieres) if type_personnel == "infirmiere" else len(self.agent.aides_soignants)
        }
    
    # ========== ANALYSE ==========
    
    def analyser_flux_24h(self) -> Dict[str, Any]:
        """Analyse flux des dernières 24h via logs RAG"""
        metriques = self.rag.calculer_metriques_arima(24)
        
        series = metriques["series_temporelles"]
        
        # Calculer statistiques
        taux_sat = [h["taux"] for h in series["taux_saturation_par_heure"]]
        arrivees = series["flux_arrivees_par_heure"]
        sorties = series["flux_sorties_par_heure"]
        
        return {
            "periode_heures": 24,
            "total_evenements": metriques["total_events"],
            "saturation": {
                "moyenne": round(sum(taux_sat) / len(taux_sat), 2) if taux_sat else 0,
                "max": max(taux_sat) if taux_sat else 0,
                "min": min(taux_sat) if taux_sat else 0
            },
            "flux": {
                "total_arrivees": sum(arrivees),
                "total_sorties": sum(sorties),
                "pic_arrivees": max(arrivees) if arrivees else 0,
                "pic_sorties": max(sorties) if sorties else 0
            },
            "series_temporelles": metriques["series_temporelles"]
        }
    
    def get_statistiques_globales(self) -> Dict[str, Any]:
        """Statistiques globales du système"""
        logs = self.rag.charger_logs(limit=10000)
        
        return {
            "total_evenements": len(logs),
            "par_type": {
                "patients_accueillis": len([l for l in logs if l.get("event_type") == "PATIENT_ACCUEILLI"]),
                "consultations": len([l for l in logs if l.get("event_type") == "CONSULTATION_DEMARREE"]),
                "transferts": len([l for l in logs if l.get("event_type") == "PATIENT_TRANSFERE"]),
                "violations_surveillance": len([l for l in logs if l.get("event_type") == "VIOLATION_CONTRAINTE_SURVEILLANCE"]),
                "salles_pleines": len([l for l in logs if l.get("event_type") == "SALLE_PLEINE"]),
                "unites_saturees": len([l for l in logs if l.get("event_type") == "UNITE_SATUREE"])
            },
            "etat_actuel": self.agent.get_etat_complet()["metriques"]
        }


if __name__ == "__main__":
    print("=== Test MCP Tools ===")
    
    from rag_systeme import RAGSysteme
    from agent import AgentOrchestration
    
    # Créer RAG et Agent
    rag = RAGSysteme()
    agent = AgentOrchestration(rag)
    
    # Créer MCP
    mcp = MCPTools(rag, agent)
    
    # Test 1: Ajouter patients en masse
    print("\n1. Ajouter 5 patients:")
    resultat = mcp.ajouter_patients_masse(5)
    print(f"  Ajoutés: {resultat['ajoutes']}")
    print(f"  Refusés: {resultat['refuses']}")
    print(f"  Saturation: {resultat['taux_saturation_apres']}%")
    
    # Test 2: Scénario exception 360
    print("\n2. Scénario exception 360min:")
    scenario = mcp.creer_scenario_exception_360()
    print(f"  Exception activée: {scenario['exception_activee']}")
    print(f"  VERT priorité: {scenario['patient_vert']['priorite_effective']}")
    print(f"  JAUNE priorité: {scenario['patient_jaune']['priorite_effective']}")
    
    # Test 3: Stats
    print("\n3. Statistiques:")
    stats = mcp.get_statistiques_globales()
    print(f"  Total événements: {stats['total_evenements']}")
    print(f"  Patients accueillis: {stats['par_type']['patients_accueillis']}")