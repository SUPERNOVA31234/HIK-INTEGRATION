import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import os
import re

# DVRs com falhas
falhas = []

def ler_dvrs_txt(arquivo):
    dvrs = []
    if not os.path.isfile(arquivo):
        print(f"[ERRO] Arquivo '{arquivo}' não encontrado.")
        return dvrs

    with open(arquivo, 'r') as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.lstrip().startswith('#'):
                continue
            try:
                _, dados = linha.split(' - ', 1)
                partes = dados.split(',')
                if len(partes) == 3:
                    ip, username, password = partes
                    dvrs.append({
                        "ip": ip,
                        "username": username,
                        "password": password
                    })
                else:
                    print(f"[!] Linha inválida: {linha}")
            except Exception as e:
                print(f"[!] Erro ao processar linha: {linha} - {e}")
    return dvrs

def configurar_dvr(dvr, tentativa=1):
    now = datetime.now(timezone(timedelta(hours=-3)))
    local_time_str = now.strftime("%Y-%m-%dT%H:%M:%S-03:00")
    ns = "http://www.hikvision.com/ver20/XMLSchema"

    root = ET.Element("Time", xmlns=ns)
    ET.SubElement(root, "timeMode").text = "manual"
    ET.SubElement(root, "localTime").text = local_time_str
    ET.SubElement(root, "timeZone").text = "CST+3:00:00"

    xml_payload = ET.tostring(root, encoding="utf-8", method="xml").decode()
    url = f"http://{dvr['ip']}/ISAPI/System/time"

    try:
        response = requests.put(
            url,
            data=xml_payload,
            auth=HTTPDigestAuth(dvr["username"], dvr["password"]),
            headers={'Content-Type': 'application/xml'},
            timeout=(15 if tentativa == 1 else 30, 15 if tentativa == 1 else 30)
        )
        if response.status_code == 200:
            print(f"[✓] Sucesso: {dvr['ip']}")
        elif response.status_code == 404:
            print(f"[404] Endpoint não encontrado: {dvr['ip']}")
            falhas.append(dvr)
        elif response.status_code == 401:
            print(f"[401] Acesso negado: {dvr['ip']}")
            falhas.append(dvr)
        else:
            print(f"[!] Erro HTTP {response.status_code}: {dvr['ip']}")
            print("↳ Resposta:", response.text.strip())
            falhas.append(dvr)
    except requests.exceptions.ConnectTimeout:
        print(f"[X] Timeout: {dvr['ip']}")
        falhas.append(dvr)
    except requests.exceptions.ConnectionError:
        print(f"[X] Erro de conexão: {dvr['ip']}")
        falhas.append(dvr)
    except Exception as e:
        print(f"[X] Erro inesperado com {dvr['ip']}: {e}")
        falhas.append(dvr)

def executar_configuracao():
    print("\n==== INICIANDO CONFIGURAÇÃO DE DVRs ====\n")
    dvrs = ler_dvrs_txt("dvrs.txt")
    if not dvrs:
        print("[!] Nenhum DVR encontrado. Corrija o arquivo dvrs.txt.")
        return

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(lambda d: configurar_dvr(d, tentativa=1), dvrs)

    if falhas:
        print("\n==== TENTANDO NOVAMENTE DVRs COM FALHA ====\n")
        reprocessar = falhas.copy()
        falhas.clear()
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.map(lambda d: configurar_dvr(d, tentativa=2), reprocessar)

        if falhas:
            print("\n[!] DVRs que falharam nas duas tentativas:")
            for d in falhas:
                print(f"- {d['ip']}")
        else:
            print("\n[✓] Todos os DVRs foram configurados na segunda tentativa!")
    else:
        print("\n[✓] Todos os DVRs foram configurados com sucesso!")

# Função para extrair a remota automaticamente pelo padrão corsegXXXX
def extrair_remota_por_nome(host_com_porta):
    host = host_com_porta.split(':')[0]
    match = re.search(r'corseg(\d+)', host)
    if match:
        return match.group(1).zfill(4)
    return None

# Função para buscar remota no arquivo txt (manual)
def encontrar_remota_por_ip(caminho_arquivo, ip_busca):
    if not os.path.isfile(caminho_arquivo):
        print(f"[ERRO] Arquivo '{caminho_arquivo}' não encontrado.")
        return None

    with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if ip_busca in linha:
                linha_sem_hash = linha.lstrip("#").strip()
                partes = linha_sem_hash.split("-")
                if len(partes) >= 2:
                    numero_remota = partes[0].strip()
                    return numero_remota
    return None

# Função que junta as duas buscas para remota: automática e manual
def obter_remota(ip, arquivo_txt="lista_remotas.txt"):
    remota_auto = extrair_remota_por_nome(ip)
    if remota_auto:
        return remota_auto
    remota_manual = encontrar_remota_por_ip(arquivo_txt, ip)
    return remota_manual

if __name__ == "__main__":
    executar_configuracao()

    # Teste rápido para listar a remota dos DVRs que falharam
    print("\n==== Associação das remotas dos DVRs que falharam ====\n")
    for dvr in falhas:
        remota = obter_remota(dvr['ip'])
        print(f"{dvr['ip']} => remota {remota if remota else 'não encontrada'}")
