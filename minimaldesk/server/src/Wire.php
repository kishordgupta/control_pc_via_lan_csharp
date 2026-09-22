<?php
declare(strict_types=1);
namespace MinimalDesk;

final class ProtocolError extends \RuntimeException {}

/** Bounded RFC 6455 framing. Clients must mask; extensions are not negotiated. */
final class Wire
{
    public const LIMIT = 1500000;

    public static function encode(string $data, int $opcode = 1): string
    {
        $n = strlen($data);
        $head = chr(0x80 | $opcode);
        if ($n < 126) return $head . chr($n) . $data;
        if ($n <= 65535) return $head . chr(126) . pack('n', $n) . $data;
        return $head . chr(127) . pack('NN', 0, $n) . $data;
    }

    /** @return array{fin:bool,op:int,data:string}|null */
    public static function pop(string &$buffer): ?array
    {
        if (strlen($buffer) < 2) return null;
        $a = ord($buffer[0]); $b = ord($buffer[1]);
        $fin = (bool)($a & 128); $op = $a & 15;
        if (($a & 112) || !($b & 128) || !in_array($op, [0,1,2,8,9,10], true)) {
            throw new ProtocolError('Invalid WebSocket frame');
        }
        $n = $b & 127; $at = 2;
        if ($n === 126) {
            if (strlen($buffer) < 4) return null;
            $n = unpack('n', substr($buffer, 2, 2))[1]; $at = 4;
            if ($n < 126) throw new ProtocolError('Non-minimal length');
        } elseif ($n === 127) {
            if (strlen($buffer) < 10) return null;
            $parts = unpack('Nhi/Nlo', substr($buffer, 2, 8));
            if ($parts['hi'] !== 0 || $parts['lo'] < 65536) {
                throw new ProtocolError('Invalid or excessive length');
            }
            $n = $parts['lo']; $at = 10;
        }
        if ($n > self::LIMIT || ($op >= 8 && (!$fin || $n > 125))) {
            throw new ProtocolError('Frame exceeds limits');
        }
        if (strlen($buffer) < $at + 4 + $n) return null;
        $mask = substr($buffer, $at, 4);
        $data = substr($buffer, $at + 4, $n);
        $buffer = substr($buffer, $at + 4 + $n);
        if ($n) $data = $data ^ substr(str_repeat($mask, intdiv($n + 3, 4)), 0, $n);
        return ['fin'=>$fin, 'op'=>$op, 'data'=>$data];
    }
}
