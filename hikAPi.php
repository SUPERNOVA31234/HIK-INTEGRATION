<?php

// Configurações do DVR
$ip = "corseg.ddns.net:3000";
$username = "admin";
$password = "cradmroot68@1";

// === VERIFICAR ENDPOINTS DISPONÍVEIS ===
echo "=== VERIFICAÇÃO DOS ENDPOINTS ===\n";
$endpoints = [
    "/ISAPI/System/time",
    "/ISAPI/System/time/ntp",
    "/ISAPI/System/network/interfaces",
    "/ISAPI/Streaming/channels",
];

foreach ($endpoints as $ep) {
    $url = "http://$ip$ep";
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPAUTH, CURLAUTH_DIGEST);
    curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    echo "GET $ep - Status: $http_code\n";
    echo substr($response, 0, 500) . "\n\n"; // Mostra os primeiros 500 caracteres
    curl_close($ch);
}
echo "=================================\n\n";

// === CONFIGURAÇÃO DE HORÁRIO MANUAL ===
echo "=== CONFIGURAÇÃO DE HORÁRIO ===\n";

// Geração do XML
$xml = new SimpleXMLElement('<Time></Time>');
$xml->addChild('timeMode', 'manual');
$xml->addChild('localTime', '2025-05-22T15:30:00-03:00'); // Pode ajustar dinamicamente se desejar
$xml->addChild('timeZone', 'CST+3:00:00');

$xml_string = $xml->asXML();

// Debug
echo "======= XML ENVIADO =======\n";
echo $xml_string . "\n";
echo "===========================\n";

// Envio do XML via PUT
$url = "http://$ip/ISAPI/System/time";
$ch = curl_init($url);
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, "PUT");
curl_setopt($ch, CURLOPT_POSTFIELDS, $xml_string);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/xml']);
curl_setopt($ch, CURLOPT_HTTPAUTH, CURLAUTH_DIGEST);
curl_setopt($ch, CURLOPT_USERPWD, "$username:$password");

$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);

if ($http_code == 200) {
    echo "[✓] Hora configurada com sucesso: $ip\n";
} else {
    echo "[!] Falha ao configurar horário em $ip - Status: $http_code\n";
    echo "Resposta:\n$response\n";
}
curl_close($ch);
?>
