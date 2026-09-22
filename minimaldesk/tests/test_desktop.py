"""Run with xvfb-run -a python -m pytest. Never inject into a personal desktop."""
import os
import time
from unittest.mock import Mock
import pytest
from minimaldesk.capture import decode_frame, capture_desktop

pytestmark = pytest.mark.skipif(os.environ.get('MINIDESK_TEST_X11') != '1', reason='Opt-in isolated X11/Xvfb tests')


def pump(root, seconds=.1):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        root.update(); time.sleep(.005)


def test_real_x11_capture_input_and_emergency_stop():
    import tkinter as tk
    from minimaldesk.input_control import InputController
    root=tk.Tk();root.geometry('400x250+50+50')
    entry=tk.Entry(root);entry.pack(pady=40)
    root.update();entry.focus_force();pump(root)
    ctl=InputController()
    try:
        w,h,jpeg=capture_desktop()
        img=decode_frame(jpeg)
        assert w>0 and h>0 and img.width<=1280 and img.height<=720
        ctl.enable(True)
        ctl.handle({'op':'key','key':'a','down':True});ctl.handle({'op':'key','key':'a','down':False})
        pump(root)
        assert entry.get()=='a'
        ctl.handle({'op':'move','x':.25,'y':.25})
        assert abs(root.winfo_pointerx()-round(.25*(w-1)))<=1
        for key in ['Control_L','Alt_L','F12']:ctl.handle({'op':'key','key':key,'down':True})
        assert ctl.backend.stop_requested()
        ctl.enable(False)
        assert not ctl.backend.stop_requested()
    finally:
        ctl.close();root.destroy()


def test_tk_app_and_viewer_rendering():
    import tkinter as tk
    from minimaldesk.gui import App,Viewer
    root=tk.Tk();app=App(root)
    try:
        pump(root)
        app.session.peer='test-viewer'
        app.viewer=Viewer(app)
        _,_,jpeg=capture_desktop()
        app.viewer.frame(jpeg);pump(root)
        assert app.viewer.image is not None
        assert app.viewer.photo is not None
    finally:app.close()


def test_full_host_gui_to_viewer_over_php_relay(relay):
    import queue
    import tkinter as tk
    from minimaldesk.gui import App
    from minimaldesk.session import Session
    from minimaldesk.transport import Transport
    root=tk.Tk();app=App(root)
    events=[]
    transport=Transport(relay['url'],'u1',relay['accounts']['u1'])
    viewer=Session(transport.send,lambda t,d:events.append((t,d)))
    transport.start()
    app.server.set(relay['url']);app.username.set('u0');app.token.set(relay['accounts']['u0'])
    app.connect()
    def until(predicate, timeout=5):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            root.update()
            while True:
                try:kind,data=transport.inbox.get_nowait()
                except queue.Empty:break
                if kind=='message':viewer.handle(data)
            for kind,data in list(events):
                if kind=='frame':
                    number,w,h,jpeg=data;decode_frame(jpeg);viewer.ack_frame(number)
                    events.remove((kind,data));events.append(('frame_seen',number))
            viewer.tick()
            if predicate():return
            time.sleep(.005)
        raise AssertionError(f'Timeout: host={app.session.state}, viewer={viewer.state}, status={app.status.get()}')
    try:
        until(lambda:app.session.connected and viewer.connected)
        app.host();until(lambda:app.invite.get().startswith('MD1.'))
        viewer.begin_join(app.invite.get(),True)
        until(lambda:app.session.verified)
        assert app.capture is None and not app.controller.enabled
        app.approve(True)
        until(lambda:viewer.state=='active' and any(t=='frame_seen' for t,d in events))
        target=tk.Toplevel(root);entry=tk.Entry(target);entry.pack();root.update();entry.focus_force()
        viewer.send_input({'op':'key','key':'b','down':True})
        viewer.send_input({'op':'key','key':'b','down':False})
        until(lambda:entry.get()=='b')
        app.session.revoke();until(lambda:not viewer.control)
        assert not app.controller.enabled
        viewer.stop();until(lambda:app.session.state=='idle')
        assert app.controller is None and app.capture is None
    finally:
        app.close();transport.stop();transport.thread.join(timeout=2)
