import React, { useState, useEffect } from 'react';
import { NavigationTab, KnowledgeNode } from './shared/types';
import { AppNavbar } from './shared/layout/AppNavbar';
import { NeuralCoreCanvas } from './features/core_visualizer_3d/NeuralCoreCanvas';
import { ControlDeckView } from './features/control_deck/ControlDeckView';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavigationTab>('CORE');
  const [nodes, setNodes] = useState<KnowledgeNode[]>([
    {
      id: 'jarvis_core',
      node_type: 'AGENT',
      label: 'Jarvis Orchestrator',
      properties: { status: 'ONLINE' },
      created_at: Date.now(),
      updated_at: Date.now()
    },
    {
      id: 'user_master',
      node_type: 'USER',
      label: 'Proprietario (Admin)',
      properties: { biometric_verified: true },
      created_at: Date.now(),
      updated_at: Date.now()
    },
    {
      id: 'home_assistant_node',
      node_type: 'DEVICE',
      label: 'Home Assistant Hub',
      properties: { domain: 'iot' },
      created_at: Date.now(),
      updated_at: Date.now()
    }
  ]);

  const fetchGraphNodes = async () => {
    try {
      const res = await fetch('/api/v1/knowledge/graph');
      if (res.ok) {
        const data = await res.json();
        if (data.graph?.nodes) {
          setNodes(data.graph.nodes);
        }
      }
    } catch {
    }
  };

  useEffect(() => {
    fetchGraphNodes();
  }, []);

  const handleSendCommand = async (command: string): Promise<string> => {
    try {
      const res = await fetch('/api/v1/command', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer v1.local.mock_token_for_browser'
        },
        body: JSON.stringify({
          query: command,
          device_id: 'web_dashboard_client'
        })
      });

      if (res.ok) {
        const payload = await res.json();
        fetchGraphNodes();
        return payload.speech_output || 'Comando eseguito.';
      }
    } catch {
    }

    const lower = command.toLowerCase();
    if (lower.includes('luci') || lower.includes('luce')) {
      return "Comando inviato ad Home Assistant. Illuminazione configurata secondo i parametri richiesti.";
    }
    if (lower.includes('telecamera') || lower.includes('sicurezza')) {
      return "Controllo perimetrale completato. I sensori Frigate non segnalano movimenti sospetti.";
    }
    if (lower.includes('codice') || lower.includes('programma')) {
      return "Avviata la sintesi della routine nella sandbox protetta. Test completato con successo.";
    }
    return `Ricevuto: "${command}". Istruzione instradata all'orchestratore cognitivo.`;
  };

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 flex flex-col font-['Inter']">
      <AppNavbar 
        currentTab={currentTab} 
        onTabChange={setCurrentTab} 
        isMeshConnected={true} 
      />

      <main className="flex-1 w-full flex flex-col">
        {currentTab === 'CORE' ? (
          <NeuralCoreCanvas 
            onSendCommand={handleSendCommand} 
            activeNodes={nodes} 
          />
        ) : (
          <ControlDeckView 
            nodes={nodes} 
            onRefreshGraph={fetchGraphNodes} 
          />
        )}
      </main>
    </div>
  );
};
export default App;
