<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/src/Wire.php';
use MinimalDesk\Wire;
use MinimalDesk\ProtocolError;
$checks = 0;
function check(bool $value): void { global $checks; ++$checks; if (!$value) throw new RuntimeException("Check $checks failed"); }
function masked(string $data): string {
    $raw = Wire::encode($data); $n = strlen($data); $head = strlen($raw)-$n;
    $mask = "abcd"; $raw[1] = chr(ord($raw[1])|128);
    return substr($raw,0,$head).$mask.($data ^ substr(str_repeat($mask,intdiv($n+3,4)),0,$n));
}
foreach ([0,1,125,126,65535,65536,120000] as $n) {
    $data = str_repeat('x',$n); $raw = masked($data); $full = $raw;
    $part = substr($raw,0,strlen($raw)-1); check(Wire::pop($part) === null);
    $decoded = Wire::pop($full); check($decoded['data'] === $data && $decoded['fin'] && $full === '');
}
foreach (["\x81\x02{}", "\xc1\x80abcd", "\x09\x80abcd", "\x81\xfe\x00\x01abcdx", "\x81\xff".pack('NN',1,0)] as $bad) {
    try { Wire::pop($bad); check(false); } catch (ProtocolError $e) { check(true); }
}
echo "$checks WebSocket framing checks passed\n";
