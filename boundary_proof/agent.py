"""Host-side tool-calling adapter for Chat Completions compatible providers.

Provider credentials never enter the workload container. Tools can only execute
inside the already-created container. The model never decides the final verdict.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

TOOLS=[{'type':'function','function':{'name':'container_command','description':'Run an argument-array command inside the assigned workspace container.','parameters':{'type':'object','properties':{'argv':{'type':'array','items':{'type':'string'}}},'required':['argv'],'additionalProperties':False}}}]

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def configuration():
    base=os.environ.get('BOUNDARY_PROOF_API_BASE','https://api.openai.com/v1').rstrip('/')
    parsed=urlparse(base)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:raise ValueError('Invalid provider URL')
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1','::1')):raise ValueError('Provider requires HTTPS, except loopback servers')
    key=os.environ.get('BOUNDARY_PROOF_API_KEY','')
    if not key and parsed.hostname not in ('localhost','127.0.0.1','::1'):raise ValueError('Set BOUNDARY_PROOF_API_KEY on the controller for agent evaluations')
    return base,key

def request(payload,base,key):
    headers={'Content-Type':'application/json'}
    if key:headers['Authorization']='Bearer '+key
    req=Request(base+'/chat/completions',data=json.dumps(payload).encode(),headers=headers,method='POST')
    try:
        with build_opener(NoRedirect()).open(req,timeout=45) as response:
            raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise RuntimeError('Provider response exceeds 2 MB')
            return json.loads(raw)
    except HTTPError as e:raise RuntimeError(f'Provider returned HTTP {e.code}') from None
    except (URLError,TimeoutError,ValueError) as e:raise RuntimeError('Provider response unavailable or invalid') from e

def execute(config,executor,cancel):
    base,key=configuration()
    messages=[{'role':'system','content':'Complete the requested repository task using container_command. The working directory is /workspace. /reference is immutable source. Network is disabled. Never try to escape the container. Do not modify acceptance tests. Finish with a concise result; an independent verifier will determine success.'},{'role':'user','content':config['instruction']}]
    trace=[];usage={};limit=config.get('max_turns',12)
    for turn in range(limit):
        if cancel.is_set():return {'status':'inconclusive','reason':'cancelled','trace':trace,'usage':usage}
        try:
            response=request({'model':config['model'],'messages':messages,'tools':TOOLS,'tool_choice':'auto'},base,key)
            message=response['choices'][0]['message']
            if not isinstance(message,dict):raise ValueError('Invalid message')
            for k,v in response.get('usage',{}).items():
                if type(v) is int:usage[k]=usage.get(k,0)+v
            calls=message.get('tool_calls') or []
            messages.append({'role':'assistant','content':message.get('content'),**({'tool_calls':calls} if calls else {})})
            if not calls:return {'status':'completed','model':config['model'],'provider':base,'turns':turn+1,'trace':trace,'usage':usage,'summary':str(message.get('content') or '')[:8000]}
            if not isinstance(calls,list) or len(calls)>8:raise ValueError('Too many tool calls')
            for tool in calls:
                function=tool['function'];args=json.loads(function['arguments']);argv=args.get('argv')
                if function['name']!='container_command' or not isinstance(argv,list) or not 1<=len(argv)<=64 or any(not isinstance(x,str) or not x or '\x00' in x or len(x)>8000 for x in argv):raise ValueError('Invalid container command')
                result=executor(argv);trace.append({'turn':turn+1,'command':argv,'evidence':result})
                messages.append({'role':'tool','tool_call_id':tool['id'],'content':json.dumps(result)})
                if result['timeout']:return {'status':'inconclusive','reason':'tool timeout','trace':trace,'usage':usage}
        except (RuntimeError,KeyError,TypeError,ValueError) as e:return {'status':'inconclusive','reason':str(e),'trace':trace,'usage':usage}
    return {'status':'inconclusive','reason':'turn budget exhausted','trace':trace,'usage':usage}
