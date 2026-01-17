"""
Application Streamlit avec Simulation Temporelle Visuelle
Interface inspirée de l'ED Manager avec auto-avancement du temps
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from datetime import datetime, timedelta
import time
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Imports modules
from rag_systeme import RAGSysteme
from chatbot import ChatbotOrchestration
from agent import AgentOrchestration, Patient, Gravite
from mcp_tools import MCPTools


# ========== CONFIGURATION ==========

st.set_page_config(
    page_title="🏥 Orchestration Urgences - Simulation",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ========== SESSION STATE ==========

def initialiser_session():
    """Initialise session state avec 1 RAG partagé + simulation"""
    if 'rag' not in st.session_state:
        st.session_state.rag = RAGSysteme()
        st.session_state.agent = AgentOrchestration(st.session_state.rag)
        st.session_state.chatbot = ChatbotOrchestration(st.session_state.rag)
        st.session_state.mcp = MCPTools(st.session_state.rag, st.session_state.agent)
        
        # Simulation
        st.session_state.simulation_running = False
        st.session_state.simulation_speed = 0.5  # secondes entre ticks
        st.session_state.temps_simule = 0  # minutes simulées
        st.session_state.events_log = []
        
        st.session_state.initialized = True


def ajouter_event_log(message: str):
    """Ajoute un événement au log avec timestamp"""
    temps = st.session_state.temps_simule
    timestamp = f"[T+{temps:03d}min]"
    st.session_state.events_log.append(f"{timestamp} {message}")


# ========== VISUALISATIONS ==========

def afficher_metriques_temps_reel():
    """Métriques en haut avec temps simulé"""
    etat = st.session_state.agent.get_etat_complet()
    metriques = etat['metriques']
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        # Temps simulé
        heures = st.session_state.temps_simule // 60
        minutes = st.session_state.temps_simule % 60
        st.metric(
            "⏰ Temps Simulé",
            f"{heures:02d}h{minutes:02d}",
            delta="+1min" if st.session_state.simulation_running else None
        )
    
    with col2:
        st.metric("📊 Saturation", f"{metriques['taux_saturation']}%")
    
    with col3:
        st.metric("⏳ En Attente", metriques['patients_attente'])
    
    with col4:
        st.metric("👨‍⚕️ Consultation", metriques['patients_consultation'])
    
    with col5:
        st.metric("✅ Transférés", metriques['patients_transferes'])


def afficher_occupation_salles_compact():
    """Affichage compact des salles avec emojis"""
    etat = st.session_state.agent.get_etat_complet()
    
    st.subheader("🏥 Salles d'Attente")
    
    for salle_data in etat['salles']:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Emojis patients
            emojis = []
            for patient in salle_data['patients']:
                emoji_gravite = {
                    "ROUGE": "🔴",
                    "JAUNE": "🟡",
                    "VERT": "🟢",
                    "GRIS": "⚪"
                }.get(patient['gravite'], "❓")
                emojis.append(emoji_gravite)
            
            # Ajouter emojis vides
            for _ in range(salle_data['capacite'] - len(emojis)):
                emojis.append("⬜")
            
            st.markdown(f"**Salle {salle_data['numero']}** ({len(salle_data['patients'])}/{salle_data['capacite']}): {' '.join(emojis)}")
        
        with col2:
            # Barre de progression
            taux = salle_data['taux_occupation']
            color = "red" if taux >= 80 else "orange" if taux >= 60 else "green"
            st.progress(taux / 100, text=f"{taux:.0f}%")


# Dans app_simulation.py

def afficher_personnel_compact():
    """Version améliorée pour voir qui est BUSY ou non"""
    etat = st.session_state.agent.get_etat_complet()
    st.subheader("👥 État du Personnel")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**🩺 Infirmières (Surveillance)**")
        for inf in etat['personnel']['infirmieres']:
            # Utilisation de badges de couleur pour le statut
            color = "green" if inf['statut'] == "DISPONIBLE" else "red"
            st.markdown(f"**{inf['nom']}** : <span style='color:{color}'>{inf['statut']}</span>", unsafe_allow_html=True)
            
    with col2:
        st.write("**🚑 Aides-Soignants (Transport)**")
        for aide in etat['personnel']['aides_soignants']:
            # L'aide-soignant devient orange quand il transporte un patient
            color = "green" if aide['statut'] == "DISPONIBLE" else "orange"
            st.markdown(f"**{aide['nom']}** : <span style='color:{color}'>{aide['statut']}</span>", unsafe_allow_html=True)

    # Note : Le docteur est déjà géré dans votre code par une section spécifique


def afficher_file_attente_compact():
    """File d'attente compacte"""
    etat = st.session_state.agent.get_etat_complet()
    file_attente = etat['file_attente']
    
    st.subheader("📋 File d'Attente Consultation")
    
    if not file_attente:
        st.info("✅ Aucun patient en attente")
        return
    
    for i, patient in enumerate(file_attente[:5]):  # Max 5
        emoji_gravite = {
            "ROUGE": "🔴",
            "JAUNE": "🟡",
            "VERT": "🟢",
            "GRIS": "⚪"
        }.get(patient['gravite'], "❓")
        
        exception = " ⚠️ **>360min!**" if patient.get('exception_360') else ""
        
        st.write(f"{i+1}. {emoji_gravite} **{patient['nom']}** - Priorité {patient['priorite_effective']} ({patient['attente_min']}min){exception}")
    
    if len(file_attente) > 5:
        st.caption(f"... et {len(file_attente) - 5} autres patients")


def afficher_graphique_temps_reel():
    """Graphique saturation en temps réel"""
    # Récupérer logs récents
    logs = st.session_state.rag.charger_logs(limit=100)
    
    if len(logs) < 2:
        st.info("Pas assez de données pour graphique")
        return
    
    # Extraire données
    data = []
    for log in logs:
        if 'metriques_instant' in log:
            data.append({
                'temps': datetime.fromisoformat(log['timestamp']),
                'saturation': log['metriques_instant'].get('taux_saturation', 0),
                'attente': log['metriques_instant'].get('patients_attente', 0)
            })
    
    if not data:
        return
    
    df = pd.DataFrame(data)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['temps'],
        y=df['saturation'],
        name='Saturation (%)',
        mode='lines+markers',
        line=dict(color='red', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['temps'],
        y=df['attente'],
        name='Patients en attente',
        mode='lines+markers',
        line=dict(color='blue', width=2),
        yaxis='y2'
    ))
    
    fig.update_layout(
        title="📈 Évolution Temps Réel",
        xaxis_title="Temps",
        yaxis_title="Saturation (%)",
        yaxis2=dict(
            title="Patients",
            overlaying='y',
            side='right'
        ),
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)


# ========== SIMULATION ==========

# Dans app_simulation.py
def tick_simulation():
    """Un tick de simulation (1 minute simulée)"""
    # Création d'une heure fictive : aujourd'hui à 8h + X minutes simulées
    horloge_virtuelle = datetime.now().replace(hour=8, minute=0) + timedelta(minutes=st.session_state.temps_simule)
    
    st.session_state.temps_simule += 1
    
    # On passe l'horloge virtuelle à l'agent
    actions = st.session_state.agent.cycle_orchestration(temps_virtuel=horloge_virtuelle)
    
    for action in actions:
        ajouter_event_log(action)

# ========== INTERFACE ==========

def main():
    """Application principale"""
    initialiser_session()
    
    # Sidebar contrôles
    with st.sidebar:
        st.title("🏥 Simulation Urgences")
        
        st.divider()
        
        # Contrôles simulation
        st.subheader("🎮 Contrôles")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("▶️ Démarrer", disabled=st.session_state.simulation_running, use_container_width=True):
                st.session_state.simulation_running = True
                ajouter_event_log("🎬 Simulation démarrée")
                st.rerun()
        
        with col2:
            if st.button("⏸️ Pause", use_container_width=True):
                st.session_state.simulation_running = False
                ajouter_event_log("⏸️ Simulation en pause")
                st.rerun()
        
        if st.button("🔄 Réinitialiser", use_container_width=True):
            # Réinitialiser tout
            st.session_state.rag = RAGSysteme()
            st.session_state.agent = AgentOrchestration(st.session_state.rag)
            st.session_state.chatbot = ChatbotOrchestration(st.session_state.rag)
            st.session_state.mcp = MCPTools(st.session_state.rag, st.session_state.agent)
            st.session_state.simulation_running = False
            st.session_state.temps_simule = 0
            st.session_state.events_log = []
            st.rerun()
        
        st.divider()
        
        # Vitesse simulation
        st.subheader("⏱️ Vitesse")
        speed = st.select_slider(
            "1 min simulée =",
            options=["🐌 2 sec", "⚡ 1 sec", "🚀 0.5 sec", "💨 0.2 sec"],
            value="⚡ 1 sec"
        )
        
        if "2 sec" in speed:
            st.session_state.simulation_speed = 2.0
        elif "1 sec" in speed:
            st.session_state.simulation_speed = 1.0
        elif "0.5 sec" in speed:
            st.session_state.simulation_speed = 0.5
        else:
            st.session_state.simulation_speed = 0.2
        
        st.divider()
        
        # Actions rapides
        st.subheader("➕ Actions Rapides")
        
        if st.button("👤 Ajouter 1 Patient", use_container_width=True):
            patient = st.session_state.mcp.generer_patient_aleatoire()
            resultat = st.session_state.agent.accueillir_patient(patient)
            if resultat['success']:
                emoji = {"ROUGE": "🔴", "JAUNE": "🟡", "VERT": "🟢", "GRIS": "⚪"}[patient.gravite.value]
                ajouter_event_log(f"{emoji} {patient.id} accueilli en salle {resultat['salle']}")
            st.rerun()
        
        if st.button("👥 Ajouter 5 Patients", use_container_width=True):
            resultat = st.session_state.mcp.ajouter_patients_masse(5)
            ajouter_event_log(f"➕ {resultat['ajoutes']} patients ajoutés en masse")
            st.rerun()
        
        if st.button("🚨 Scénario Afflux", use_container_width=True):
            resultat = st.session_state.mcp.creer_scenario_afflux()
            ajouter_event_log(f"🚨 Afflux massif: {resultat['patients_generes']} patients!")
            st.rerun()
        
        if st.button("⏱️ Test Exception 360min", use_container_width=True):
            resultat = st.session_state.mcp.creer_scenario_exception_360()
            if resultat['exception_activee']:
                ajouter_event_log("⚠️ Exception 360min activée: VERT passe avant JAUNE!")
            st.rerun()
    
    # Main content
    st.title("🏥 Simulation Temps Réel - Orchestration Urgences")
    
    # Métriques en haut
    afficher_metriques_temps_reel()
    
    st.divider()
    
    # Layout principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Salles et file
        afficher_occupation_salles_compact()
        st.divider()
        afficher_file_attente_compact()
        st.divider()
        afficher_graphique_temps_reel()
    
    with col2:
        # Personnel
        afficher_personnel_compact()
        
        st.divider()
        
        # Log événements
        st.subheader("📋 Log Événements")
        
        if st.session_state.events_log:
            log_container = st.container(height=400)
            with log_container:
                for event in reversed(st.session_state.events_log[-20:]):  # 20 derniers
                    st.text(event)
        else:
            st.info("Aucun événement. Lancez la simulation ▶️")
    
    # Footer info
    st.divider()
    st.caption("🎯 **Cycle Auto:** Consultation → Transfert → Nouvel patient | ⏱️ 1 min simulée = temps réel configurable")
    
    # Auto-tick si simulation active
    if st.session_state.simulation_running:
        time.sleep(st.session_state.simulation_speed)
        tick_simulation()
        st.rerun()


if __name__ == "__main__":
    main()