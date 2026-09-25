"""Single health snapshot for the future UI/daemon."""
import os,sys,time,datetime,subprocess
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

def snapshot():
    modules=["agent_os.security_kernel","agent_os.kernel","agent_os.golden_loop","brain","webtools"]
    imports={}
    for m in modules:
        try: __import__(m); imports[m]=True
        except Exception as e: imports[m]=False
    return {"time":C.now_iso(),"imports":imports,"healthy":all(imports.values()),"pid":os.getpid()}
