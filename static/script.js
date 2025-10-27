const baseURL = "https://mte-backend-v2.onrender.com";

document.addEventListener("DOMContentLoaded", () => {
  const moduleInput = document.getElementById("moduleInput");
  const modelInput = document.getElementById("modelInput");
  const variantInput = document.getElementById("variantInput");
  const moduleList = document.getElementById("moduleList");
  const modelList = document.getElementById("modelList");
  const variantList = document.getElementById("variantList");
  const chipsContainer = document.getElementById("chips");
  const calculateBtn = document.getElementById("calculateBtn");
  const clearBtn = document.getElementById("clearBtn");
  const mteDisplay = document.getElementById("mteDisplay");
  const loadingText = document.getElementById("loading");

  let modules=[], models=[], variants=[], selectedChips=[];

  function showList(listEl, items, filter='') {
    listEl.innerHTML = "";
    items.forEach(item=>{
      const div=document.createElement("div");
      const regex=new RegExp(`(${filter})`,"gi");
      div.innerHTML=filter?item.replace(regex,"<mark>$1</mark>"):item;
      listEl.appendChild(div);
    });
    listEl.style.display=items.length?"block":"none";
  }

  function hideAllLists(){
    moduleList.style.display="none";
    modelList.style.display="none";
    variantList.style.display="none";
  }

  function renderChips(){
    chipsContainer.innerHTML="";
    selectedChips.forEach((chip,index)=>{
      const div=document.createElement("div");
      div.className="chip";
      div.innerHTML=`${chip.module} > ${chip.model} > ${chip.variant} <span data-index="${index}">&times;</span>`;
      chipsContainer.appendChild(div);

      // Swipe to remove
      let startX=null;
      div.addEventListener("touchstart", e=>{ startX=e.touches[0].clientX; });
      div.addEventListener("touchmove", e=>{
        if(startX!==null){
          let diffX=e.touches[0].clientX-startX;
          div.style.transform=`translateX(${diffX}px)`;
        }
      });
      div.addEventListener("touchend", e=>{
        if(startX!==null){
          let diffX=e.changedTouches[0].clientX-startX;
          if(diffX>100){
            div.style.animation="swipeOut 0.3s forwards";
            setTimeout(()=>{
              selectedChips.splice(index,1);
              renderChips();
            },300);
          } else { div.style.transform="translateX(0)"; }
          startX=null;
        }
      });
    });
  }

  async function loadModules(){
    try{ const res=await fetch(`${baseURL}/modules`); modules=await res.json(); }
    catch(err){ console.error(err); }
  }
  loadModules();

  // MODULE
  moduleInput.addEventListener("input", ()=>{
    const filter=moduleInput.value.toLowerCase();
    const filtered=modules.filter(m=>m.toLowerCase().includes(filter));
    showList(moduleList, filtered, filter);
  });
  moduleList.addEventListener("click", async e=>{
    if(e.target.tagName==="DIV"){
      moduleInput.value=e.target.textContent.replace(/<mark>|<\/mark>/g,"");
      hideAllLists();
      modelInput.disabled=false; modelInput.value="";
      variantInput.disabled=true; variantInput.value="";
      try{
        const res=await fetch(`${baseURL}/models/${encodeURIComponent(moduleInput.value)}`);
        models=await res.json();
      }catch(err){ console.error(err);}
    }
  });

  // MODEL
  modelInput.addEventListener("input", ()=>{
    const filter=modelInput.value.toLowerCase();
    const modelNames=models.map(m=>typeof m==='string'?m:m.model_name);
    const filtered=modelNames.filter(m=>m.toLowerCase().includes(filter));
    showList(modelList, filtered, filter);
  });
  modelList.addEventListener("click", async e=>{
    if(e.target.tagName==="DIV"){
      modelInput.value=e.target.textContent.replace(/<mark>|<\/mark>/g,"");
      hideAllLists();
      variantInput.disabled=false; variantInput.value="";
      try{
        const res=await fetch(`${baseURL}/variants/${encodeURIComponent(modelInput.value)}`);
        variants=await res.json();
      }catch(err){ console.error(err);}
    }
  });

  // VARIANT
  variantInput.addEventListener("input", ()=>{
    const filter=variantInput.value.toLowerCase();
    const variantNames=variants.map(v=>typeof v==='string'?v:v.variant_name);
    const filtered=variantNames.filter(v=>v.toLowerCase().includes(filter));
    showList(variantList, filtered, filter);
  });
  variantList.addEventListener("click", e=>{
    if(e.target.tagName==="DIV"){
      const variantName=e.target.textContent.replace(/<mark>|<\/mark>/g,"");
      if(!selectedChips.find(c=>c.module===moduleInput.value && c.model===modelInput.value && c.variant===variantName)){
        selectedChips.push({module:moduleInput.value, model:modelInput.value, variant:variantName});
        renderChips();
      }
      variantInput.value="";
      variantList.style.display="none";
    }
  });

  // REMOVE CHIP BY CLICK
  chipsContainer.addEventListener("click", e=>{
    if(e.target.tagName==="SPAN"){
      const idx=e.target.dataset.index;
      selectedChips.splice(idx,1);
      renderChips();
    }
  });

  // CALCULATE MTE BUTTON
  async function calculateMTE(){
    if(!selectedChips.length){ mteDisplay.innerText="Overall MTE: 0"; return; }
    loadingText.style.display="flex"; mteDisplay.innerText="";
    const variantsList=selectedChips.map(c=>c.variant);
    try{
      const res=await fetch(`${baseURL}/calculate_mte`,{
        method:"POST",
        headers:{"Content-Type":"application/json; charset=utf-8"},
        body:JSON.stringify({variants:variantsList})
      });
      const data=await res.json();
      mteDisplay.innerText=`Overall MTE: ${data.overall_mte}`;
    }catch(err){
      console.error(err);
      mteDisplay.innerText="Error calculating MTE";
    }finally{ loadingText.style.display="none"; }
  }
  calculateBtn.addEventListener("click", calculateMTE);

  // CLEAR ALL
  clearBtn.addEventListener("click", ()=>{
    moduleInput.value="";
    modelInput.value="";
    variantInput.value="";
    modelInput.disabled=true;
    variantInput.disabled=true;
    selectedChips=[];
    renderChips();
    mteDisplay.innerText="Overall MTE: 0";
    hideAllLists();
    loadingText.style.display="none";
  });

  // CLICK OUTSIDE DROPDOWN
  document.addEventListener("click", e=>{
    if(!e.target.classList.contains("dropdown")) hideAllLists();
  });
});
















