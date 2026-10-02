import os
import json

HTML_FILE = r"d:\Google Drive (aprilenunzio88@gmail.com)\03_NunzioTech\Software_Creati_Da_Me\Jarvis\installer_wizard\features\brain\admin.html"
JS_FILE = r"d:\Google Drive (aprilenunzio88@gmail.com)\03_NunzioTech\Software_Creati_Da_Me\Jarvis\installer_wizard\features\brain\admin.js"
API_FILE = r"d:\Google Drive (aprilenunzio88@gmail.com)\03_NunzioTech\Software_Creati_Da_Me\Jarvis\server\features\brain\api.py"

html_snippet = """
  <div class="panel" style="margin-top:18px">
    <div class="panel-title">Mappatura Agenti Specializzati</div>
    <div class="muted-note" style="margin-bottom:12px">Assegna un cervello specifico (LLM) a ogni singolo Agente. Se lasciato in bianco, verrà usato il modello predefinito.</div>
    <form id="agent-map-form" class="form-grid" style="grid-template-columns:1fr 1fr">
      <div><label>Agente Ricercatore</label><select id="map-ricercatore" class="agent-map-select"><option value="">-- Predefinito --</option></select></div>
      <div><label>Agente Domotico</label><select id="map-domotico" class="agent-map-select"><option value="">-- Predefinito --</option></select></div>
      <div><label>Studio Autonomo (La Scuola)</label><select id="map-studio" class="agent-map-select"><option value="">-- Predefinito --</option></select></div>
      <div><label>Generatore 3D</label><select id="map-3d" class="agent-map-select"><option value="">-- Predefinito --</option></select></div>
      <div><label>Sviluppatore Web (Architetto)</label><select id="map-coder" class="agent-map-select"><option value="">-- Predefinito --</option></select></div>
    </form>
    <div class="actions" style="margin-top:14px"><button class="btn primary" id="save-agent-map">Salva Mappatura</button></div>
    <div class="faint" id="agent-map-res" style="margin-top:8px"></div>
  </div>
"""

def patch_html():
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "Mappatura Agenti Specializzati" not in content:
        # Inserisci dopo il div class="grid g2 br-lists"
        marker = '</div>\n\n  <div class="panel">\n    <div class="panel-title">Aggiungi cervelli</div>'
        new_content = content.replace(marker, f'</div>\n{html_snippet}\n  <div class="panel">\n    <div class="panel-title">Aggiungi cervelli</div>')
        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("HTML patched")

def patch_js():
    js_snippet = """
  // === AGENT MAPPING LOGIC ===
  async function loadAgentMap() {
    try {
      const res = await fetch('/api/brain/agent_map', { headers: { "Authorization": "Bearer " + localStorage.getItem("token") } });
      if (!res.ok) return;
      const data = await res.json();
      
      const selects = document.querySelectorAll(".agent-map-select");
      
      // Popola le option dei select con i modelli disponibili
      const allModels = window._lastModels || []; // Presupponendo che i modelli siano salvati
      // Facciamo una fetch dei modelli se non ci sono
      const mRes = await fetch('/api/brain/models', { headers: { "Authorization": "Bearer " + localStorage.getItem("token") } });
      const mData = await mRes.json();
      
      let optionsHtml = '<option value="">-- Predefinito --</option>';
      for (const m of mData.models || []) {
        optionsHtml += `<option value="${m.id}">${m.name} (${m.provider})</option>`;
      }
      
      selects.forEach(sel => {
        sel.innerHTML = optionsHtml;
        const mappedAgentId = sel.id.replace("map-", ""); // es. ricercatore
        
        let dbId = mappedAgentId;
        if (dbId === 'studio') dbId = 'skill_synthesizer';
        if (dbId === '3d') dbId = 'genera_modello_3d';
        if (dbId === 'coder') dbId = 'agent_self_healing_coder';
        
        if (data.map && data.map[dbId]) {
           sel.value = data.map[dbId];
        }
      });
    } catch (e) {}
  }
  
  if ($("save-agent-map")) {
      $("save-agent-map").addEventListener("click", async () => {
          $("save-agent-map").disabled = true;
          const map = {};
          document.querySelectorAll(".agent-map-select").forEach(sel => {
              if (sel.value) {
                  let dbId = sel.id.replace("map-", "");
                  if (dbId === 'studio') dbId = 'skill_synthesizer';
                  if (dbId === '3d') dbId = 'genera_modello_3d';
                  if (dbId === 'coder') dbId = 'agent_self_healing_coder';
                  map[dbId] = sel.value;
              }
          });
          
          const res = await fetch('/api/brain/agent_map', {
              method: 'POST',
              headers: { "Content-Type": "application/json", "Authorization": "Bearer " + localStorage.getItem("token") },
              body: JSON.stringify({ map })
          });
          
          if (res.ok) {
              $("agent-map-res").textContent = "✓ Mappatura salvata con successo";
              $("agent-map-res").style.color = "var(--cyan)";
          } else {
              $("agent-map-res").textContent = "Errore durante il salvataggio";
          }
          $("save-agent-map").disabled = false;
          setTimeout(() => { $("agent-map-res").textContent = ""; }, 3000);
      });
      
      // Load map on boot
      loadAgentMap();
  }
"""
    with open(JS_FILE, "a", encoding="utf-8") as f:
        f.write(js_snippet)
    print("JS patched")

def patch_api():
    # Se il file API non esiste in server/features/brain/api.py proverò a crearlo o a fare un bypass
    if not os.path.exists(API_FILE):
        print(f"API file {API_FILE} not found. Needs manual routing.")
        return
        
    with open(API_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        
    if "def get_agent_map" not in content:
        snippet = """
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict

class AgentMapPayload(BaseModel):
    map: Dict[str, str]

@router.get("/agent_map")
async def get_agent_map():
    from server.config.env import settings
    return {"map": settings.AGENT_BRAIN_MAP}

@router.post("/agent_map")
async def save_agent_map(payload: AgentMapPayload):
    from server.config.env import settings
    import json
    
    settings.AGENT_BRAIN_MAP = payload.map
    
    # Salva nel file .env fisico
    lines = []
    with open(".env", "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    with open(".env", "w", encoding="utf-8") as f:
        replaced = False
        for line in lines:
            if line.startswith("AGENT_BRAIN_MAP="):
                f.write(f"AGENT_BRAIN_MAP='{json.dumps(payload.map)}'\\n")
                replaced = True
            else:
                f.write(line)
        if not replaced:
            f.write(f"\\nAGENT_BRAIN_MAP='{json.dumps(payload.map)}'\\n")
            
    return {"status": "ok"}
"""
        with open(API_FILE, "a", encoding="utf-8") as f:
            f.write(snippet)
        print("API patched")

if __name__ == "__main__":
    patch_html()
    try:
        patch_js()
    except Exception as e:
        print(f"JS patch error: {e}")
    try:
        patch_api()
    except Exception as e:
        print(f"API patch error: {e}")
