from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    id: str
    label: str
    group: str
    role: str
    hint: str
    side: str = "supervisor"


COMPONENTS: tuple[Component, ...] = (
    Component("conversation", "Conversazione", "Dialogo", "chat", "Risposte parlate e chat; il sistema sceglie tra veloce e ragionamento."),
    Component("agent", "Agente di sistema", "Dialogo", "deep", "Sceglie ed esegue gli strumenti del sistema operativo."),
    Component("mind", "Memoria e ricordi", "Dialogo", "chat", "Estrae e ordina ciò che Jarvis ricorda di te."),
    Component("presentation", "Impaginazione dei contenuti", "Dialogo", "chat", "Sceglie come mostrare le risposte: testo, passi, tabelle, immagini, modelli 3D."),
    Component("diary", "Diario", "Dialogo", "chat", "Riassunti della giornata."),
    Component("actions", "Azioni rapide", "Dialogo", "chat", "Calcoli e comandi brevi."),
    Component("home_commands", "Comandi domotici", "Casa", "domotico", "Interpreta i comandi per luci, scene e dispositivi."),
    Component("automations", "Automazioni", "Casa", "deep", "Trasforma una frase in una regola automatica."),
    Component("documents", "Documenti", "Servizi", "deep", "Piani e stesura di documenti."),
    Component("skills", "Abilità", "Servizi", "studio", "Generazione di nuove abilità."),
    Component("study", "Studio autonomo", "Servizi", "studio", "Lettura di fonti, esercizi ed esami a riposo."),
    Component("models3d", "Editor modelli 3D", "Servizi", "modello3d", "Disegno di oggetti nell'editor."),
    Component("research", "Ricercatore", "Agenti del Core", "ricercatore", "Ricerche sul web e sintesi di fonti.", "core"),
    Component("domotics", "Domotico", "Agenti del Core", "domotico", "Esecuzione di scene e comandi per la casa.", "core"),
    Component("skill_synthesizer", "Sintetizzatore di strumenti", "Agenti del Core", "studio", "Scrive strumenti dinamici in sandbox.", "core"),
    Component("tool_builder", "Costruttore di strumenti", "Agenti del Core", "studio", "Costruisce strumenti nei piani a grafo.", "core"),
    Component("genera_modello_3d", "Generatore 3D", "Agenti del Core", "modello3d", "Strumento di generazione 3D.", "core"),
    Component("parametric_designer", "Progettista parametrico", "Agenti del Core", "modello3d", "Da richiesta a specifica e file CAD.", "core"),
    Component("agent_self_healing_coder", "Architetto web (coder)", "Agenti del Core", "coder", "Scrive siti e app e li ripara da solo.", "core"),
    Component("analytic_reasoner", "Ragionatore analitico", "Agenti del Core", "deep", "Analisi e ragionamento puro.", "core"),
    Component("home_assistant_agent", "Agente Home Assistant", "Agenti del Core", "domotico", "Controlla i dispositivi tramite Home Assistant.", "core"),
    Component("sysops_agent", "Agente di sistema (Core)", "Agenti del Core", "coder", "Automazione e manutenzione del sistema.", "core"),
    Component("surveillance_agent", "Agente di sorveglianza", "Agenti del Core", "deep", "Interpreta eventi e immagini delle telecamere.", "core"),
    Component("intent_classifier", "Classificatore di intenti", "Cervello cognitivo", "chat", "Capisce cosa vuoi fare prima di instradare.", "core"),
    Component("kernel_planner", "Pianificatore a grafo", "Cervello cognitivo", "deep", "Scompone i compiti complessi in un DAG.", "core"),
    Component("kernel_critic", "Critico finale", "Cervello cognitivo", "deep", "Giudica il risultato prima di consegnarlo.", "core"),
    Component("consensus_security", "Consenso: sicurezza", "Cervello cognitivo", "deep", "Voto con veto sulle operazioni distruttive.", "core"),
    Component("consensus_proportionality", "Consenso: proporzionalità", "Cervello cognitivo", "deep", "Voto sulla necessità dei passi.", "core"),
    Component("consensus_reversibility", "Consenso: reversibilità", "Cervello cognitivo", "deep", "Voto sulla recuperabilità degli errori.", "core"),
)

BY_ID: dict[str, Component] = {c.id: c for c in COMPONENTS}
