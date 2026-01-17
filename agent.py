"""
Agent d'Orchestration des Urgences
Utilise le RAG pour accéder aux règles
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from rag_systeme import RAGSysteme


# ========== ENUMS ==========

class Gravite(Enum):
    ROUGE = "ROUGE"
    JAUNE = "JAUNE"
    VERT = "VERT"
    GRIS = "GRIS"


class StatutPatient(Enum):
    EN_ATTENTE = "EN_ATTENTE"
    EN_CONSULTATION = "EN_CONSULTATION"
    TRANSFERE = "TRANSFERE"
    PARTI = "PARTI"


class StatutPersonnel(Enum):
    DISPONIBLE = "DISPONIBLE"
    OCCUPE = "OCCUPE"
    EN_TRANSPORT = "EN_TRANSPORT"


# ========== MODÈLES ==========

@dataclass
class Patient:
    """Patient dans le système"""
    id: str
    prenom: str
    nom: str
    gravite: Gravite
    type_maladie: List[str]
    heure_arrivee: datetime
    statut: StatutPatient = StatutPatient.EN_ATTENTE
    salle: Optional[int] = None
    
    def temps_attente_minutes(self) -> float:
        """Temps d'attente en minutes"""
        return (datetime.now() - self.heure_arrivee).total_seconds() / 60
    
    def priorite_effective(self) -> int:
        """
        Calcule priorité avec exception 360 minutes
        1 = Plus prioritaire
        """
        # ROUGE toujours priorité 1
        if self.gravite == Gravite.ROUGE:
            return 1
        
        # VERT >360min passe à priorité 2
        if self.gravite == Gravite.VERT and self.temps_attente_minutes() > 360:
            return 2
        
        # JAUNE priorité 3
        if self.gravite == Gravite.JAUNE:
            return 3
        
        # VERT <360min priorité 4
        if self.gravite == Gravite.VERT:
            return 4
        
        # GRIS priorité 5
        return 5


@dataclass
class SalleAttente:
    """Salle d'attente"""
    numero: int
    capacite: int
    patients: List[Patient] = field(default_factory=list)
    derniere_surveillance: datetime = field(default_factory=datetime.now)
    
    def est_pleine(self) -> bool:
        return len(self.patients) >= self.capacite
    
    def a_de_la_place(self) -> bool:
        return len(self.patients) < self.capacite
    
    def ajouter_patient(self, patient: Patient) -> bool:
        if self.est_pleine():
            return False
        self.patients.append(patient)
        patient.salle = self.numero
        return True
    
    def retirer_patient(self, patient: Patient):
        if patient in self.patients:
            self.patients.remove(patient)
            patient.salle = None


@dataclass
class Personnel:
    """Personnel médical"""
    id: str
    nom: str
    type: str  # FIXE ou MOBILE
    statut: StatutPersonnel = StatutPersonnel.DISPONIBLE
    patient_en_charge: Optional[Patient] = None
    fin_activite: Optional[datetime] = None


@dataclass
class Unite:
    """Unité de transfert"""
    nom: str
    capacite: int
    patients_actuels: int = 0
    specialites: List[str] = field(default_factory=list)
    
    def a_de_la_place(self) -> bool:
        return self.patients_actuels < self.capacite
    
    def accepter_patient(self) -> bool:
        if self.a_de_la_place():
            self.patients_actuels += 1
            return True
        return False


# ========== AGENT ==========

class AgentOrchestration:
    """
    Agent d'orchestration utilisant le RAG
    
    Responsabilités:
    - Gérer l'état du système (patients, salles, personnel)
    - Calculer file de priorité avec exception 360min
    - Orchestrer consultations et transferts
    - Valider décisions contre règles RAG
    - Logger tous événements dans RAG
    """
    
    def __init__(self, rag: Optional[RAGSysteme] = None):
        """
        Initialise l'agent avec règles depuis RAG
        
        Args:
            rag: Instance RAG (partagée avec chatbot)
        """
        self.rag = rag if rag else RAGSysteme()
        
        # Charger configuration depuis RAG
        self._initialiser_depuis_rag()
        
        # État système
        self.patients_en_attente: List[Patient] = []
        self.patients_consultes: List[Patient] = []
        self.patients_transferes: List[Patient] = []
        self.violations: List[Dict] = []
        
        print("✅ Agent initialisé depuis règles RAG")
    
    def _initialiser_depuis_rag(self):
        """Initialise infrastructure et personnel depuis RAG"""
        # Infrastructure
        infra = self.rag.get_infrastructure()
        self.salles = []
        
        if "salles_attente" in infra:
            for salle_config in infra["salles_attente"]:
                self.salles.append(SalleAttente(
                    numero=salle_config["numero"],
                    capacite=salle_config["capacite"]
                ))
        
        # Personnel
        personnel_config = self.rag.get_personnel()
        
        # Docteur
        if "docteur" in personnel_config:
            self.docteur = Personnel(
                id="docteur_1",
                nom="Dr. Urgences",
                type="FIXE"
            )
        
        # Infirmières
        self.infirmieres = []
        if "infirmieres" in personnel_config:
            for i, inf in enumerate(personnel_config["infirmieres"]):
                self.infirmieres.append(Personnel(
                    id=f"infirmiere_{i+1}",
                    nom=inf["nom"],
                    type=inf["type"]
                ))
        
        # Aides-soignants
        self.aides_soignants = []
        if "aides_soignants" in personnel_config:
            for i, aide in enumerate(personnel_config["aides_soignants"]):
                self.aides_soignants.append(Personnel(
                    id=f"aide_{i+1}",
                    nom=aide["nom"],
                    type=aide["type"]
                ))
        
        # Unités de transfert
        self.unites = []
        unites_config = self.rag.get_unites_transfert()
        for unite_cfg in unites_config:
            self.unites.append(Unite(
                nom=unite_cfg["nom"],
                capacite=unite_cfg.get("capacite_initiale", unite_cfg.get("capacite", 10)),
                specialites=unite_cfg.get("specialites", [])
            ))
    
    # ========== ACCUEIL PATIENTS ==========
    
    def accueillir_patient(self, patient: Patient) -> Dict[str, Any]:
        """
        Accueille un nouveau patient
        
        Returns:
            Résultat avec salle assignée ou erreur
        """
        # Trouver salle disponible
        for salle in self.salles:
            if salle.a_de_la_place():
                salle.ajouter_patient(patient)
                self.patients_en_attente.append(patient)
                
                # Logger dans RAG
                self.rag.enregistrer_log(
                    "PATIENT_ACCUEILLI",
                    {
                        "patient_id": patient.id,
                        "nom": f"{patient.prenom} {patient.nom}",
                        "gravite": patient.gravite.value,
                        "salle": salle.numero
                    },
                    self._calculer_metriques_instant()
                )
                
                return {
                    "success": True,
                    "message": f"Patient {patient.id} assigné à salle {salle.numero}",
                    "salle": salle.numero
                }
        
        # Aucune salle disponible
        self.violations.append({
            "type": "SALLE_PLEINE",
            "timestamp": datetime.now(),
            "patient_id": patient.id
        })
        
        self.rag.enregistrer_log(
            "SALLE_PLEINE",
            {"patient_id": patient.id, "gravite": patient.gravite.value},
            self._calculer_metriques_instant()
        )
        
        return {
            "success": False,
            "message": "Aucune salle disponible",
            "capacite_totale": sum(s.capacite for s in self.salles),
            "occupation_actuelle": sum(len(s.patients) for s in self.salles)
        }
    
    # ========== FILE DE PRIORITÉ ==========
    
    def calculer_file_priorite(self) -> List[Patient]:
        """
        Calcule file de priorité avec exception 360min
        Utilise Patient.priorite_effective()
        
        Returns:
            Liste triée par priorité puis heure arrivée
        """
        return sorted(
            self.patients_en_attente,
            key=lambda p: (p.priorite_effective(), p.heure_arrivee)
        )
    
    def selectionner_prochain_patient(self) -> Optional[Patient]:
        """Sélectionne prochain patient selon priorité"""
        file = self.calculer_file_priorite()
        return file[0] if file else None
    
    # ========== CONSULTATION ==========
    
    def demarrer_consultation(self, patient: Patient) -> Dict[str, Any]:
        """Démarre une consultation"""
        if self.docteur.statut != StatutPersonnel.DISPONIBLE:
            return {
                "success": False,
                "message": "Docteur occupé",
                "fin_consultation": self.docteur.fin_activite
            }
        
        # Lire durée depuis règles RAG
        regles_priorite = self.rag.get_regles_priorite()
        duree_min = 5  # Défaut
        
        if "niveaux" in regles_priorite:
            for niveau in regles_priorite["niveaux"]:
                if niveau["gravite"] == patient.gravite.value:
                    duree_min = niveau.get("temps_consultation_max", 5)
                    break
        
        # Démarrer consultation
        self.docteur.statut = StatutPersonnel.OCCUPE
        self.docteur.patient_en_charge = patient
        self.docteur.fin_activite = datetime.now() + timedelta(minutes=duree_min)
        
        patient.statut = StatutPatient.EN_CONSULTATION
        self.patients_en_attente.remove(patient)
        
        # Logger
        self.rag.enregistrer_log(
            "CONSULTATION_DEMARREE",
            {
                "patient_id": patient.id,
                "gravite": patient.gravite.value,
                "duree_prevue_min": duree_min
            },
            self._calculer_metriques_instant()
        )
        
        return {
            "success": True,
            "patient_id": patient.id,
            "duree_min": duree_min,
            "fin_prevue": self.docteur.fin_activite
        }
    
    def terminer_consultation(self, patient: Patient) -> Dict[str, Any]:
        """Termine consultation et suggère transfert"""
        # Libérer docteur
        self.docteur.statut = StatutPersonnel.DISPONIBLE
        self.docteur.patient_en_charge = None
        self.docteur.fin_activite = None
        
        patient.statut = StatutPatient.TRANSFERE
        self.patients_consultes.append(patient)
        
        # Suggérer unité via RAG
        suggestion = self._suggerer_unite_transfert(patient)
        
        # Logger
        self.rag.enregistrer_log(
            "CONSULTATION_TERMINEE",
            {
                "patient_id": patient.id,
                "unite_suggeree": suggestion["unite"]
            },
            self._calculer_metriques_instant()
        )
        
        return {
            "success": True,
            "patient_id": patient.id,
            "suggestion_transfert": suggestion
        }
    
    # ========== TRANSFERT ==========
    
    def _suggerer_unite_transfert(self, patient: Patient) -> Dict[str, Any]:
        """
        Suggère unité de transfert en utilisant règles RAG
        """
        regles_speciales = self.rag.get_regles_speciales()
        
        # GRIS → MAISON
        if patient.gravite == Gravite.GRIS and "gris" in regles_speciales:
            return {
                "unite": regles_speciales["gris"]["transfert"],
                "justification": regles_speciales["gris"]["description"],
                "priorite": "NORMALE"
            }
        
        # ROUGE → Chercher spécialité ou SOINS_CRITIQUES
        if patient.gravite == Gravite.ROUGE:
            for unite in self.unites:
                for patho in patient.type_maladie:
                    if patho.lower() in [s.lower() for s in unite.specialites]:
                        return {
                            "unite": unite.nom,
                            "justification": f"Spécialité {patho} → {unite.nom}",
                            "priorite": "IMMEDIATE",
                            "places_disponibles": unite.capacite - unite.patients_actuels
                        }
            
            # Fallback ROUGE
            if "rouge" in regles_speciales:
                return {
                    "unite": regles_speciales["rouge"]["transfert_prioritaire"],
                    "justification": regles_speciales["rouge"]["description"],
                    "priorite": "IMMEDIATE"
                }
        
        # JAUNE/VERT → Chercher spécialité
        for unite in self.unites:
            for patho in patient.type_maladie:
                if patho.lower() in [s.lower() for s in unite.specialites]:
                    return {
                        "unite": unite.nom,
                        "justification": f"Pathologie {patho} correspond à {unite.nom}",
                        "priorite": "NORMALE",
                        "places_disponibles": unite.capacite - unite.patients_actuels
                    }
        
        # Fallback
        return {
            "unite": "ORTHOPÉDIE",
            "justification": "Unité par défaut",
            "priorite": "NORMALE"
        }
    
    def transferer_patient(self, patient: Patient, unite_nom: str) -> Dict[str, Any]:
        """Transfère patient vers unité"""
        # Trouver unité
        unite = next((u for u in self.unites if u.nom == unite_nom), None)
        
        if not unite:
            return {"success": False, "message": f"Unité {unite_nom} introuvable"}
        
        if not unite.a_de_la_place():
            self.rag.enregistrer_log(
                "UNITE_SATUREE",
                {"unite": unite_nom, "patient_id": patient.id},
                self._calculer_metriques_instant()
            )
            return {"success": False, "message": f"Unité {unite_nom} pleine"}
        
        # Transférer
        unite.accepter_patient()
        self.patients_transferes.append(patient)
        
        # Retirer de salle attente
        for salle in self.salles:
            if patient in salle.patients:
                salle.retirer_patient(patient)
        
        # Logger
        self.rag.enregistrer_log(
            "PATIENT_TRANSFERE",
            {
                "patient_id": patient.id,
                "unite": unite_nom,
                "gravite": patient.gravite.value
            },
            self._calculer_metriques_instant()
        )
        
        return {
            "success": True,
            "patient_id": patient.id,
            "unite": unite_nom
        }
    
    # ========== CYCLE ORCHESTRATION ==========
    
    # Dans agent.py

    def cycle_orchestration(self, temps_virtuel: datetime = None) -> List[str]:
        actions = []
        maintenant = temps_virtuel if temps_virtuel else datetime.now()
    
        # --- 1. GESTION DU PERSONNEL (Mise à jour des statuts) ---
        for p in self.infirmieres + self.aides_soignants:
            if p.statut == StatutPersonnel.OCCUPE and p.fin_activite and maintenant >= p.fin_activite:
                p.statut = StatutPersonnel.DISPONIBLE
                p.fin_activite = None
                p.patient_en_charge = None

        # --- 2. FIN DE CONSULTATION & DÉBUT TRANSPORT ---
        if self.docteur.statut == StatutPersonnel.OCCUPE:
            if maintenant >= self.docteur.fin_activite:
                patient = self.docteur.patient_en_charge
                # On cherche un aide-soignant libre pour le transfert
                aide = next((a for a in self.aides_soignants if a.statut == StatutPersonnel.DISPONIBLE), None)
            
                if aide:
                    # Libérer le docteur
                    self.docteur.statut = StatutPersonnel.DISPONIBLE
                    self.docteur.patient_en_charge = None
                
                    # Occuper l'aide-soignant pour 15 min
                    suggestion = self._suggerer_unite_transfert(patient)
                    aide.statut = StatutPersonnel.OCCUPE
                    aide.fin_activite = maintenant + timedelta(minutes=15)
                    aide.patient_en_charge = patient
                
                    patient.statut = StatutPatient.TRANSFERE
                    self.transferer_patient(patient, suggestion["unite"])
                    actions.append(f"✅ Consult terminée. 🚑 {aide.nom} transporte {patient.id} vers {suggestion['unite']} (15 min)")
                else:
                    actions.append(f"⚠️ {patient.id} attend un transport (tous les aides sont occupés)")

        # --- 3. SURVEILLANCE DES SALLES (Infirmières) ---
        for salle in self.salles:
            if (maintenant - salle.derniere_surveillance).total_seconds() / 60 >= 15:
                inf = next((i for i in self.infirmieres if i.statut == StatutPersonnel.DISPONIBLE), None)
                if inf:
                    inf.statut = StatutPersonnel.OCCUPE
                    inf.fin_activite = maintenant + timedelta(minutes=5)
                    salle.derniere_surveillance = maintenant
                    actions.append(f"🩺 {inf.nom} inspecte la Salle {salle.numero}")
        # --- 4. NOUVELLE CONSULTATION ---
        if self.docteur.statut == StatutPersonnel.DISPONIBLE:
            prochain = self.selectionner_prochain_patient()
            if prochain:
                self.docteur.statut = StatutPersonnel.OCCUPE
                self.docteur.patient_en_charge = prochain
                self.docteur.fin_activite = maintenant + timedelta(minutes=5)
                prochain.statut = StatutPatient.EN_CONSULTATION
                if prochain in self.patients_en_attente: self.patients_en_attente.remove(prochain)
                actions.append(f"👨‍⚕️ {prochain.id} entre en consultation")
            
        return actions
    
    def _verifier_contraintes(self) -> List[str]:
        """Vérifie contraintes opérationnelles"""
        violations = []
        
        # Vérifier surveillance salles (15min)
        for salle in self.salles:
            if len(salle.patients) > 0:
                temps_sans_surveillance = (datetime.now() - salle.derniere_surveillance).total_seconds() / 60
                if temps_sans_surveillance > 15:
                    violations.append(f"⚠️  Salle {salle.numero} sans surveillance >{int(temps_sans_surveillance)}min")
                    self.rag.enregistrer_log(
                        "VIOLATION_CONTRAINTE_SURVEILLANCE",
                        {"salle": salle.numero, "duree_min": temps_sans_surveillance},
                        self._calculer_metriques_instant()
                    )
        
        return violations
    
    # ========== ÉTAT SYSTÈME ==========
    
    def get_etat_complet(self) -> Dict[str, Any]:
        return {
            "salles": [
                {
                    "numero": s.numero,
                    "capacite": s.capacite,
                    "occupation": len(s.patients), # Correction pour app.py
                    "taux_occupation": round(len(s.patients) / s.capacite * 100, 2) if s.capacite > 0 else 0,
                    "patients": [
                        {"id": p.id, "nom": f"{p.prenom} {p.nom}", "gravite": p.gravite.value}
                        for p in s.patients
                    ],
                }
                for s in self.salles
            ],
            "docteur": {
                "disponible": self.docteur.statut == StatutPersonnel.DISPONIBLE,
                "patient_actuel": self.docteur.patient_en_charge.id if self.docteur.patient_en_charge else None,
                "fin_consultation": self.docteur.fin_activite.isoformat() if self.docteur.fin_activite else None
            },
            "personnel": {
                "infirmieres": [
                    {"nom": i.nom, "statut": i.statut.value, "type": i.type}
                    for i in self.infirmieres
                ],
                "aides_soignants": [
                    {"nom": a.nom, "statut": a.statut.value, "type": a.type}
                    for a in self.aides_soignants
                ]
            },
            "metriques": self._calculer_metriques_instant(),
            "file_attente": [
                {
                    "id": p.id,
                    "nom": f"{p.prenom} {p.nom}",
                    "gravite": p.gravite.value,
                    "priorite_effective": p.priorite_effective(),
                    "attente_min": int(p.temps_attente_minutes()),
                    "exception_360": p.gravite == Gravite.VERT and p.temps_attente_minutes() > 360
                }
                for p in self.calculer_file_priorite()
            ],
            "unites": [
                {
                    "nom": u.nom, 
                    "capacite": u.capacite, 
                    "occupation": u.patients_actuels, 
                    "disponible": u.a_de_la_place()
                }
                for u in self.unites
            ]
        }
    
    def _calculer_metriques_instant(self) -> Dict[str, Any]:
        """Calcule métriques instantanées"""
        total_places = sum(s.capacite for s in self.salles)
        occupation = sum(len(s.patients) for s in self.salles)
        
        temps_attente = [p.temps_attente_minutes() for p in self.patients_en_attente]
        
        return {
            "taux_saturation": round(occupation / total_places * 100, 2) if total_places > 0 else 0,
            "patients_attente": len(self.patients_en_attente),
            "patients_consultation": 1 if self.docteur.statut == StatutPersonnel.OCCUPE else 0,
            "patients_transferes": len(self.patients_transferes),
            "temps_attente_moyen": round(sum(temps_attente) / len(temps_attente), 2) if temps_attente else 0,
            "temps_attente_max": round(max(temps_attente), 2) if temps_attente else 0
        }


if __name__ == "__main__":
    print("=== Test Agent ===")
    
    # Créer agent (crée son propre RAG)
    agent = AgentOrchestration()
    
    # Ajouter patients test
    p1 = Patient(
        id="P001",
        prenom="Marie",
        nom="Dupont",
        gravite=Gravite.ROUGE,
        type_maladie=["respiratoire"],
        heure_arrivee=datetime.now()
    )
    
    p2 = Patient(
        id="P002",
        prenom="Jean",
        nom="Martin",
        gravite=Gravite.VERT,
        type_maladie=["entorse"],
        heure_arrivee=datetime.now() - timedelta(hours=7)  # 7h d'attente
    )
    
    # Accueillir
    print("\n1. Accueil patients:")
    print(agent.accueillir_patient(p1))
    print(agent.accueillir_patient(p2))
    
    # File priorité
    print("\n2. File de priorité:")
    for p in agent.calculer_file_priorite():
        print(f"  - {p.id} ({p.gravite.value}) priorité={p.priorite_effective()} attente={int(p.temps_attente_minutes())}min")
    
    # Cycle
    print("\n3. Cycle orchestration:")
    actions = agent.cycle_orchestration()
    for action in actions:
        print(f"  {action}")
    
    # État
    print("\n4. État système:")
    etat = agent.get_etat_complet()
    print(f"  Saturation: {etat['metriques']['taux_saturation']}%")
    print(f"  En attente: {etat['metriques']['patients_attente']}")