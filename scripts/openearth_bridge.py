"""Optional bridge for the real OpenEarthAgent model.

Run this FROM a Python environment where OpenEarthAgent is installed and its tool-server
requirements are satisfied. It mirrors the public OpenEarthAgent app logic at a small API layer.

Example:
  export PYTHONPATH=/path/to/OpenEarthAgent:$PYTHONPATH
  uvicorn scripts.openearth_bridge:app --host 0.0.0.0 --port 8010

The main SatQuery backend then uses OPENEARTHAGENT_URL=http://localhost:8010.
"""
from __future__ import annotations
import json, re, os
from fastapi import FastAPI
from pydantic import BaseModel

app=FastAPI(title='OpenEarthAgent SatQuery Bridge')
_loaded=False
_model=None

class Inp(BaseModel):
    query: str
    image_path: str|None=None

def load():
    global _loaded,_model
    if _loaded: return
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from tool_server.tf_eval.utils.rs_agent_prompt import RS_AGENT_PROMPT
    class Planner:
        def __init__(self):
            self.device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model=AutoModelForCausalLM.from_pretrained('MBZUAI/OpenEarthAgent',dtype=torch.bfloat16,trust_remote_code=True).to(self.device)
            self.tok=AutoTokenizer.from_pretrained('MBZUAI/OpenEarthAgent',use_fast=True,trust_remote_code=True)
            self.prompt=RS_AGENT_PROMPT
        def generate(self,q):
            conv=[{'role':'system','content':self.prompt},{'role':'user','content':q}]
            text=self.tok.apply_chat_template(conv,tokenize=False,add_generation_prompt=True)
            inp=self.tok(text,return_tensors='pt').to(self.device)
            out=self.model.generate(**inp,max_new_tokens=256)
            return self.tok.decode(out[0][inp.input_ids.shape[-1]:],skip_special_tokens=True)
    _model=Planner(); _loaded=True

@app.get('/health')
def health():
    return {'status':'ok','model_loaded':_loaded}

@app.post('/plan')
def plan(inp:Inp):
    load()
    raw=_model.generate(inp.query)
    m=re.search(r'"actions"\s*:\s*(\[.*\])',raw,re.S)
    actions=[]
    if m:
        try: actions=json.loads(m.group(1))
        except Exception: pass
    return {'raw_output':raw,'actions':actions}
