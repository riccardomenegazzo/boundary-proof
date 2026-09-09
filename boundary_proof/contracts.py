"""Strict repository contracts. No host commands, paths or Docker flags are accepted."""
import re
from .core import CHECKS

DEFAULT_PROFILES = {
 'permissive': {'user':'0:0','read_only':False,'secret_shared':True,'workspace_writable':True},
 'restricted': {'user':'10001:10001','read_only':True,'secret_shared':False,'workspace_writable':False},
 'balanced': {'user':'10001:10001','read_only':True,'secret_shared':False,'workspace_writable':True},
}

def validate(c):
    if not isinstance(c,dict) or c.get('schema_version')!='2.0': raise ValueError('Expected repository contract schema 2.0')
    allowed={'schema_version','name','owner','objective','workflow','repeats','required_checks','image','steps','verify','profiles','timeout_seconds','artifacts','agent'}
    if set(c)-allowed: raise ValueError('Unknown contract fields: '+', '.join(sorted(set(c)-allowed)))
    for key in ('name','owner','objective','image'):
        if not isinstance(c.get(key),str) or not 1<=len(c[key])<=1000: raise ValueError('Invalid '+key)
    if c['image'].startswith('-') or any(x.isspace() for x in c['image']): raise ValueError('Invalid image reference')
    if c.get('workflow')!='repository': raise ValueError('workflow must be repository')
    if c.get('required_checks')!=list(CHECKS): raise ValueError('All four boundary checks are mandatory')
    for key,default,lo,hi in [('repeats',3,1,20),('timeout_seconds',120,1,900)]:
        value=c.get(key,default)
        if type(value) is not int or not lo<=value<=hi: raise ValueError(f'{key} must be between {lo} and {hi}')
    for key in ('steps','verify'):
        steps=c.get(key)
        if not isinstance(steps,list) or not 1<=len(steps)<=20: raise ValueError(key+' requires 1–20 commands')
        for cmd in steps:
            if not isinstance(cmd,list) or not 1<=len(cmd)<=64 or any(not isinstance(a,str) or not a or '\x00' in a or len(a)>8000 for a in cmd): raise ValueError('Commands must be nonempty argument arrays')
    # Verification code must live in the immutable reference, never in mutable workspace tests.
    for cmd in c['verify']:
        if len(cmd)<2 or cmd[0]!='python' or not cmd[1].startswith('/reference/') or '..' in cmd[1].split('/'):
            raise ValueError('Verification commands must use python /reference/<trusted-script.py>')
    profiles=c.get('profiles')
    if not isinstance(profiles,dict) or not 1<=len(profiles)<=8 or len(profiles)*c.get('repeats',3)>80: raise ValueError('Use 1–8 profiles and at most 80 total trials')
    for name,p in profiles.items():
        if not re.fullmatch('[a-z][a-z0-9_-]{0,39}',name) or not isinstance(p,dict) or set(p)!={'user','read_only','secret_shared','workspace_writable'}: raise ValueError('Invalid profile')
        if p['user'] not in ('0:0','10001:10001') or any(type(p[k]) is not bool for k in ('read_only','secret_shared','workspace_writable')): raise ValueError('Invalid permission value')
    if 'agent' in c:
        agent=c['agent']
        if not isinstance(agent,dict) or set(agent)-{'instruction','model','max_turns'}: raise ValueError('Invalid agent configuration')
        for key in ('instruction','model'):
            if not isinstance(agent.get(key),str) or not 1<=len(agent[key])<=8000:raise ValueError('Agent requires '+key)
        turns=agent.get('max_turns',12)
        if type(turns) is not int or not 1<=turns<=40:raise ValueError('max_turns must be 1–40')
    artifacts=c.get('artifacts',[])
    if not isinstance(artifacts,list) or len(artifacts)>30: raise ValueError('Invalid artifacts')
    for a in artifacts:
        if not isinstance(a,str) or not a or a.startswith('/') or '..' in a.split('/') or '\\' in a or len(a)>250: raise ValueError('Artifacts must be relative workspace paths')
    return c

def starter(name='Repository evaluation'):
    return {'schema_version':'2.0','name':name,'owner':'Platform Engineering','objective':'Complete the repository workflow and pass independent acceptance checks.','workflow':'repository','image':'python:3.12-alpine','repeats':3,'timeout_seconds':120,'required_checks':list(CHECKS),'profiles':DEFAULT_PROFILES,'steps':[['python','-m','compileall','-q','.']],'verify':[['python','/reference/boundary_verify.py']],'artifacts':[]}
