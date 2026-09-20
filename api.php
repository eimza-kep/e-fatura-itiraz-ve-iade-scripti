<?php
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json; charset=UTF-8");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

$dataFile = __DIR__ . '/fatura_itirazlar.json';

function getStoredData($file) {
    if (!file_exists($file)) return [];
    $content = file_get_contents($file);
    return json_decode($content, true) ?: [];
}

function saveStoredData($file, $data) {
    file_put_contents($file, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
}

$action = $_GET['action'] ?? '';
$method = $_SERVER['REQUEST_METHOD'];

if ($method === 'POST') {
    $raw = file_get_contents('php://input');
    $input = json_decode($raw, true) ?: [];

    if ($action === 'durum-guncelle' || (isset($input['action']) && $input['action'] === 'durum-guncelle')) {
        $tracking = $input['tracking_code'] ?? '';
        $newStatus = $input['status'] ?? 'İtiraz Gönderildi (KEP/Noter)';

        $records = getStoredData($dataFile);
        $updated = false;
        foreach ($records as &$item) {
            if (($item['tracking_code'] ?? '') === $tracking) {
                $item['status'] = $newStatus;
                $updated = true;
                break;
            }
        }
        saveStoredData($dataFile, $records);
        echo json_encode(['status' => 'success', 'updated' => $updated, 'new_status' => $newStatus]);
        exit();
    }

    $trackingCode = $input['tracking_code'] ?? ('ITIRAZ-2026-' . rand(1000, 9999));
    $input['tracking_code'] = $trackingCode;
    $input['status'] = $input['status'] ?? 'İtiraz Gönderildi (KEP/Noter)';
    $input['created_at'] = $input['created_at'] ?? date('c');

    $records = getStoredData($dataFile);
    array_unshift($records, $input);
    saveStoredData($dataFile, $records);

    echo json_encode(['status' => 'success', 'tracking_code' => $trackingCode]);
    exit();
}

if ($method === 'GET') {
    $records = getStoredData($dataFile);
    echo json_encode($records, JSON_UNESCAPED_UNICODE);
    exit();
}
