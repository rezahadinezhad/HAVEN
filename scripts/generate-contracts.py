#!/usr/bin/env python3
"""Generate OpenAPI from runtime DRF requests and explicit public response contracts."""
import os,sys,json,re
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'apps/api'));os.environ.setdefault('DJANGO_SETTINGS_MODULE','haven.settings')
import django
django.setup()
from core import serializers as s
from rest_framework import serializers as drf
from haven.urls import urlpatterns

def obj(properties, required=None):
    return {'type':'object','properties':properties,'required':list(properties) if required is None else required,'additionalProperties':False}
S={'type':'string'};B={'type':'boolean'};N={'type':'integer','minimum':0};ID={'type':'string','format':'uuid'}
DATE={'type':['string','null'],'format':'date-time'}
def arr(x):return {'type':'array','items':x}
def ref(name):return {'$ref':'#/components/schemas/'+name}
user=obj({'id':ID,'username':S,'display_name':S,'role':{'enum':['member','community_admin','superadmin']},'security_generation':N,'is_active':B})
device=obj({'id':ID,'user_id':ID,'label':S,'identity':S,'public_key':S,'trust_state':S,'revoked_at':DATE,'challenge':S,'approved_by':{'type':['string','null']},'approval_signature':S})
certificate=obj({k:device['properties'][k] for k in ['id','user_id','identity','public_key']}|{'role':{'enum':['owner','moderator','member']}})
transition=obj({'action':{'enum':['add','remove','update','transfer','role']},'device_id':{'type':['string','null']},'next_epoch':N,'members':arr(ref('Certificate')),'welcome_hash':S,'state_hash':S})
header=obj({'domain':{'const':'haven/envelope/v1'},'v':{'const':1},'conversation_id':ID,'group_id':S,'sender_device':ID,'client_message_id':ID,'epoch':N,'seq':N,'previous_hash':S,'ciphertext_hash':S,'transition':{'oneOf':[ref('Transition'),{'type':'null'}]}})
conv=obj({'id':ID,'kind':{'enum':['direct','group']},'group_id':S,'epoch':N,'last_seq':N,'status':S,'head_hash':S})
genesis=obj({'domain':{'const':'haven/genesis/v1'},'id':ID,'kind':{'enum':['direct','group']},'group_id':S,'members':arr(ref('Certificate'))})
env=obj({'id':ID,'client_message_id':ID,'sender_device':ID,'v':{'const':1},'seq':N,'epoch':N,'kind':{'enum':['application','commit']},'header':ref('DeliveryHeader'),'signature':S,'chain_hash':S,'ciphertext':S,'received_at':DATE,'welcome':S,'transition':ref('Transition')},['id','client_message_id','sender_device','v','seq','epoch','kind','header','signature','chain_hash'])
privacy=obj({'delivered_ciphertext_grace_hours':N,'attachment_days':N,'abandoned_upload_hours':N,'audit_days':N,'cleanup_interval_seconds':N,'unsynced_ciphertext_expires':B,'signed_history_retained':B,'accounts_and_membership_retained':B,'ingress_observes_ip':B,'independent_review':B})
env['properties']['ciphertext_retired']=B
schemas={'User':user,'Device':device,'Certificate':certificate,'Transition':transition,'DeliveryHeader':header,'Conversation':conv,'Genesis':genesis,'Envelope':env,'PrivacyPolicy':privacy}
schemas['InvitationAccess']=obj({'allowed':B,'reason':{'enum':['ready','paused','crypto_unavailable','members_disabled','browser_not_ready','daily_limit','pending_limit']},'remaining_today':{'type':['integer','null'],'minimum':0},'max_hours':N,'resets_at':{'type':'string','format':'date-time'},'pending_invitations':arr(obj({'id':ID,'expires_at':{'type':'string','format':'date-time'}}))})
# Status endpoints deliberately expose only bounded operational metadata.
status={'type':'object','additionalProperties':True}
ok=obj({'ok':B})
requests={'Login':s.Login,'Redeem':s.Redeem,'ChangePassword':s.Password,'Invitations':s.Invite,'Users':s.UserPatch,'EnrollmentRequest':s.Enrollment,'EnrollmentApprove':s.Approval,'EnrollmentComplete':s.Approval,'KeyPackages':s.Package,'Conversations':s.CreateConversation,'Messages':s.Envelope,'CryptoEvents':s.Control,'Acks':s.Ack,'Attachments':s.AttachmentInit,'ViewOnceAttachment':s.AttachmentViewToken,'CloseViewOnceAttachment':s.AttachmentViewToken,'MembersPropose':s.Leave,'RecoveryKey':s.RecoveryKey,'RecoveryStart':s.RecoveryStart,'RecoveryReset':s.RecoveryReset,'DisableAccount':s.DisableAccount,'SystemStatus':s.ServerPolicy}

def field(v):
    if isinstance(v,drf.Serializer):return request_schema(v)
    out={'type':'string'}
    if isinstance(v,drf.IntegerField):out={'type':'integer'}
    elif isinstance(v,drf.BooleanField):out={'type':'boolean'}
    elif isinstance(v,drf.JSONField):out={'type':'object','additionalProperties':True}
    if isinstance(v,drf.ChoiceField):out['enum']=list(v.choices)
    if isinstance(v,drf.UUIDField):out['format']='uuid'
    if isinstance(v,s.Base64):out['contentEncoding']='base64'
    for attr,k in [('max_length','maxLength'),('min_length','minLength'),('min_value','minimum'),('max_value','maximum')]:
        val=getattr(v,attr,None)
        if val is not None:out[k]=val
    return out

def request_schema(serializer):return obj({k:field(v) for k,v in serializer.fields.items()},[k for k,v in serializer.fields.items() if v.required])
requests['FriendInvitations']=s.Invite

def response(name,method,params):
    if name=='FriendInvitations':return ref('InvitationAccess') if method=='get' else obj({'id':ID,'token':S,'expires_at':DATE})
    if name=='PrivacyPolicy':return ref('PrivacyPolicy')
    if name=='Health':return obj({'status':S,'crypto_ready':B,'name':S,'maintenance':S,'release_status':S})
    if name=='CSRF':return obj({'csrf':S})
    if name in ['Login','Redeem','RecoveryReset']:return obj({'user':ref('User'),'crypto_ready':B})
    if name=='Me':return obj({'user':ref('User'),'device_id':{'type':['string','null']},'crypto_ready':B,'recovery_configured':B})
    if name=='Devices':return arr(ref('Device'))
    if name=='PeerDevices':return arr(ref('Device'))
    if name=='EnrollmentRequest':return obj(device['properties']|{'signing_payload':S})
    if name=='EnrollmentComplete':return ref('Device')
    if name=='Users':return ref('User') if params else arr(ref('User'))
    if name=='Invitations':return obj({'id':ID,'token':S,'expires_at':DATE}) if method=='post' else arr(obj({'id':ID,'intended_username':S,'expires_at':DATE,'consumed_at':DATE,'revoked_at':DATE}))
    if name=='KeyPackages':return obj({'device':ref('Device')}) if params and method=='get' else obj({'id':ID,'package':S,'device':ref('Device')}) if params else obj({'id':ID})
    if name=='Conversations':return arr(ref('Conversation')) if method=='get' and not params else obj(conv['properties']|{'genesis':ref('Genesis'),'genesis_signature':S,'members':arr(obj({'device':ref('Device'),'role':S,'valid_from_epoch':N,'leaving':B}))}) if params else ref('Conversation')
    if name in ['Messages','CryptoEvents']:return obj({'messages':arr(ref('Envelope')),'last_seq':N,'head_hash':S}) if method=='get' else obj({'id':ID,'seq':N,'state':{'const':'server_accepted'},'envelope':ref('Envelope')})
    if name=='Proofs':return obj({'proofs':arr(ref('Envelope')),'last_seq':N,'head_hash':S,'genesis':ref('Genesis'),'genesis_signature':S})
    if name=='Acks':return obj({'seq':N,'state':{'const':'recipient_synced'}}) if method=='post' else obj({'cursors':arr(obj({'device_id':ID,'last_acked_seq':N}))})
    if name=='Sync':return obj({'conversations':arr(ref('Conversation')),'strategy':S,'max_page':N})
    if name=='RecoveryStart':return obj({'id':ID,'nonce':S})
    if name=='Attachments':return obj({'id':ID,'status':S},['id'])
    if name=='ViewOnceAttachment':return obj({'state':{'enum':['available','opened','sent']}}) if method=='get' else obj({'expires_at':{'type':'string','format':'date-time'}})
    if name=='Chunk':return {'type':'string','format':'binary'} if method=='get' else obj({'hash':S,'index':N})
    if name in ['SystemStatus','AdminDevices']:return status if name=='SystemStatus' or params else arr(status)
    if name in ['MembersPropose','DisableAccount','RevokeDevice','ChangePassword']:return status
    return ok

paths={}
for pattern in urlpatterns:
    cls=pattern.callback.view_class;name=cls.__name__;route='/'+str(pattern.pattern);params=re.findall(r'<(?:uuid|int):(\w+)>',route);route=re.sub(r'<(?:uuid|int):(\w+)>',r'{\1}',route)
    methods=[m for m in ['get','post','patch','put','delete'] if hasattr(cls,m)]
    if name=='Users':methods=['patch'] if params else ['get']
    if name=='AdminDevices':methods=['post'] if params else ['get']
    if name=='Conversations' and params:methods=['get']
    for method in methods:
        media='application/octet-stream' if name=='Chunk' and method=='get' else 'application/json'
        op={'operationId':f'{name}_{method}_{len(paths)}','security':[] if name in ['Health','CSRF','Login','Redeem','RecoveryStart','RecoveryReset'] else [{'cookieAuth':[]}], 'responses':{str(code):{'description':'Committed success' if code<300 else 'Request rejected; no secret diagnostics','content':{media:{'schema':response(name,method,params) if code<300 else {'type':'object','additionalProperties':True}}}} for code in ([200,201,400,403,404,409,429,503]+([410] if name in ['Messages','CryptoEvents'] and method=='get' else []))}}
        if params:op['parameters']=[{'name':p,'in':'path','required':True,'schema':{'type':'integer' if p=='index' else 'string','minimum':0} if p=='index' else {'type':'string','format':'uuid'}} for p in params]
        if name=='Chunk' and method=='get':op.setdefault('parameters',[]).append({'name':'X-Haven-View-Token','in':'header','required':False,'description':'Temporary, device-bound session capability required for view-once attachments. Never a media decryption key. Never place in a URL.','schema':{'type':'string','pattern':'^[0-9a-f]{64}$'}})
        if method in ['post','patch','put']:
            schema=request_schema(requests[name]()) if name in requests else obj({})
            if name=='KeyPackages' and params:schema=obj({})
            if name=='Chunk':schema={'type':'string','format':'binary'}
            op['requestBody']={'required':True,'content':{'application/octet-stream' if name=='Chunk' else 'application/json':{'schema':schema}}}
        paths.setdefault(route,{})[method]=op
spec={'openapi':'3.1.0','info':{'title':'HAVEN delivery API','version':'0.2.0','description':'Authenticated ciphertext delivery; no server plaintext/crypto keys. See security status for qualification gates.'},'servers':[{'url':'/'}],'components':{'schemas':schemas,'securitySchemes':{'cookieAuth':{'type':'apiKey','in':'cookie','name':'__Host-haven'}}},'paths':paths}
(root/'packages/contracts/openapi.json').write_text(json.dumps(spec,indent=2)+'\n')
(root/'packages/contracts/paths.ts').write_text('// Generated by scripts/generate-contracts.py\nexport type APIPath = '+' | '.join(json.dumps(x) for x in paths)+';\n')
print(f'Generated {len(paths)} paths with request/response contracts')
