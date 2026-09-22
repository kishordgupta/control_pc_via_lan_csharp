import base64
import json
import os
from unittest.mock import Mock
import pytest
from minimaldesk.crypto import SecureChannel, invitation, parse_invitation
from minimaldesk.validation import validate_input, validate_url, normalize_key
from minimaldesk.input_control import InputController
from minimaldesk.session import Session

ROOM = 'a' * 32
PAIR = 'b' * 32
KEY = bytes(range(32))


def channels():
    return SecureChannel(KEY, ROOM, PAIR, 'host'), SecureChannel(KEY, ROOM, PAIR, 'viewer')


def test_invitation_roundtrip():
    assert parse_invitation(invitation(ROOM, KEY)) == (ROOM, KEY)


@pytest.mark.parametrize('text', ['', 'MD1.x.y', 'MD2.' + ROOM + '.' + 'A'*43, 'MD1.' + ROOM + '.' + 'A'*44, 'MD1.' + ROOM + '.' + 'A'*42 + '!'])
def test_invalid_invite(text):
    with pytest.raises(ValueError):
        parse_invitation(text)


def test_both_directions_and_replay():
    h, v = channels()
    msg = h.seal('frame', b'a frame')
    assert v.open('frame', msg) == b'a frame'
    with pytest.raises(ValueError):
        v.open('frame', msg)
    assert h.open('input', v.seal('input', b'a key')) == b'a key'


@pytest.mark.parametrize('mutation', ['kind', 'key', 'pair', 'role', 'body'])
def test_authenticated_context(mutation):
    h, v = channels()
    body, kind = h.seal('frame', b'content'), 'frame'
    if mutation == 'kind': kind = 'input'
    if mutation == 'key': v = SecureChannel(os.urandom(32), ROOM, PAIR, 'viewer')
    if mutation == 'pair': v = SecureChannel(KEY, ROOM, 'c'*32, 'viewer')
    if mutation == 'role': v = SecureChannel(KEY, ROOM, PAIR, 'host')
    if mutation == 'body':
        raw = bytearray(base64.b64decode(body)); raw[-1] ^= 1
        body = base64.b64encode(raw).decode()
    with pytest.raises(ValueError): v.open(kind, body)


def test_reordered_data_rejected():
    h, v = channels()
    first, second = h.seal('alive', b'1'), h.seal('alive', b'2')
    assert v.open('alive', second) == b'2'
    with pytest.raises(ValueError): v.open('alive', first)


@pytest.mark.parametrize('message', [
    {'op':'move','x':float('nan'),'y':0}, {'op':'move','x':True,'y':0},
    {'op':'move','x':-0.1,'y':0}, {'op':'move','x':1.1,'y':0},
    {'op':'scroll','steps':6}, {'op':'scroll','steps':True},
    {'op':'key','key':'ExecuteAnything','down':True},
    {'op':'key','key':'a','down':1}, {'op':'button','button':'other','down':True},
    {'op':'exec','command':'anything'}, [], None,
])
def test_bad_input(message):
    with pytest.raises(ValueError): validate_input(message)


def test_valid_input_and_keys():
    assert validate_input({'op':'move','x':0.5,'y':1})['x'] == 0.5
    assert normalize_key('A') == 'a'
    assert normalize_key('exclam') == '1'
    assert normalize_key('NotAKey') is None


@pytest.mark.parametrize('url', ['ws://example.com/ws','wss://user:pass@example.com/ws','wss://example.com/','wss://example.com/ws?q=token','https://example.com/ws'])
def test_insecure_urls_rejected(url):
    with pytest.raises(ValueError): validate_url(url)


@pytest.mark.parametrize('url', ['ws://127.0.0.1:8080/ws','ws://[::1]:8080/ws','wss://example.com/ws'])
def test_valid_urls(url):
    assert validate_url(url) == url


def test_input_is_disabled_until_enabled_and_released_on_revoke():
    b = Mock(); c = InputController(b)
    c.handle({'op':'key','key':'a','down':True}); b.key.assert_not_called()
    c.enable(True)
    c.handle({'op':'key','key':'a','down':True})
    c.handle({'op':'button','button':'left','down':True})
    c.enable(False)
    assert ('a', False) in [call.args for call in b.key.call_args_list]
    b.button.assert_any_call('left', False)
    assert not c.keys and not c.buttons
    before = b.key.call_count
    c.handle({'op':'key','key':'b','down':True})
    assert b.key.call_count == before


def paired_sessions(request_control=True):
    hm, vm, he, ve = [], [], [], []
    h = Session(hm.append, lambda t,d: he.append((t,d)))
    v = Session(vm.append, lambda t,d: ve.append((t,d)))
    h.handle({'t':'ready','v':1,'user':'host'})
    v.handle({'t':'ready','v':1,'user':'viewer'})
    h.begin_host(); h.handle({'t':'hosted','room':ROOM})
    code = [d for t,d in he if t == 'invitation'][0]
    v.begin_join(code, request_control)
    h.handle({'t':'paired','pair':PAIR,'peer':'viewer'})
    v.handle({'t':'paired','pair':PAIR,'peer':'host'})
    hello = vm[-1].copy(); hello['pair'] = PAIR; h.handle(hello)
    return h,v,hm,vm,he,ve,code


def activate(h,v,hm,control):
    h.approve(control)
    h.handle({'t':'active','control':control})
    accepted = hm[-1].copy(); accepted['pair']=PAIR; v.handle(accepted)


def test_relay_cannot_bypass_local_consent():
    h,v,hm,vm,he,ve,code = paired_sessions()
    assert h.verified and h.state == 'pending'
    h.handle({'t':'active','control':True})
    v.handle({'t':'active','control':True})
    assert h.state == v.state == 'pending' and not h.approved
    assert not h.send_frame(10,10,b'fake')
    assert not any(t == 'started' for t,d in he)
    assert code.split('.')[-1] not in json.dumps(hm+vm)


def test_approval_frames_ack_and_control_revoke():
    h,v,hm,vm,he,ve,_ = paired_sessions()
    activate(h,v,hm,True)
    assert h.control and v.control and h.state == v.state == 'active'
    assert h.send_frame(100,100,b'JPEG')
    assert not h.send_frame(100,100,b'JPEG')
    frame = hm[-1].copy(); frame['pair']=PAIR; v.handle(frame)
    v.ack_frame(1)
    ack = vm[-1].copy(); ack['pair']=PAIR; h.handle(ack)
    assert h.waiting_frame is None
    v.send_input({'op':'key','key':'a','down':True})
    inp = vm[-1].copy(); inp['pair']=PAIR; h.handle(inp)
    assert any(t == 'input' for t,d in he)
    h.revoke()
    permission = hm[-2].copy(); permission['pair']=PAIR; v.handle(permission)
    assert not h.control and not v.control
    count=len(vm); v.send_input({'op':'key','key':'b','down':True})
    assert len(vm) == count


def test_view_only_even_when_relay_claims_control():
    h,v,hm,vm,he,ve,_ = paired_sessions(False)
    activate(h,v,hm,True)
    assert not h.control and not v.control
    raw = v.channel.seal('input', b'{"op":"key","key":"a","down":true}')
    h.handle({'t':'relay','pair':PAIR,'kind':'input','body':raw})
    assert not any(t=='input' for t,d in he)


def test_approval_requires_verified_secret():
    h = Session(lambda m:None, lambda t,d:None)
    h.connected=True; h.begin_host(); h.handle({'t':'hosted','room':ROOM})
    h.handle({'t':'paired','pair':PAIR,'peer':'viewer'})
    with pytest.raises(ValueError): h.approve(True)
    wrong = SecureChannel(os.urandom(32),ROOM,PAIR,'viewer')
    h.handle({'t':'relay','pair':PAIR,'kind':'hello','body':wrong.seal('hello',b'{}')})
    assert h.state == 'idle' and not h.approved


def test_peer_timeout_stops_and_clears_keys():
    h,v,hm,vm,he,ve,_ = paired_sessions()
    activate(h,v,hm,True)
    h.last_peer -= 16
    h.tick()
    assert h.state == 'idle' and h.secret is None and h.channel is None
    assert hm[-1] == {'t':'stop'}
