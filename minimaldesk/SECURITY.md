# Security model and limitations

MinimalDesk is an experimental attended-support MVP. It has automated security-relevant tests but **has not had an independent security audit**. Do not equate passing tests with production security or regulatory compliance. Use a trusted/private deployment and non-sensitive test machines first.

## Access boundaries

Both endpoints need administrator-issued accounts. Each token contains 256 random bits; the server stores only its SHA-256 hash and compares hashes with `hash_equals`. This is appropriate for high-entropy machine-generated tokens, not for user-chosen passwords. There is no public registration or default credential.

Knowing an account token alone is insufficient to view another computer: a helper also needs that host's one-use invitation secret and explicit local approval. The host verifies an encrypted greeting before presenting approval. A server `active` message by itself cannot start capture or enable input. View-only is enforced by both the relay and the host client. Revocation only reduces privileges; it cannot silently enable control.

## End-to-end message encryption

A fresh 32-byte random secret is generated locally for every host invitation. It is shared out of band and is not sent to PHP. HKDF-SHA256 derives separate host-to-viewer and viewer-to-host keys, salted with the room and connection-pair identifiers.

Each envelope uses AES-256-GCM with a fresh random 12-byte nonce, an authenticated 64-bit increasing sequence number in the plaintext, and associated data containing version, room, pair, direction, and message kind. Replay/reordering and modified ciphertext are rejected. The format is `base64(nonce || ciphertext || tag)`; plaintext begins with the 8-byte sequence number.

This custom protocol uses a standard cryptography library but is **not independently audited**. It has **no forward secrecy**: later disclosure of the invitation secret can expose recorded traffic for that invitation. Random nonces rely on the operating system's secure random generator. Account names are authenticated by the relay, not bound to independently certified human identities. Verify the person through a trusted channel. Never reuse or publish an invitation.

TLS remains mandatory outside loopback: it protects account authentication and connection metadata in transit to the relay. Certificate verification is enabled; there is no insecure-certificate option. Caddy terminates TLS, so its operator can see account authentication traffic. Treat the entire server/proxy host as trusted for account handling.

## Storage, logging, and control

No screenshot history, recording, input log, automatic token storage, or hidden remote service is implemented. Session state and screen/control messages exist in process memory while needed. Secret deletion from Python variables is not guaranteed secure memory erasure. Administrator/OS access to a client, debugger, swap, crash dump, or clipboard may expose secrets/content. The relay logs connection events and account names; deployment network/proxy logs may contain additional metadata.

An approved helper can see private desktop content and can act with the host user's normal desktop privileges. Do not approve strangers. The app cannot prevent a helper from recording the visible display or misusing granted control. No software encryption changes this trust requirement.

Normal stop, focus loss, revocation, and disconnect paths release input held by the application. Sudden process termination, X server failure, or OS failure can prevent cleanup; recover locally. The app does not bypass UAC, secure desktops, lock screens, or host authorization. Native Wayland hosting is unsupported rather than worked around by disabling security.

## Operational limits

Per-connection queues, message sizes, rates, handshake timeouts, peer heartbeats, and session expiry are bounded. These controls are not comprehensive protection against distributed denial of service, a compromised relay, an authorized account exhausting slots, or codec/library vulnerabilities. The custom WebSocket implementation should undergo protocol fuzzing and an independent review before untrusted public deployment.

Run one relay instance as an unprivileged account, keep its data directory private, expose only TLS through a reviewed reverse proxy, and patch dependencies. A 20-client software cap is not a security certification or a measured service-level guarantee. The Docker/systemd deployment examples were reviewed but were not deployed to a public server in the initial validation run.

## Reporting a vulnerability

Do not post live tokens, invitation secrets, desktop content, or exploitable private-machine details in a public issue. Use the repository owner's private reporting channel where available. Report the affected version, a minimal local reproduction on test machines, and expected versus actual behavior. This project makes no promise of a staffed response SLA.
