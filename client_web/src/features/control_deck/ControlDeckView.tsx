import React, { useState } from 'react';
import { 
  Cpu, 
  Database, 
  Sliders, 
  Terminal, 
  ShieldCheck, 
  Network, 
  Home, 
  Camera, 
  Code2, 
  RefreshCw,
  Server
} from 'lucide-react';
import { AgentDescriptor, SystemModelConfig, KnowledgeNode } from '../../shared/types';

interface ControlDeckViewProps {
  nodes: KnowledgeNode[];
  onRefreshGraph: () => void;
}

export const ControlDeckView: React.FC<ControlDeckViewProps> = ({ nodes, onRefreshGraph }) => {
  const [modelConfig, setModelConfig] = useState<SystemModelConfig>({
    activeProvider: 'OLLAMA',
    ollamaModel: 'qwen2.5-coder:7b',
    temperature: 0.2,
    maxTokens: 4096,
    voiceVolume: 0.9,
    voiceSpeed: 1.0,
  });

  const agents: AgentDescriptor[] = [
    {
      id: 'agent_home_assistant',
      name: 'Agente Domotica (Home Assistant)',
      status: 'IDLE',
      capabilities: ['Luci', 'Clima', 'Tapparelle', 'Sensori Ambientali'],
      latencyMs: 14
    },
    {
      id: 'agent_vision_surveillance',
      name: 'Agente Sicurezza Visiva (Frigate NVR)',
      status: 'EXECUTING',
      capabilities: ['RTSP Stream', 'Riconoscimento Volti', 'Allerta Perimetrale'],
      latencyMs: 28
    },
    {
      id: 'agent_self_healing_coder',
      name: 'Agente Auto-Programmazione & Self-Healing',
      status: 'IDLE',
      capabilities: ['AST Synthesis', 'Sandbox Testing', 'Git Hot-Patch'],
      latencyMs: 110
    }
  ];

  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl sm:text-3xl font-['Rajdhani'] font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-blue-400 to-indigo-400">
          Pannello di Controllo & Centro Cognitivo
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Configurazione dell'orchestratore, allocazione dei modelli e ispezione dei nodi di conoscenza.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur-md">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2.5">
                <Cpu className="w-5 h-5 text-cyan-400" />
                <h2 className="font-['Rajdhani'] text-lg font-semibold text-slate-100">
                  Pool degli Agenti Orchestrati
                </h2>
              </div>
              <span className="text-xs font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-800/60 px-2.5 py-1 rounded-full">
                3 Operativi
              </span>
            </div>

            <div className="space-y-3">
              {agents.map((agent) => (
                <div 
                  key={agent.id}
                  className="bg-slate-950/50 border border-slate-800/80 hover:border-cyan-500/40 p-4 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-all"
                >
                  <div className="flex items-start space-x-3">
                    <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-cyan-400 mt-0.5">
                      {agent.id.includes('home') && <Home className="w-4 h-4" />}
                      {agent.id.includes('vision') && <Camera className="w-4 h-4" />}
                      {agent.id.includes('coder') && <Code2 className="w-4 h-4" />}
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-slate-200">{agent.name}</h3>
                      <div className="flex flex-wrap gap-1.5 mt-1.5">
                        {agent.capabilities.map((cap) => (
                          <span key={cap} className="text-[10px] bg-slate-800/80 text-slate-400 px-2 py-0.5 rounded">
                            {cap}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3 self-end sm:self-center">
                    <span className="text-xs font-mono text-slate-400">{agent.latencyMs}ms</span>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                      agent.status === 'EXECUTING' 
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30 animate-pulse'
                        : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    }`}>
                      {agent.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur-md">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2.5">
                <Database className="w-5 h-5 text-blue-400" />
                <h2 className="font-['Rajdhani'] text-lg font-semibold text-slate-100">
                  Database Nodi & Grafo di Conoscenza Autonomo
                </h2>
              </div>
              <button 
                onClick={onRefreshGraph}
                className="flex items-center space-x-1.5 text-xs text-cyan-400 hover:text-cyan-300 bg-cyan-950/40 hover:bg-cyan-900/40 border border-cyan-800/50 px-3 py-1.5 rounded-lg transition-all"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Aggiorna Nodi</span>
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-64 overflow-y-auto pr-1">
              {nodes.map((node) => (
                <div key={node.id} className="bg-slate-950/60 border border-slate-800 p-3 rounded-xl flex items-start space-x-3">
                  <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                    <Network className="w-4 h-4" />
                  </div>
                  <div className="overflow-hidden">
                    <div className="text-xs font-semibold text-slate-200 truncate">{node.label}</div>
                    <div className="text-[10px] font-mono text-cyan-400 uppercase mt-0.5">{node.node_type}</div>
                    <div className="text-[10px] text-slate-500 font-mono mt-1 truncate">ID: {node.id}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur-md space-y-5">
            <div className="flex items-center space-x-2.5">
              <Sliders className="w-5 h-5 text-indigo-400" />
              <h2 className="font-['Rajdhani'] text-lg font-semibold text-slate-100">
                Impostazioni Modelli & Inferenza
              </h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-mono uppercase text-slate-400 mb-1.5">
                  Provider Primario
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {(['OLLAMA', 'OPENAI', 'ANTHROPIC', 'GEMINI'] as const).map((prov) => (
                    <button
                      key={prov}
                      onClick={() => setModelConfig({ ...modelConfig, activeProvider: prov })}
                      className={`text-xs py-2 px-3 rounded-lg border font-mono transition-all ${
                        modelConfig.activeProvider === prov
                          ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 font-bold'
                          : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      {prov}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono uppercase text-slate-400 mb-1.5">
                  Modello Ollama Locale
                </label>
                <input
                  type="text"
                  value={modelConfig.ollamaModel}
                  onChange={(e) => setModelConfig({ ...modelConfig, ollamaModel: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs font-mono text-slate-200 focus:border-cyan-400 outline-none"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono text-slate-400 mb-1">
                  <span>Temperatura di Risposta</span>
                  <span className="text-cyan-400">{modelConfig.temperature}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={modelConfig.temperature}
                  onChange={(e) => setModelConfig({ ...modelConfig, temperature: parseFloat(e.target.value) })}
                  className="w-full accent-cyan-400 bg-slate-800"
                />
              </div>
            </div>
          </div>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur-md">
            <div className="flex items-center space-x-2.5 mb-3">
              <Terminal className="w-5 h-5 text-emerald-400" />
              <h2 className="font-['Rajdhani'] text-lg font-semibold text-slate-100">
                Sandbox & Self-Healing Log
              </h2>
            </div>
            <div className="bg-black/80 rounded-xl p-3 font-mono text-[11px] text-emerald-400/90 space-y-1 border border-slate-800">
              <div className="text-slate-500">[08:29:12] Sandbox initialized: gVisor/isolate</div>
              <div>[08:30:45] Home Assistant sync: 42 entità ok</div>
              <div>[08:31:02] Self-healing test passed: 0 regressions</div>
              <div className="text-cyan-400">[08:32:10] Jarvis Core: In attesa su porta 8443</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
