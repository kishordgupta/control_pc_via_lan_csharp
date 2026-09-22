<?php
declare(strict_types=1);
require_once __DIR__ . '/src/Relay.php';
if (PHP_SAPI !== 'cli' || PHP_VERSION_ID < 80200) { fwrite(STDERR,"PHP 8.2+ CLI required.\n"); exit(1); }
$data = getenv('MINIDESK_DATA') ?: __DIR__.'/data';
if (!is_dir($data) && !mkdir($data,0700,true)) { fwrite(STDERR,"Cannot create data directory.\n"); exit(1); }
$lock = fopen($data.'/.relay.lock','c');
if (!$lock || !flock($lock,LOCK_EX|LOCK_NB)) { fwrite(STDERR,"A relay already owns this data directory.\n"); exit(1); }
try {
    $limit = getenv('MINIDESK_MAX_CLIENTS');
    if ($limit !== false && !preg_match('/^[0-9]+$/D',$limit)) throw new RuntimeException('Invalid client limit');
    (new MinimalDesk\Relay(getenv('MINIDESK_LISTEN') ?: '127.0.0.1:8080',$data.'/users.json',$limit === false ? 20 : (int)$limit))->run();
} catch (Throwable $e) { fwrite(STDERR,$e->getMessage()."\n"); exit(1); }
