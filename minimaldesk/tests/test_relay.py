import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
import socket
import struct
import subprocess
import time
from contextlib import ExitStack
import pytest
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosed
from minimaldesk.crypto import SecureChannel
from conftest import ROOT


def send(c, data): c.send(json.dumps(data,separators=(',',':')))
def recv(c): return json.loads(c.recv(timeout=3))
def login(r, number, expect='ready'):
    c = connect(r['url'],compression=None,proxy=None,close_timeout=.2)
    send(c,{'t':'auth','v':1,'user':f'u{number}','token':r['accounts'][f'u{number}']})
    m=recv(c)
    assert m['t'] == expect, m
    return c,m


def pair(h,v,control=False):
    send(h,{'t':'host'}); room=recv(h)['room']
    send(v,{'t':'join','room':room}); hp,vp=recv(h),recv(v)
    assert hp['pair'] == vp['pair']
    key=os.urandom(32)
    hc=SecureChannel(key,room,hp['pair'],'host'); vc=SecureChannel(key,room,hp['pair'],'viewer')
    send(v,{'t':'relay','kind':'hello','body':vc.seal('hello',b'{"v":1,"requested_control":true}')})
    m=recv(h); assert hc.open('hello',m['body'])
    send(h,{'t':'approve','control':control})
    assert recv(h)['t']=='active'; assert recv(v)['t']=='active'
    return hc,vc,room


def test_twentieth_accepted_twenty_first_rejected_and_slot_reused(relay):
    with ExitStack() as stack:
        clients=[stack.enter_context(login(relay,i)[0]) for i in range(20)]
        rejected,m=login(relay,20,'error')
        assert m['code']=='server_full'; rejected.close()
        clients[0].close()
        newcomer,m=login(relay,20); stack.enter_context(newcomer)
        assert m['limit']==20


def test_duplicate_account_and_bad_token(relay):
    c,_=login(relay,0)
    try:
        duplicate,m=login(relay,0,'error'); assert m['code']=='already_connected'; duplicate.close()
        with connect(relay['url'],compression=None,proxy=None) as bad:
            send(bad,{'t':'auth','v':1,'user':'u1','token':'A'*43})
            assert recv(bad)['code']=='authentication_failed'
        send(c,{'t':'ping'}); assert recv(c)['t']=='pong'
    finally:c.close()


def test_consent_view_only_directions_and_stop(relay):
    h,_=login(relay,0); v,_=login(relay,1)
    try:
        send(h,{'t':'host'}); room=recv(h)['room']
        send(v,{'t':'join','room':room}); recv(h); recv(v)
        send(h,{'t':'approve','control':True}); assert recv(h)['code']=='invalid_state'
        send(h,{'t':'stop'}); assert recv(h)['t']=='ended'; assert recv(v)['t']=='ended'
        hc,vc,room=pair(h,v,False)
        send(v,{'t':'relay','kind':'input','body':vc.seal('input',b'{}')})
        assert recv(v)['code']=='permission_denied'
        send(v,{'t':'relay','kind':'frame','body':vc.seal('frame',b'data')})
        assert recv(v)['code']=='permission_denied'
        send(h,{'t':'relay','kind':'frame','body':hc.seal('frame',b'a screenshot')})
        assert vc.open('frame',recv(v)['body'])==b'a screenshot'
        send(h,{'t':'stop'}); assert recv(v)['t']=='ended'; assert recv(h)['t']=='ended'
        send(v,{'t':'join','room':room}); assert recv(v)['t']=='error'
    finally:h.close();v.close()


def test_revocation_and_disconnect_cleanup(relay):
    h,_=login(relay,0); v,_=login(relay,1)
    try:
        hc,vc,_=pair(h,v,True)
        send(v,{'t':'relay','kind':'input','body':vc.seal('input',b'{}')})
        assert hc.open('input',recv(h)['body'])==b'{}'
        send(h,{'t':'revoke'}); assert recv(h)['t']=='control_revoked';assert recv(v)['t']=='control_revoked'
        send(v,{'t':'relay','kind':'input','body':vc.seal('input',b'{}')})
        assert recv(v)['code']=='permission_denied'
        v.close(); assert recv(h)['t']=='ended'
        send(h,{'t':'host'}); assert recv(h)['t']=='hosted'
    finally:h.close();v.close()


def test_fragmented_auth_and_websocket_ping(relay):
    with connect(relay['url'],compression=None,proxy=None) as c:
        raw=json.dumps({'t':'auth','v':1,'user':'u0','token':relay['accounts']['u0']})
        c.send([raw[:10],raw[10:30],raw[30:]])
        assert recv(c)['t']=='ready'
        assert c.ping(b'health').wait(2)


def test_live_user_revoke_and_instance_lock(relay):
    h,_=login(relay,0)
    try:
        p=subprocess.run(['php',str(ROOT/'server/relay.php')],env=relay['env'],capture_output=True,text=True,timeout=3)
        assert p.returncode!=0
        p=subprocess.run(['php',str(ROOT/'server/bin/users.php'),'revoke','u0'],env=relay['env'],capture_output=True,text=True,timeout=3)
        assert p.returncode==0, p.stderr
        with pytest.raises(ConnectionClosed): h.recv(timeout=7)
    finally:h.close()


def test_cli_accounts_and_hard_cap_configuration(tmp_path):
    import shutil
    if not shutil.which('php'):pytest.skip('PHP CLI required')
    env=dict(os.environ,MINIDESK_DATA=str(tmp_path))
    p=subprocess.run(['php',str(ROOT/'server/bin/users.php'),'add','alice'],env=env,capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    data=json.loads((tmp_path/'users.json').read_text());assert len(data['alice'])==64
    assert data['alice'] not in p.stdout
    env['MINIDESK_MAX_CLIENTS']='21'
    p=subprocess.run(['php',str(ROOT/'server/relay.php')],env=env,capture_output=True,text=True,timeout=3)
    assert p.returncode!=0


def test_unmasked_client_frame_is_rejected(relay):
    s=socket.create_connection(('127.0.0.1',relay['port']));s.settimeout(3)
    key=base64.b64encode(os.urandom(16)).decode()
    req=f'GET /ws HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'
    s.sendall(req.encode()); assert b'101' in s.recv(4096)
    s.sendall(b'\x81\x02{}')
    close=s.recv(4096); s.close()
    assert close[0]&15==8
    assert struct.unpack('!H',close[2:4])[0]==1002


def test_ten_parallel_pairs_encrypted_payloads(relay):
    """Bounded loopback exercise, not a WAN or real-display performance claim."""
    with ExitStack() as stack:
        clients=[stack.enter_context(login(relay,i)[0]) for i in range(20)]
        pairs=[]
        for i in range(10):
            h,v=clients[2*i:2*i+2];hc,vc,_=pair(h,v)
            pairs.append((h,v,hc,vc))
        def exchange(args):
            h,v,hc,vc=args
            payload=os.urandom(80_000)
            for n in range(12):
                send(h,{'t':'relay','kind':'frame','body':hc.seal('frame',payload)})
                assert vc.open('frame',recv(v)['body'])==payload
                send(v,{'t':'relay','kind':'ack','body':vc.seal('ack',str(n).encode())})
                assert hc.open('ack',recv(h)['body'])==str(n).encode()
                time.sleep(.05)
            return 12
        with ThreadPoolExecutor(max_workers=10) as pool:
            assert sum(pool.map(exchange,pairs))==120


def test_php_wire_boundaries():
    import shutil
    if not shutil.which('php'):pytest.skip('PHP CLI required')
    p=subprocess.run(['php',str(ROOT/'server/tests/wire.php')],capture_output=True,text=True,timeout=5)
    assert p.returncode==0,p.stderr
    assert '19 WebSocket framing checks passed' in p.stdout
