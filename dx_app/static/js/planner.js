// DX-APP — Application Init
// (Planner TCO engine moved to dx_planner/ standalone server)
// ═══════════════════════════════════════════════════════════

async function init(){
  await loadModels();
  nav('models');
  initRunPage();
  initBenchPage();
  initABImages();
  initPipeImages();
  // Pre-load chat models in background so picker is ready when chat opens
  if(typeof _loadChatModels === 'function') setTimeout(_loadChatModels, 500);
  // Image preview modal: click to close
  var ipd=$('modal-imgpreview');
  ipd.addEventListener('click',function(){ipd.close()});
  ipd.addEventListener('cancel',function(e){e.preventDefault();ipd.close()});
  // model search
  $('m-search').addEventListener('input',function(){filterModels()});
}
