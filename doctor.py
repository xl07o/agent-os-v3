"""Agent OS Doctor — bounded preflight for unattended operation."""
import os,sys,subprocess,datetime
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

def run(full_tests=False):
    result={"time":C.now_iso(),"compile":False,"tests":None,"health":None}
    try:
        import compileall
        result["compile"]=bool(compileall.compile_dir(C.BASE_DIR,quiet=1,rx=re.compile(r"^(?!data|logs|output).*") if False else None))
    except Exception as e: result["compile_error"]=str(e)
    try:
        from agent_os.health_report import snapshot
        result["health"]=snapshot()
    except Exception as e: result["health"]={"healthy":False,"error":str(e)}
    if full_tests:
        try:
            r=subprocess.run([sys.executable,"-m","pytest","-q","--disable-warnings"],cwd=C.BASE_DIR,shell=False,capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=120)
            result["tests"]={"ok":r.returncode==0,"output":(r.stdout+r.stderr)[-1500:]}
        except subprocess.TimeoutExpired: result["tests"]={"ok":False,"output":"timeout"}
    return result

if __name__=="__main__":
    import json
    print(json.dumps(run("--full" in sys.argv),ensure_ascii=False,indent=2))
