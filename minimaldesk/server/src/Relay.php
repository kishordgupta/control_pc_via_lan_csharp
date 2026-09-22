<?php
declare(strict_types=1);
namespace MinimalDesk;
require_once __DIR__ . '/Wire.php';

final class Peer
{
    public string $in = '', $out = '', $fragment = '';
    public ?int $fragmentOp = null;
    public bool $upgraded = false, $closing = false;
    public ?string $user = null, $tokenHash = null, $room = null;
    public float $born, $seen, $closeAt = 0, $budgetAt;
    public float $budget = 4194304;
    public int $messageSecond = 0, $messages = 0;
    public function __construct(public mixed $socket, public int $id)
    {
        $this->born = $this->seen = $this->budgetAt = microtime(true);
    }
}

/** One event loop owns every slot and room: never run multiple relay replicas. */
final class Relay
{
    /** @var array<int,Peer> */
    private array $peers = [];
    private array $rooms = [];
    private bool $running = true;
    private float $lastSweep = 0, $lastUsers = 0;
    private int $acceptWindow = 0, $acceptCount = 0;
    public function __construct(private string $listen, private string $usersFile, private int $limit = 20)
    {
        if ($limit < 1 || $limit > 20) throw new \InvalidArgumentException('Client limit must be 1..20');
    }

    public function run(): void
    {
        $server = @stream_socket_server('tcp://' . $this->listen, $errno, $error);
        if (!$server) throw new \RuntimeException("Cannot listen: $error ($errno)");
        stream_set_blocking($server, false);
        if (function_exists('pcntl_async_signals')) {
            pcntl_async_signals(true);
            pcntl_signal(SIGTERM, fn() => $this->running = false);
            pcntl_signal(SIGINT, fn() => $this->running = false);
        }
        $this->audit('started');
        while ($this->running) {
            $this->sweep();
            $read = [$server]; $write = []; $except = null;
            foreach ($this->peers as $p) {
                if (!$p->closing) $read[] = $p->socket;
                if ($p->out !== '') $write[] = $p->socket;
            }
            if (@stream_select($read, $write, $except, 0, 100000) === false) continue;
            foreach ($read as $sock) {
                if ($sock === $server) { $this->accept($server); continue; }
                $id = (int)$sock;
                if (isset($this->peers[$id])) $this->read($this->peers[$id]);
            }
            foreach ($write as $sock) {
                $id = (int)$sock;
                if (!isset($this->peers[$id])) continue;
                $p = $this->peers[$id];
                $n = @fwrite($sock, substr($p->out, 0, 65536));
                if ($n === false) { $this->drop($id); continue; }
                $p->out = substr($p->out, $n);
                if ($p->closing && $p->out === '') $this->drop($id);
            }
        }
        foreach (array_keys($this->peers) as $id) $this->drop($id);
        fclose($server);
    }

    private function accept(mixed $server): void
    {
        $sock = @stream_socket_accept($server, 0);
        if (!$sock) return;
        $window = intdiv(time(), 60);
        if ($this->acceptWindow !== $window) { $this->acceptWindow = $window; $this->acceptCount = 0; }
        if (count($this->peers) >= 48 || ++$this->acceptCount > 240) { fclose($sock); return; }
        stream_set_blocking($sock, false);
        stream_set_write_buffer($sock, 0);
        $id = (int)$sock;
        $this->peers[$id] = new Peer($sock, $id);
    }

    private function read(Peer $p): void
    {
        $chunk = @fread($p->socket, 65536);
        if ($chunk === false || ($chunk === '' && feof($p->socket))) { $this->drop($p->id); return; }
        $now = microtime(true);
        $p->budget = min(4194304, $p->budget + ($now - $p->budgetAt) * 2097152) - strlen($chunk);
        $p->budgetAt = $p->seen = $now;
        if ($p->budget < 0) { $this->close($p, 1008, 'Rate limit'); return; }
        $p->in .= $chunk;
        if (strlen($p->in) > Wire::LIMIT * 2) { $this->close($p, 1009, 'Too large'); return; }
        try {
            if (!$p->upgraded && !$this->handshake($p)) return;
            $steps = 0;
            while (!$p->closing && ($frame = Wire::pop($p->in)) !== null) {
                if (++$steps > 256) throw new ProtocolError('Too many frames');
                $op = $frame['op']; $data = $frame['data'];
                if ($op === 8) {
                    if (strlen($data) === 1) throw new ProtocolError('Invalid close');
                    if (strlen($data) >= 2) {
                        $code = unpack('n', substr($data,0,2))[1];
                        if (!($code >= 3000 && $code <= 4999) && !in_array($code,[1000,1001,1002,1003,1007,1008,1009,1010,1011,1012,1013,1014],true)) {
                            throw new ProtocolError('Invalid close code');
                        }
                        if (!preg_match('//u',substr($data,2))) throw new ProtocolError('Invalid close text');
                    }
                    $this->close($p); return;
                }
                if ($op === 9) { $this->queue($p, Wire::encode($data,10)); continue; }
                if ($op === 10) continue;
                if ($op === 0) {
                    if ($p->fragmentOp === null) throw new ProtocolError('Unexpected continuation');
                    $p->fragment .= $data;
                    if (strlen($p->fragment) > Wire::LIMIT) throw new ProtocolError('Message too large');
                    if (!$frame['fin']) continue;
                    $data = $p->fragment; $op = $p->fragmentOp;
                    $p->fragment = ''; $p->fragmentOp = null;
                } else {
                    if ($p->fragmentOp !== null) throw new ProtocolError('Interleaved message');
                    if (!$frame['fin']) { $p->fragment = $data; $p->fragmentOp = $op; continue; }
                }
                if ($op !== 1) { $this->close($p,1003,'JSON text required'); return; }
                $second = time();
                if ($p->messageSecond !== $second) { $p->messageSecond = $second; $p->messages = 0; }
                if (++$p->messages > 150) { $this->close($p,1008,'Message rate limit'); return; }
                $m = json_decode($data, true, 8, JSON_THROW_ON_ERROR);
                if (!is_array($m) || !isset($m['t']) || !is_string($m['t'])) throw new ProtocolError('Invalid JSON message');
                if ($m['t'] !== 'relay' && strlen($data) > 4096) throw new ProtocolError('Control too large');
                $this->message($p,$m);
            }
        } catch (\JsonException|ProtocolError $e) {
            $this->close($p,1002,'Invalid protocol');
        } catch (\Throwable $e) {
            $this->audit('internal_error');
            $this->close($p,1011,'Internal error');
        }
    }

    private function handshake(Peer $p): bool
    {
        $end = strpos($p->in,"\r\n\r\n");
        if ($end === false) {
            if (strlen($p->in) > 8192) $this->httpClose($p,431,'Headers too large');
            return false;
        }
        if ($end > 8192) { $this->httpClose($p,431,'Headers too large'); return false; }
        $lines = explode("\r\n",substr($p->in,0,$end)); $first = array_shift($lines); $h = [];
        $p->in = substr($p->in,$end+4);
        foreach ($lines as $line) {
            if (!preg_match('/^([A-Za-z0-9-]+):[ \t]*(.*)$/D',$line,$match)) { $this->httpClose($p,400,'Bad headers'); return false; }
            $key = strtolower($match[1]);
            if (isset($h[$key])) { $this->httpClose($p,400,'Duplicate header'); return false; }
            $h[$key] = trim($match[2]);
        }
        if ($first === 'GET /healthz HTTP/1.1') {
            $this->httpClose($p,200,json_encode(['ok'=>true,'clients'=>$this->countUsers(),'limit'=>$this->limit])); return false;
        }
        $key = $h['sec-websocket-key'] ?? '';
        if ($first !== 'GET /ws HTTP/1.1' || !isset($h['host']) || isset($h['origin']) || isset($h['transfer-encoding']) || (isset($h['content-length']) && $h['content-length'] !== '0') ||
            strtolower($h['upgrade'] ?? '') !== 'websocket' || !in_array('upgrade',array_map('trim',explode(',',strtolower($h['connection'] ?? ''))),true) ||
            ($h['sec-websocket-version'] ?? '') !== '13' || strlen((string)base64_decode($key,true)) !== 16) {
            $this->httpClose($p,400,'Native WebSocket client required'); return false;
        }
        $accept = base64_encode(sha1($key.'258EAFA5-E914-47DA-95CA-C5AB0DC85B11',true));
        $p->upgraded = true;
        $this->queue($p,"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: $accept\r\n\r\n");
        return true;
    }

    private function message(Peer $p,array $m): void
    {
        $t = $m['t'];
        if ($p->user === null) {
            $user = $m['user'] ?? null; $token = $m['token'] ?? null; $users = $this->users();
            if ($t !== 'auth' || ($m['v'] ?? null) !== 1 || !is_string($user) || !preg_match('/^[A-Za-z0-9_.-]{1,40}$/D',$user) || !is_string($token) || !preg_match('/^[A-Za-z0-9_-]{43}$/D',$token) ||
                !isset($users[$user]) || !hash_equals($users[$user],hash('sha256',$token))) {
                $this->error($p,'authentication_failed'); $this->close($p,1008,'Authentication failed'); return;
            }
            if ($this->countUsers() >= $this->limit) { $this->error($p,'server_full'); $this->close($p,1013,'20-client limit'); return; }
            foreach ($this->peers as $other) {
                if (!$other->closing && $other->user === $user) { $this->error($p,'already_connected'); $this->close($p,1008,'Account already connected'); return; }
            }
            $p->user = $user; $p->tokenHash = $users[$user];
            $this->send($p,['t'=>'ready','v'=>1,'user'=>$user,'limit'=>$this->limit]);
            $this->audit('authenticated',$user); return;
        }
        if ($t === 'ping') { $this->send($p,['t'=>'pong']); return; }
        if ($t === 'host') {
            if ($p->room !== null) { $this->error($p,'busy'); return; }
            do { $room = bin2hex(random_bytes(16)); } while (isset($this->rooms[$room]));
            $this->rooms[$room] = ['host'=>$p->id,'viewer'=>null,'pair'=>null,'stage'=>'waiting','hello'=>false,'control'=>false,'expires'=>time()+300];
            $p->room = $room;
            $this->send($p,['t'=>'hosted','room'=>$room,'expires_in'=>300]); return;
        }
        if ($t === 'join') {
            $room = $m['room'] ?? '';
            if ($p->room !== null || !is_string($room) || !preg_match('/^[a-f0-9]{32}$/D',$room) || !isset($this->rooms[$room])) { $this->error($p,'unavailable'); return; }
            $r = &$this->rooms[$room];
            if ($r['stage'] !== 'waiting' || $r['host'] === $p->id || $r['expires'] <= time()) { $this->error($p,'unavailable'); return; }
            $p->room = $room; $r['viewer'] = $p->id; $r['pair'] = bin2hex(random_bytes(16)); $r['stage'] = 'pending'; $r['expires'] = time()+30;
            $host = $this->peers[$r['host']];
            $this->send($host,['t'=>'paired','pair'=>$r['pair'],'peer'=>$p->user]);
            $this->send($p,['t'=>'paired','pair'=>$r['pair'],'peer'=>$host->user]); return;
        }
        if ($p->room === null || !isset($this->rooms[$p->room])) { $this->error($p,'no_session'); return; }
        $r = &$this->rooms[$p->room]; $isHost = $r['host'] === $p->id;
        if ($t === 'stop' || ($t === 'deny' && $isHost)) { $this->endRoom($p->room,'stopped'); return; }
        if ($t === 'approve' && $isHost && $r['stage'] === 'pending' && $r['hello']) {
            if (!is_bool($m['control'] ?? null)) throw new ProtocolError('Boolean permission required');
            $r['control'] = $m['control']; $r['stage'] = 'active'; $r['expires'] = time()+3600;
            foreach ([$r['host'],$r['viewer']] as $id) $this->send($this->peers[$id],['t'=>'active','control'=>$r['control']]);
            return;
        }
        if ($t === 'revoke' && $isHost && $r['stage'] === 'active') {
            $r['control'] = false;
            foreach ([$r['host'],$r['viewer']] as $id) $this->send($this->peers[$id],['t'=>'control_revoked']);
            return;
        }
        if ($t !== 'relay') { $this->error($p,'invalid_state'); return; }
        $kind = $m['kind'] ?? null; $body = $m['body'] ?? null;
        if (!is_string($kind) || !is_string($body) || strlen($body) < 48 || strlen($body) > ($kind === 'frame' ? 1400000 : 4096) || base64_decode($body,true) === false) throw new ProtocolError('Invalid envelope');
        if ($r['stage'] === 'pending') {
            if ($isHost || $kind !== 'hello' || $r['hello']) { $this->error($p,'approval_required'); return; }
            $r['hello'] = true;
        } elseif ($r['stage'] === 'active') {
            $allowed = $isHost ? ['accept','frame','alive','permission'] : ['input','ack','alive'];
            if (!in_array($kind,$allowed,true) || ($kind === 'input' && !$r['control'])) { $this->error($p,'permission_denied'); return; }
        } else { $this->error($p,'approval_required'); return; }
        $target = $isHost ? $r['viewer'] : $r['host'];
        if (isset($this->peers[$target])) $this->send($this->peers[$target],['t'=>'relay','pair'=>$r['pair'],'kind'=>$kind,'body'=>$body]);
    }

    private function send(Peer $p,array $message): void
    {
        if (!$p->closing) $this->queue($p,Wire::encode(json_encode($message,JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR)));
    }
    private function error(Peer $p,string $code): void { $this->send($p,['t'=>'error','code'=>$code]); }
    private function queue(Peer $p,string $data): void
    {
        if (strlen($p->out)+strlen($data) > 2097152) { $this->drop($p->id); return; }
        $p->out .= $data;
    }
    private function httpClose(Peer $p,int $code,string $body): void
    {
        $p->out = "HTTP/1.1 $code " . ($code === 200 ? 'OK' : 'Error') . "\r\nContent-Type: application/json\r\nContent-Length: " . strlen($body) . "\r\nConnection: close\r\n\r\n$body";
        $p->closing = true; $p->closeAt = microtime(true)+1;
    }
    private function close(Peer $p,int $code = 1000,string $reason = ''): void
    {
        if ($p->closing) return;
        $p->closing = true; $p->closeAt = microtime(true)+1;
        if ($p->room !== null) $this->endRoom($p->room,'peer_disconnected');
        if ($p->upgraded) $this->queue($p,Wire::encode(pack('n',$code).$reason,8));
    }
    private function drop(int $id): void
    {
        if (!isset($this->peers[$id])) return;
        $p = $this->peers[$id]; unset($this->peers[$id]);
        if ($p->room !== null) $this->endRoom($p->room,'peer_disconnected');
        @fclose($p->socket);
        if ($p->user !== null) $this->audit('disconnected',$p->user);
    }
    private function endRoom(string $room,string $reason): void
    {
        if (!isset($this->rooms[$room])) return;
        $r = $this->rooms[$room]; unset($this->rooms[$room]);
        foreach ([$r['host'],$r['viewer']] as $id) {
            if ($id !== null && isset($this->peers[$id])) {
                $p = $this->peers[$id]; $p->room = null;
                $this->send($p,['t'=>'ended','reason'=>$reason]);
            }
        }
    }
    private function countUsers(): int
    {
        return count(array_filter($this->peers,fn(Peer $p) => $p->user !== null && !$p->closing));
    }
    private function users(): array
    {
        $raw = @file_get_contents($this->usersFile);
        $data = $raw === false ? null : json_decode($raw,true);
        if (!is_array($data)) return []; // Fail closed during corruption or removal.
        return array_filter($data,fn($v) => is_string($v) && preg_match('/^[a-f0-9]{64}$/D',$v));
    }
    private function sweep(): void
    {
        $now = microtime(true);
        if ($now-$this->lastSweep < 0.5) return;
        $this->lastSweep = $now;
        $users = null;
        if ($now-$this->lastUsers >= 5) { $users = $this->users(); $this->lastUsers = $now; }
        foreach (array_values($this->peers) as $p) {
            if ($p->closing) { if ($p->closeAt <= $now) $this->drop($p->id); continue; }
            if ((!$p->upgraded && $now-$p->born > 5) || ($p->user === null && $now-$p->born > 10) || $now-$p->seen > 45) {
                $this->close($p,1008,'Timeout');
            } elseif ($p->user !== null && $users !== null && (!isset($users[$p->user]) || !hash_equals($users[$p->user],$p->tokenHash))) {
                $this->close($p,1008,'Account revoked');
            }
        }
        foreach ($this->rooms as $id=>$r) if ($r['expires'] <= time()) $this->endRoom($id,'expired');
    }
    private function audit(string $event,?string $user = null): void
    {
        fwrite(STDOUT,json_encode(['time'=>gmdate('c'),'event'=>$event,'user'=>$user]).PHP_EOL);
    }
}
