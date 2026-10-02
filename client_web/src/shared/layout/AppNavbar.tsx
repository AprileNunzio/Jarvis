import React from 'react';
import { NavigationTab } from '../types';
import { Activity, ShieldCheck, Cpu, Terminal, Radio } from 'lucide-react';

interface AppNavbarProps {
  currentTab: NavigationTab;
  onTabChange: (tab: NavigationTab) => void;
  isMeshConnected: boolean;
}

export const AppNavbar: React.FC<AppNavbarProps> = ({ currentTab, onTabChange, isMeshConnected }) => {
  return (
    <header className="sticky top-0 z-50 w-full backdrop-blur-md bg-[#030712]/80 border-b border-cyan-950/60 px-4 lg:px-8 py-3 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-cyan-950/40 border border-cyan-500/40 text-cyan-400 shadow-[0_0_15px_rgba(0,240,255,0.2)]">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-['Rajdhani'] font-bold text-xl tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
                JARVIS CORE
              </span>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                v1.0.0
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              Orchestratore Cognitivo Autonomo
            </p>
          </div>
        </div>

        <nav className="flex items-center space-x-1 sm:space-x-2 bg-slate-900/60 p-1 rounded-xl border border-slate-800">
          <button
            onClick={() => onTabChange('CORE')}
            className={`flex items-center space-x-2 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${
              currentTab === 'CORE'
                ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_12px_rgba(0,240,255,0.15)]'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Activity className="w-4 h-4 text-cyan-400" />
            <span>Visione Core 3D</span>
          </button>
          
          <button
            onClick={() => onTabChange('CONTROL_DECK')}
            className={`flex items-center space-x-2 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${
              currentTab === 'CONTROL_DECK'
                ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-cyan-300 border border-cyan-500/40 shadow-[0_0_12px_rgba(0,240,255,0.15)]'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Terminal className="w-4 h-4 text-blue-400" />
            <span>Pannello di Controllo</span>
          </button>
        </nav>

        <div className="hidden md:flex items-center space-x-4">
          <div className="flex items-center space-x-2 bg-slate-950/60 border border-slate-800 px-3 py-1.5 rounded-lg text-xs font-mono">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-slate-300">Zero-Trust:</span>
            <span className="text-emerald-400">ATTIVO</span>
          </div>

          <div className="flex items-center space-x-2 bg-slate-950/60 border border-slate-800 px-3 py-1.5 rounded-lg text-xs font-mono">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span className="text-slate-300">Rete Mesh:</span>
            <span className={isMeshConnected ? "text-cyan-400" : "text-amber-400"}>
              {isMeshConnected ? "SINCRONIZZATA" : "STANDALONE"}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
