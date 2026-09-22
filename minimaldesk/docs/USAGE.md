# Usage guide

## Roles

The **host** is the computer being shared. The **viewer/helper** is the person viewing or controlling it. Both run the same application, choose the same relay URL, and log in with different administrator-issued accounts. One application instance has one role per session.

## Host: request help

Connect, then choose **Share this computer**. The app creates an invitation beginning with `MD1.`. This includes a secret encryption key: share the complete invitation privately with only the person you expect. Never post it publicly.

The invitation lasts five minutes and is consumed by one connection attempt. No image is captured merely by creating it. After the helper joins with the correct key, the host sees the helper's relay account name and whether control was requested.

Check the person through a trusted channel. An account name is not independently verified real-world identity. Choose **Allow view only**, **Allow keyboard + mouse**, or **Deny**. You may approve view-only even when the helper requested control. Approving control is unavailable when it was not requested.

Once approved, a visible always-on-top sharing window appears. The host's invitation field and incoming prompt are cleared before the first screen capture. Close sensitive documents and notifications before approving; the current desktop is shared, not an individual application window.

## Helper: view or control

Paste the invitation under **Help on another computer**. View-only is the default. Select **Request keyboard and mouse control** only when needed, then choose **Join invitation**. Wait for local approval on the host.

The viewer window scales the remote image while preserving its aspect ratio. Click within the image to focus it. When control is approved, the viewer forwards basic keys, mouse clicks, dragging, movement, and vertical scrolling. US-layout keys, common navigation keys, and F1–F12 are supported. International layouts, IMEs, touch gestures, and all OS-reserved shortcuts are not guaranteed.

`Escape` releases local viewer focus and asks the host to release keys/buttons held by this application. The **Release keyboard / mouse** button does the same. Use **Send Escape** to send an actual Escape key to the remote application.

## Stop or reduce access

Either person may select **Stop/End session** or disconnect. Closing the application stops sharing. The host can also press **Ctrl+Alt+F12**, which is checked while a session is active, or select **STOP** in the sharing window.

**Revoke control** immediately releases app-held keys/buttons locally and leaves the session view-only. This session cannot re-enable control; create a new invitation for a new approval. Normal disconnect/error paths release app-held input. Abrupt OS/process failures are not a guarantee of cleanup: physically recover the host when necessary.

## Time limits and reconnection

- Unused invitation: five minutes.
- Approval request: 30 seconds at the server.
- Active session: at most one hour.
- Missing authenticated peer heartbeat: client stops after approximately 15 seconds.
- Unacknowledged screen frame: host stops after approximately 10 seconds.

A new session always needs a fresh invitation and local approval. There is no unattended reconnect, saved permanent password, background service, or automatic startup.

## Capacity and privacy

Twenty logged-in clients means ten fully paired sessions only when all clients are paired. For example, eight pairs plus four idle clients fill all 20 slots. Each client account may connect once. The cap is per deployment and does not apply across separately installed relay servers.

The relay sees account names, room membership, timing, message types, and traffic sizes. Screen and input bodies are encrypted with the invitation secret. The relay does not store screen recordings or input history. The helper can still take screenshots or copy information manually; encryption cannot prevent that after you grant viewing access.
