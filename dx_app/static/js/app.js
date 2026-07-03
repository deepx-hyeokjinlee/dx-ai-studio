// DX-APP — App
// Init, boot sequence

// Load Models
// ══════════════════════════════════════════════
async function loadModels(){
  const data=await api('/api/models');
  S.models=Array.isArray(data)?data:[];
}

// ═══════════════════════════════════════════════════════════

// ═══ Launcher PostMessage listener (theme sync) ═══
window.addEventListener('message', function(e) {
  if (!e.data || !e.data.type) return;
  if (e.data.type === 'dx-lang-change') {
    if (window._dxTutorial) window._dxTutorial.refreshLang();
  }
});

window.addEventListener('DOMContentLoaded',init);

