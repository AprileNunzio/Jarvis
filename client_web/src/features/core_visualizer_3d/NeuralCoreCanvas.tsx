import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Mic, Send, Volume2, Shield, Activity, Zap, BrainCircuit } from 'lucide-react';
import { KnowledgeNode } from '../../shared/types';

interface NeuralCoreCanvasProps {
  onSendCommand: (command: string) => Promise<string>;
  activeNodes: KnowledgeNode[];
}

export const NeuralCoreCanvas: React.FC<NeuralCoreCanvasProps> = ({ onSendCommand, activeNodes }) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [lastSpeechOutput, setLastSpeechOutput] = useState<string>('In attesa di istruzioni. I sistemi periferici e gli agenti sono pronti.');
  
  const [selectedMemory, setSelectedMemory] = useState<KnowledgeNode | null>(null);

  useEffect(() => {
    const currentMount = mountRef.current;
    if (!currentMount) return;

    const width = currentMount.clientWidth;
    const height = currentMount.clientHeight;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
    camera.position.z = 10;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    currentMount.appendChild(renderer.domElement);

    const nodesCount = Math.max(activeNodes.length, 100);
    const positions = new Float32Array(nodesCount * 3);
    const colors = new Float32Array(nodesCount * 3);
    
    for (let i = 0; i < nodesCount; i++) {
        positions[i*3] = (Math.random() - 0.5) * 15;
        positions[i*3+1] = (Math.random() - 0.5) * 15;
        positions[i*3+2] = (Math.random() - 0.5) * 15;

        let r = 0.1, g = 0.2, b = 0.3;

        if (i < activeNodes.length) {
            const type = (activeNodes[i].node_type || '').toUpperCase();
            if (type === 'PERSISTENT' || type === 'LONG_TERM') {
                r = 1.0; g = 0.84; b = 0.0;
            } else if (type === 'ACTIVE' || type === 'RECENT') {
                r = 0.0; g = 1.0; b = 0.2;
            } else if (type === 'ERROR' || type === 'CORRECTION') {
                r = 1.0; g = 0.0; b = 0.2;
            } else {
                r = 0.0; g = 0.8; b = 1.0;
            }
        }

        colors[i*3] = r;
        colors[i*3+1] = g;
        colors[i*3+2] = b;
    }
    
    const nodesGeo = new THREE.BufferGeometry();
    nodesGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    nodesGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    
    const nodesMat = new THREE.PointsMaterial({
        size: 0.25,
        vertexColors: true,
        transparent: true,
        opacity: 0.9,
        blending: THREE.AdditiveBlending
    });
    
    const nodesMesh = new THREE.Points(nodesGeo, nodesMat);
    scene.add(nodesMesh);

    const linesGeo = new THREE.BufferGeometry();
    const linesPositions = [];
    const linesColors = [];
    for (let i = 0; i < nodesCount; i++) {
        for (let j = i + 1; j < nodesCount; j++) {
            const dx = positions[i*3] - positions[j*3];
            const dy = positions[i*3+1] - positions[j*3+1];
            const dz = positions[i*3+2] - positions[j*3+2];
            const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
            if (dist < 3.0) {
                linesPositions.push(
                    positions[i*3], positions[i*3+1], positions[i*3+2],
                    positions[j*3], positions[j*3+1], positions[j*3+2]
                );
                linesColors.push(
                    colors[i*3], colors[i*3+1], colors[i*3+2],
                    colors[j*3], colors[j*3+1], colors[j*3+2]
                );
            }
        }
    }
    linesGeo.setAttribute('position', new THREE.Float32BufferAttribute(linesPositions, 3));
    linesGeo.setAttribute('color', new THREE.Float32BufferAttribute(linesColors, 3));
    const linesMat = new THREE.LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.3,
        blending: THREE.AdditiveBlending
    });
    const linesMesh = new THREE.LineSegments(linesGeo, linesMat);
    scene.add(linesMesh);

    const coreGeo = new THREE.IcosahedronGeometry(2, 2);
    const coreMat = new THREE.MeshBasicMaterial({
        color: 0x0055ff,
        wireframe: true,
        transparent: true,
        opacity: 0.5,
        blending: THREE.AdditiveBlending
    });
    const coreMesh = new THREE.Mesh(coreGeo, coreMat);
    scene.add(coreMesh);

    const raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 0.3;
    const mouse = new THREE.Vector2();

    const onPointerDown = (event: MouseEvent) => {
        const rect = renderer.domElement.getBoundingClientRect();
        mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        raycaster.setFromCamera(mouse, camera);
        const intersects = raycaster.intersectObject(nodesMesh);
        
        if (intersects.length > 0) {
            const index = intersects[0].index;
            if (index !== undefined) {
                if (index < activeNodes.length) {
                    setSelectedMemory(activeNodes[index]);
                } else {
                    setSelectedMemory({
                        id: `sys-node-${index}`,
                        label: "Memoria Latente (Inattiva)",
                        node_type: "LATENT",
                        properties: { info: "Spazio neuronale pronto per l'acquisizione di nuovi ricordi." },
                        created_at: Date.now(),
                        updated_at: Date.now()
                    });
                }
            }
        } else {
            setSelectedMemory(null);
        }
    };

    window.addEventListener('pointerdown', onPointerDown);

    let animationFrameId: number;
    let clock = new THREE.Clock();
    const posAttr = nodesGeo.attributes.position as THREE.BufferAttribute;

    const animate = () => {
      const elapsedTime = clock.getElapsedTime();
      
      coreMesh.rotation.y = elapsedTime * 0.2;
      coreMesh.rotation.x = elapsedTime * 0.1;
      const pulse = 1 + Math.sin(elapsedTime * 4) * 0.05;
      coreMesh.scale.set(pulse, pulse, pulse);

      nodesMesh.rotation.y = elapsedTime * 0.05;
      linesMesh.rotation.y = elapsedTime * 0.05;
      nodesMesh.rotation.x = elapsedTime * 0.02;
      linesMesh.rotation.x = elapsedTime * 0.02;

      for (let i = 0; i < nodesCount; i++) {
          posAttr.setY(i, positions[i*3+1] + Math.sin(elapsedTime * 2 + positions[i*3]) * 0.5);
      }
      posAttr.needsUpdate = true;

      renderer.render(scene, camera);
      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    const handleResize = () => {
      if (!currentMount) return;
      const newWidth = currentMount.clientWidth;
      const newHeight = currentMount.clientHeight;
      camera.aspect = newWidth / newHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(newWidth, newHeight);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('pointerdown', onPointerDown);
      cancelAnimationFrame(animationFrameId);
      if (currentMount.contains(renderer.domElement)) {
        currentMount.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [activeNodes]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isProcessing) return;

    const query = inputText.trim();
    setInputText('');
    setIsProcessing(true);

    const speech = await onSendCommand(query);
    setLastSpeechOutput(speech);
    setIsProcessing(false);
  };

  const toggleVoiceListen = () => {
    setIsListening(prev => !prev);
    if (!isListening) {
      setLastSpeechOutput("In ascolto del comando vocale... Pronuncia 'Jarvis' o impartisci un ordine.");
    }
  };

  return (
    <div className="relative w-full h-[calc(100vh-4.5rem)] flex flex-col justify-between overflow-hidden bg-radial-gradient">
      <div ref={mountRef} className="absolute inset-0 z-0 cursor-crosshair" />

      {selectedMemory && (
          <div className="absolute top-1/4 right-8 z-20 bg-slate-900/90 border border-cyan-400/50 backdrop-blur-xl p-6 rounded-2xl w-80 shadow-[0_0_40px_rgba(0,255,255,0.15)] pointer-events-auto transform transition-all">
              <div className="flex items-center space-x-3 mb-4">
                  <BrainCircuit className="w-6 h-6 text-cyan-400" />
                  <h3 className="text-sm font-mono text-cyan-400 uppercase tracking-widest font-bold">Ispezione Neurone</h3>
              </div>
              <div className="space-y-3">
                  <div>
                      <div className="text-[10px] text-slate-500 uppercase tracking-widest">ID Neurone</div>
                      <div className="text-xs text-slate-300 font-mono truncate">{selectedMemory.id}</div>
                  </div>
                  <div>
                      <div className="text-[10px] text-slate-500 uppercase tracking-widest">Contenuto (Label)</div>
                      <div className="text-sm text-white font-semibold">{selectedMemory.label}</div>
                  </div>
                  <div>
                      <div className="text-[10px] text-slate-500 uppercase tracking-widest">Tipo Memoria</div>
                      <div className="text-xs font-mono px-2 py-0.5 rounded-sm inline-block mt-1 bg-slate-800 text-slate-300">
                          {selectedMemory.node_type}
                      </div>
                  </div>
                  {selectedMemory.properties && Object.keys(selectedMemory.properties).length > 0 && (
                      <div>
                          <div className="text-[10px] text-slate-500 uppercase tracking-widest">Attributi Semantici</div>
                          <pre className="text-[10px] text-cyan-200 mt-1 bg-black/40 p-2 rounded-lg border border-slate-800 overflow-hidden text-ellipsis max-h-32 overflow-y-auto">
                              {JSON.stringify(selectedMemory.properties, null, 2)}
                          </pre>
                      </div>
                  )}
              </div>
              <button 
                  onClick={() => setSelectedMemory(null)}
                  className="mt-5 w-full py-2 bg-slate-800 hover:bg-cyan-900/40 border border-slate-700 hover:border-cyan-400 text-xs text-white rounded-lg transition-colors uppercase tracking-widest"
              >
                  Chiudi Ispezione
              </button>
          </div>
      )}

      <div className="absolute bottom-32 left-8 z-10 bg-slate-950/70 border border-slate-800 backdrop-blur-md p-4 rounded-xl pointer-events-none">
          <h4 className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-2">Legenda Neurale</h4>
          <div className="space-y-2">
              <div className="flex items-center space-x-2"><div className="w-2 h-2 rounded-full bg-[#00ff33] shadow-[0_0_8px_#00ff33]"></div><span className="text-xs text-slate-300">Active (Richiamata)</span></div>
              <div className="flex items-center space-x-2"><div className="w-2 h-2 rounded-full bg-[#ffd700] shadow-[0_0_8px_#ffd700]"></div><span className="text-xs text-slate-300">Persistent (Lungo Termine)</span></div>
              <div className="flex items-center space-x-2"><div className="w-2 h-2 rounded-full bg-[#00ccff] shadow-[0_0_8px_#00ccff]"></div><span className="text-xs text-slate-300">Standard Memory</span></div>
              <div className="flex items-center space-x-2"><div className="w-2 h-2 rounded-full bg-[#ff0033] shadow-[0_0_8px_#ff0033]"></div><span className="text-xs text-slate-300">Error / Correction</span></div>
              <div className="flex items-center space-x-2"><div className="w-2 h-2 rounded-full bg-[#1a334d]"></div><span className="text-xs text-slate-500">Latent / Empty Space</span></div>
          </div>
      </div>

      <div className="relative z-10 p-4 lg:p-8 flex justify-between items-start pointer-events-none">
        <div className="bg-slate-950/70 border border-cyan-900/50 backdrop-blur-md p-4 rounded-2xl max-w-sm pointer-events-auto shadow-2xl">
          <div className="flex items-center space-x-2 text-cyan-400 mb-2">
            <Activity className="w-4 h-4 animate-spin" />
            <h2 className="text-xs font-mono uppercase tracking-widest font-semibold">Stato Orchestratore</h2>
          </div>
          <p className="text-sm font-['Rajdhani'] text-slate-200">
            Nodi cognitivi attivi: <span className="font-bold text-cyan-400 font-mono">{activeNodes.length}</span>
          </p>
          <p className="text-[10px] text-cyan-500/80 uppercase mt-1 tracking-wider">Clicca sui nodi 3D per ispezionare i ricordi</p>
          <div className="flex items-center space-x-2 mt-2 pt-2 border-t border-slate-800 text-[11px] text-slate-400">
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <span>Biometria: Speaker ID Verificato</span>
          </div>
        </div>

        <div className="hidden md:flex flex-col space-y-2 pointer-events-auto">
          <div className="bg-slate-950/70 border border-slate-800 backdrop-blur-md px-3 py-2 rounded-xl text-xs font-mono text-slate-300 flex items-center space-x-2">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Modalità: Multi-Agent Dynamic Routing</span>
          </div>
        </div>
      </div>

      <div className="relative z-10 w-full max-w-3xl mx-auto px-4 pb-6 flex flex-col items-center pointer-events-auto">
        <div className="w-full mb-4 bg-slate-950/80 border border-cyan-500/30 backdrop-blur-lg rounded-2xl p-4 shadow-[0_0_30px_rgba(0,240,255,0.1)]">
          <div className="flex items-start space-x-3">
            <div className="mt-1 flex items-center justify-center w-8 h-8 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Volume2 className="w-4 h-4" />
            </div>
            <div className="flex-1">
              <div className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Risposta Vocale Jarvis</div>
              <p className="text-sm sm:text-base text-slate-200 font-['Rajdhani'] font-medium tracking-wide mt-1">
                "{lastSpeechOutput}"
              </p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="w-full relative flex items-center">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Chiedi qualsiasi cosa a Jarvis o attiva il microfono..."
            className="w-full bg-slate-900/90 border border-cyan-950 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 rounded-2xl py-3.5 pl-4 pr-24 text-sm text-slate-100 placeholder:text-slate-500 backdrop-blur-md outline-none transition-all shadow-xl"
          />
          <div className="absolute right-2 flex items-center space-x-1">
            <button
              type="button"
              onClick={toggleVoiceListen}
              className={`p-2.5 rounded-xl border transition-all ${
                isListening
                  ? 'bg-rose-500/20 border-rose-500 text-rose-400 animate-pulse'
                  : 'bg-slate-800/80 hover:bg-cyan-500/20 border-slate-700 hover:border-cyan-500/50 text-slate-300 hover:text-cyan-400'
              }`}
              title="Attiva ascolto vocale"
            >
              <Mic className="w-4 h-4" />
            </button>
            <button
              type="submit"
              disabled={isProcessing || !inputText.trim()}
              className="p-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-40 text-black font-semibold transition-all shadow-md"
              title="Invia comando"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
