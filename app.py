"""
Application Streamlit - Orchestration des Urgences
Orchestre RAG + Chatbot + Agent + MCP
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Imports modules
from rag_systeme import RAGSysteme
from chatbot import ChatbotOrchestration, QUESTIONS_SUGGEREES
from agent import AgentOrchestration, Patient, Gravite
from mcp_tools import MCPTools


# ========== CONFIGURATION ==========

st.set_page_config(
    page_title="🏥 Orchestration Urgences",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ========== SESSION STATE ==========

def initialiser_session():
    """Initialise session state avec 1 RAG partagé"""
    if 'rag' not in st.session_state:
        st.session_state.rag = RAGSysteme()
        st.session_state.agent = AgentOrchestration(st.session_state.rag)
        st.session_state.chatbot = ChatbotOrchestration(st.session_state.rag)
        st.session_state.mcp = MCPTools(st.session_state.rag, st.session_state.agent)
        st.session_state.initialized = True


# ========== VISUALISATIONS ==========

def afficher_metriques_temps_reel(metriques):
    """Métriques en haut de page"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📊 Taux Saturation",
            f"{metriques['taux_saturation']}%",
            delta=None
        )
    
    with col2:
        st.metric(
            "⏳ En Attente",
            metriques['patients_attente']
        )
    
    with col3:
        st.metric(
            "👨‍⚕️ En Consultation",
            metriques['patients_consultation']
        )
    
    with col4:
        st.metric(
            "✅ Transférés",
            metriques['patients_transferes']
        )


def afficher_occupation_salles(salles):
    """Graphique occupation salles"""
    df = pd.DataFrame([
        {
            "Salle": f"Salle {s['numero']}",
            "Occupation": s['occupation'],
            "Capacité": s['capacite'],
            "Taux": s['taux_occupation']
        }
        for s in salles
    ])
    
    fig = go.Figure()
    
    # Barres occupation
    fig.add_trace(go.Bar(
        x=df["Salle"],
        y=df["Occupation"],
        name="Occupation",
        marker_color='lightblue'
    ))
    
    # Ligne capacité
    fig.add_trace(go.Scatter(
        x=df["Salle"],
        y=df["Capacité"],
        name="Capacité Max",
        mode='lines+markers',
        line=dict(color='red', dash='dash')
    ))
    
    fig.update_layout(
        title="Occupation des Salles d'Attente",
        xaxis_title="Salle",
        yaxis_title="Patients",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def afficher_qui_fait_quoi(etat):
    """Tableau qui fait quoi"""
    st.subheader("👥 Qui fait quoi?")
    
    # Docteur
    if etat['docteur']['disponible']:
        st.success("👨‍⚕️ **Docteur:** Disponible")
    else:
        patient = etat['docteur']['patient_actuel']
        st.warning(f"👨‍⚕️ **Docteur:** En consultation avec {patient}")
    
    # Infirmières
    st.write("**Infirmières:**")
    for inf in etat['personnel']['infirmieres']:
        emoji = "🟢" if inf['statut'] == "DISPONIBLE" else "🔴"
        st.write(f"{emoji} {inf['nom']} ({inf['type']}) - {inf['statut']}")
    
    # Aides-soignants
    st.write("**Aides-soignants:**")
    for aide in etat['personnel']['aides_soignants']:
        emoji = "🟢" if aide['statut'] == "DISPONIBLE" else "🔴"
        st.write(f"{emoji} {aide['nom']} ({aide['type']}) - {aide['statut']}")


def afficher_file_attente(file_attente):
    """File d'attente avec priorités"""
    st.subheader("📋 File d'Attente")
    
    if not file_attente:
        st.info("Aucun patient en attente")
        return
    
    for patient in file_attente:
        emoji_gravite = {
            "ROUGE": "🔴",
            "JAUNE": "🟡",
            "VERT": "🟢",
            "GRIS": "⚪"
        }.get(patient['gravite'], "❓")
        
        exception = " ⚠️ **EXCEPTION 360MIN**" if patient.get('exception_360') else ""
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.write(f"{emoji_gravite} **{patient['nom']}** ({patient['gravite']}){exception}")
        with col2:
            st.write(f"Priorité: **{patient['priorite_effective']}**")
        with col3:
            st.write(f"Attente: {patient['attente_min']}min")


def afficher_graphique_arima(mcp):
    """Graphique prédiction ARIMA"""
    st.subheader("📈 Analyse Flux 24h (pour ARIMA)")
    
    try:
        analyse = mcp.analyser_flux_24h()
        series = analyse["series_temporelles"]["taux_saturation_par_heure"]
        
        if not series:
            st.info("Pas assez de données pour analyse")
            return
        
        df = pd.DataFrame(series)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df["heure"],
            y=df["taux"],
            name="Taux Saturation",
            mode='lines+markers',
            line=dict(color='blue')
        ))
        
        fig.update_layout(
            title="Évolution Saturation (24h)",
            xaxis_title="Heure",
            yaxis_title="Taux Saturation (%)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Saturation Moyenne", f"{analyse['saturation']['moyenne']}%")
        with col2:
            st.metric("Saturation Max", f"{analyse['saturation']['max']}%")
        with col3:
            st.metric("Total Arrivées", analyse['flux']['total_arrivees'])
        
    except Exception as e:
        st.error(f"Erreur analyse: {e}")


# ========== MODES ==========

def mode_dashboard():
    """Mode Dashboard - Visualisation temps réel"""
    st.title("📊 Dashboard Temps Réel")
    
    # Obtenir état
    etat = st.session_state.agent.get_etat_complet()
    
    # Métriques en haut
    afficher_metriques_temps_reel(etat['metriques'])
    
    st.divider()
    
    # Deux colonnes
    col1, col2 = st.columns(2)
    
    with col1:
        afficher_occupation_salles(etat['salles'])
        afficher_file_attente(etat['file_attente'])
    
    with col2:
        afficher_qui_fait_quoi(etat)
        
        st.divider()
        
        # Unités de transfert
        st.subheader("🏥 Unités de Transfert")
        for unite in etat['unites']:
            disponible = "✅" if unite['disponible'] else "❌"
            st.write(f"{disponible} **{unite['nom']}**: {unite['occupation']}/{unite['capacite']}")
    
    # Graphique ARIMA en bas
    st.divider()
    afficher_graphique_arima(st.session_state.mcp)
    
    # Auto-refresh
    if st.button("🔄 Rafraîchir"):
        st.rerun()


def mode_chatbot():
    """Mode Chatbot - Interface questions"""
    st.title("💬 Chatbot Intelligent")
    
    st.write("Posez des questions sur les règles, l'état du système, ou l'historique.")
    
    # Questions suggérées
    st.subheader("💡 Questions suggérées")
    cols = st.columns(2)
    for i, question in enumerate(QUESTIONS_SUGGEREES):
        with cols[i % 2]:
            if st.button(question, key=f"suggest_{i}"):
                st.session_state.question_selected = question
    
    st.divider()
    
    # Input utilisateur
    question = st.text_input(
        "Votre question:",
        value=st.session_state.get('question_selected', ''),
        key="question_input"
    )
    
    if st.button("Envoyer", type="primary") or question:
        if question:
            with st.spinner("Réflexion..."):
                etat = st.session_state.agent.get_etat_complet()
                reponse = st.session_state.chatbot.repondre(
                    question,
                    contexte_etat=etat
                )
            
            st.markdown("**Réponse:**")
            st.markdown(reponse)
            
            # Reset selected
            if 'question_selected' in st.session_state:
                del st.session_state.question_selected
    
    st.divider()
    
    # Statistiques chatbot
    with st.expander("📊 Statistiques"):
        stats = st.session_state.chatbot.get_statistiques()
        for key, value in stats.items():
            st.metric(key.replace('_', ' ').title(), value)


def mode_simulation():
    """Mode Simulation - Actions et scénarios"""
    st.title("🎮 Simulation Interactive")
    
    # Actions manuelles
    st.subheader("➕ Ajouter Patient")
    
    col1, col2 = st.columns(2)
    
    with col1:
        prenom = st.text_input("Prénom", "Jean")
        nom = st.text_input("Nom", "Dupont")
        gravite_str = st.selectbox("Gravité", ["ROUGE", "JAUNE", "VERT", "GRIS"])
    
    with col2:
        maladie = st.text_input("Type maladie", "fracture")
        attente_heures = st.number_input("Heures d'attente (simulation)", 0, 24, 0)
    
    if st.button("Accueillir Patient", type="primary"):
        patient = Patient(
            id=f"P{datetime.now().strftime('%H%M%S')}",
            prenom=prenom,
            nom=nom,
            gravite=Gravite[gravite_str],
            type_maladie=[maladie],
            heure_arrivee=datetime.now() - timedelta(hours=attente_heures)
        )
        
        resultat = st.session_state.agent.accueillir_patient(patient)
        
        if resultat["success"]:
            st.success(f"✅ {resultat['message']}")
        else:
            st.error(f"❌ {resultat['message']}")
    
    st.divider()
    
    # Scénarios prédéfinis
    st.subheader("🎬 Scénarios Prédéfinis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🚨 Afflux Massif", use_container_width=True):
            with st.spinner("Génération scénario..."):
                resultat = st.session_state.mcp.creer_scenario_afflux()
            st.success(f"✅ {resultat['patients_generes']} patients générés")
            st.json(resultat['metriques_apres'])
    
    with col2:
        if st.button("⏱️ Exception 360min", use_container_width=True):
            with st.spinner("Génération scénario..."):
                resultat = st.session_state.mcp.creer_scenario_exception_360()
            if resultat['exception_activee']:
                st.success("✅ Exception activée: VERT passe avant JAUNE")
            st.json(resultat)
    
    with col3:
        if st.button("📊 Saturation", use_container_width=True):
            with st.spinner("Génération scénario..."):
                resultat = st.session_state.mcp.creer_scenario_saturation()
            st.success(f"✅ Saturation: {resultat['taux_saturation_final']}%")
            st.json(resultat)
    
    st.divider()
    
    # Patients en masse
    st.subheader("➕ Ajouter Patients en Masse")
    
    nombre = st.number_input("Nombre de patients", 1, 50, 5)
    
    if st.button("Générer", type="secondary"):
        with st.spinner(f"Génération de {nombre} patients..."):
            resultat = st.session_state.mcp.ajouter_patients_masse(nombre)
        
        st.success(f"✅ {resultat['ajoutes']} patients ajoutés")
        if resultat['refuses'] > 0:
            st.warning(f"⚠️ {resultat['refuses']} patients refusés (salles pleines)")
        st.metric("Saturation", f"{resultat['taux_saturation_apres']}%")
    
    st.divider()
    
    # Cycle orchestration
    st.subheader("🔄 Cycle d'Orchestration")
    
    if st.button("Exécuter Cycle", type="primary", use_container_width=True):
        with st.spinner("Exécution cycle..."):
            actions = st.session_state.agent.cycle_orchestration()
        
        st.write("**Actions effectuées:**")
        for action in actions:
            st.write(f"- {action}")


# ========== MAIN ==========

def main():
    """Application principale"""
    # Initialiser
    initialiser_session()
    
    # Sidebar
    with st.sidebar:
        st.title("🏥 Orchestration Urgences")
        
        st.write("**Architecture Modulaire:**")
        st.write("✅ RAG (règles JSON)")
        st.write("✅ Chatbot (questions)")
        st.write("✅ Agent (orchestration)")
        st.write("✅ MCP (outils)")
        
        st.divider()
        
        # Sélection mode
        mode = st.radio(
            "Mode",
            ["📊 Dashboard", "💬 Chatbot", "🎮 Simulation"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # Stats rapides
        st.write("**État Actuel:**")
        metriques = st.session_state.agent._calculer_metriques_instant()
        st.metric("Saturation", f"{metriques['taux_saturation']}%")
        st.metric("En attente", metriques['patients_attente'])
        
        st.divider()
        
        # Info
        st.caption("🔄 Les données se mettent à jour à chaque action")
    
    # Afficher mode sélectionné
    if mode == "📊 Dashboard":
        mode_dashboard()
    elif mode == "💬 Chatbot":
        mode_chatbot()
    elif mode == "🎮 Simulation":
        mode_simulation()


if __name__ == "__main__":
    main()