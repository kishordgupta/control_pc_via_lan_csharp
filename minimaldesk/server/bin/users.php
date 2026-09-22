<?php
declare(strict_types=1);
// Tokens are randomly generated credentials, not human-chosen passwords.
$data = getenv('MINIDESK_DATA') ?: dirname(__DIR__).'/data';
$command = $argv[1] ?? ''; $user = $argv[2] ?? '';
if (!in_array($command,['add','revoke','list'],true) || ($command !== 'list' && !preg_match('/^[A-Za-z0-9_.-]{1,40}$/D',$user))) {
    fwrite(STDERR,"Usage: php server/bin/users.php add|revoke USER   or   list\n"); exit(1);
}
umask(0077);
if (!is_dir($data) && !mkdir($data,0700,true)) { fwrite(STDERR,"Cannot create data directory.\n"); exit(1); }
$lock = fopen($data.'/.users.lock','c');
if (!$lock || !flock($lock,LOCK_EX)) exit(1);
$path = $data.'/users.json';
try {
    $users = is_file($path) ? json_decode(file_get_contents($path),true,16,JSON_THROW_ON_ERROR) : [];
    if (!is_array($users)) throw new RuntimeException('Invalid account file');
    if ($command === 'list') { foreach (array_keys($users) as $name) echo "$name\n"; exit; }
    if ($command === 'add') {
        if (isset($users[$user])) throw new RuntimeException('User exists. Revoke first to rotate credentials.');
        $token = rtrim(strtr(base64_encode(random_bytes(32)),'+/','-_'),'=');
        $users[$user] = hash('sha256',$token);
    } else { unset($users[$user]); }
    $temp = tempnam($data,'.users-');
    if ($temp === false || file_put_contents($temp,json_encode((object)$users,JSON_PRETTY_PRINT|JSON_THROW_ON_ERROR)."\n") === false || !chmod($temp,0600) || !rename($temp,$path)) throw new RuntimeException('Cannot save accounts');
    echo $command === 'add' ? "Username: $user\nToken (shown once): $token\n" : "Revoked: $user\n";
} catch (Throwable $e) { fwrite(STDERR,$e->getMessage()."\n"); exit(1); }
