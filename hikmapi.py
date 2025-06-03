import requests
from requests.auth import HTTPDigestAuth
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
import subprocess

RED = "\033[31m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

print(rf"""===============================================================================================================================================      
{RED} /$$   /$$ /$$$$$$ /$$   /$${RESET}     {GREEN}  /$$$$$$ /$$   /$$ /$$$$$$$$ /$$$$$$$$  /$$$$$$  /$$$$$$$   /$$$$$$  /$$$$$$$$ /$$$$$$  /$$$$$$  /$$   /$${RESET}
{RED}| $$  | $$|_  $$_/| $$  /$$/{RESET}     {GREEN} |_  $$_/| $$$ | $$|__  $$__/| $$_____/ /$$__  $$| $$__  $$ /$$__  $$|__  $$__/|_  $$_/ /$$__  $$| $$$ | $${RESET}
{RED}| $$  | $$  | $$  | $$ /$$/ {RESET}     {GREEN}   | $$  | $$$$| $$   | $$   | $$      | $$  \__/| $$  \ $$| $$  \ $$   | $$     | $$  | $$  \ $$| $$$$| $${RESET}
{RED}| $$$$$$$$  | $$  | $$$$$/  {RESET}     {GREEN}   | $$  | $$ $$ $$   | $$   | $$$$$   | $$ /$$$$| $$$$$$$/| $$$$$$$$   | $$     | $$  | $$  | $$| $$ $$ $${RESET}
{RED}| $$__  $$  | $$  | $$  $$  {RESET}     {GREEN}   | $$  | $$  $$$$   | $$   | $$__/   | $$|_  $$| $$__  $$| $$__  $$   | $$     | $$  | $$  | $$| $$  $$$${RESET}
{RED}| $$  | $$  | $$  | $$\  $$ {RESET}     {GREEN}   | $$  | $$\  $$$   | $$   | $$      | $$  \ $$| $$  \ $$| $$  | $$   | $$     | $$  | $$  | $$| $$\  $$${RESET}
{RED}| $$  | $$ /$$$$$$| $$ \  $${RESET}     {GREEN}  /$$$$$$| $$ \  $$   | $$   | $$$$$$$$|  $$$$$$/| $$  | $$| $$  | $$   | $$    /$$$$$$|  $$$$$$/| $$ \  $${RESET}
{RED}|__/  |__/|______/|__/  \__/{RESET}     {GREEN} |______/|__/  \__/   |__/   |________/ \______/ |__/  |__/|__/  |__/   |__/   |______/ \______/ |__/  \__/{RESET}
===============================================================================================================================================
By: Lucas""")

def verificar_nmap():
    return shutil.which("nmap") is not None

def testar_dvr_nmap(ip, porta):
    try:
        result = subprocess.run(
            ["nmap", "-Pn", "-p", porta, ip],
            capture_output=True,
            text=True,
            timeout=10
        )
        if "open" in result.stdout:
            return True
    except Exception as e:
        print(f"[x] Erro ao testar {ip}:{porta} -> {e}")
    return False

def scan_dvrs_online(dvrs):
    if not verificar_nmap():
        print("[!] nmap não encontrado. Tentando configurar todos os DVRs sem filtro...")
        return dvrs, []  # online = todos, offline = nenhum

    online = []
    offline = []

    print("\n[•] Iniciando scan dos DVRs via nmap para verificar quem está online...\n")
    for dvr in dvrs:
        ip = dvr['ip']
        porta = ip.split(':')[1] if ':' in ip else '80'  # fallback porta 80
        ip_only = ip.split(':')[0]

        print(f"Testando {ip}...")
        if testar_dvr_nmap(ip_only, porta):
            print(f"{GREEN}[✓] {ip} ONLINE{RESET}")
            online.append(dvr)
        else:
            print(f"{RED}[X] {ip} OFFLINE ou porta fechada{RESET}")
            offline.append(dvr)

    print(f"\nResumo do scan: {len(online)} online, {len(offline)} offline.\n")
    return online, offline

def ler_dvr_txt(arquivo):
    if not os.path.isfile(arquivo):
        print(f"[ERRO] Arquivo '{arquivo}' não encontrado.")
        return []
    
    dvrs = []
    with open(arquivo, 'r') as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith('#'):
                continue
            if ' - ' not in linha:
                print(f"[!] Linha mal formatada (faltando ' - '): {linha}")
                continue

            _, dados = linha.split(' - ', 1)

            partes = [x.strip() for x in dados.split(',')]
            if len(partes) != 3:
                print(f"[!] Linha inválida (esperado IP, usuário e senha): {linha}")
                continue

            ip, username, password = partes
            dvrs.append({"ip": ip, "username": username, "password": password})

    return dvrs


def gerar_xml_feriados(arquivo_txt):
    if not os.path.isfile(arquivo_txt):
        print(f"[ERRO] Arquivo '{arquivo_txt}' não encontrado.")
        return ""

    xml = ['''<?xml version="1.0" encoding="UTF-8"?>\n<HolidayList version="1.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">''']
    with open(arquivo_txt, 'r', encoding='utf-8') as f:
        for i, linha in enumerate(f, start=1):
            linha = linha.strip()
            if not linha or linha.startswith('#'):
                continue
            partes = linha.split(',')
            if len(partes) != 3:
                print(f"[!] Linha inválida (esperado 3 campos): {linha}")
                continue
            nome, mes, dia = [x.strip() for x in partes]
            bloco = f'''
  <holiday>
    <id>{i}</id>
    <enabled>true</enabled>
    <holidayName>{nome}</holidayName>
    <holidayMode>month</holidayMode>
    <holidayMonth>
      <startMonth>
        <monthOfYear>{mes}</monthOfYear>
        <dayOfMonth>{dia}</dayOfMonth>
      </startMonth>
      <endMonth>
        <monthOfYear>{mes}</monthOfYear>
        <dayOfMonth>{dia}</dayOfMonth>
      </endMonth>
    </holidayMonth>
  </holiday>'''
            xml.append(bloco)
    xml.append('</HolidayList>')
    return '\n'.join(xml)


def configurar_feriados(dvr, xml_payload):
    url = f"http://{dvr['ip']}/ISAPI/System/holidays"
    try:
        resp = requests.put(url, data=xml_payload, auth=HTTPDigestAuth(dvr['username'], dvr['password']), headers={'Content-Type': 'application/xml'}, timeout=10)
        if resp.status_code == 200:
            print(f"[✓] Feriados aplicados em {dvr['ip']}")
            return True
        print(f"[!] Erro {resp.status_code} em {dvr['ip']} -> {resp.text.strip()}")
    except Exception as e:
        print(f"[X] Falha em {dvr['ip']} -> {e}")
    return False


def configurar_horario(dvr, tentativa=1):
    now = datetime.now(timezone(timedelta(hours=-3)))
    xml_time = ET.Element("Time", xmlns="http://www.hikvision.com/ver20/XMLSchema")
    ET.SubElement(xml_time, "timeMode").text = "manual"
    ET.SubElement(xml_time, "localTime").text = now.strftime("%Y-%m-%dT%H:%M:%S-03:00")
    ET.SubElement(xml_time, "timeZone").text = "CST+3:00:00"

    payload = ET.tostring(xml_time, encoding="utf-8").decode()
    url = f"http://{dvr['ip']}/ISAPI/System/time"

    try:
        resp = requests.put(url, data=payload, auth=HTTPDigestAuth(dvr["username"], dvr["password"]), headers={'Content-Type': 'application/xml'}, timeout=(15, 15))
        if resp.status_code == 200:
            print(f"[✓] Horário configurado: {dvr['ip']}")
            return True
        print(f"[!] Erro {resp.status_code} em {dvr['ip']} -> {resp.text.strip()}")
    except requests.exceptions.ConnectTimeout:
        print(f"[X] Timeout em {dvr['ip']}")
    except Exception as e:
        print(f"[X] Falha em {dvr['ip']} -> {e}")
    return False


def executar_em_threads(func, dvrs, extra_args=None, max_workers=10):
    falhas = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(func, dvr, *extra_args) if extra_args else executor.submit(func, dvr): dvr
            for dvr in dvrs
        }
        for future in as_completed(futures):
            dvr = futures[future]
            try:
                if not future.result():
                    falhas.append(dvr)
            except Exception as e:
                print(f"[X] Erro em execução com {dvr['ip']}: {e}")
                falhas.append(dvr)
    return falhas


def executar_configuracao_horario():
    dvrs = ler_dvr_txt("dvrs.txt")
    if not dvrs:
        print("[!] Nenhum DVR encontrado.")
        return

    print("\n[1ª TENTATIVA] Configurando horário dos DVRs...") 
    falhas = executar_em_threads(configurar_horario, dvrs, extra_args=[1], max_workers=10)

    if falhas:
        print("\n[2ª TENTATIVA] Verificando conectividade com Nmap nos que falharam...")
        dvrs_online, dvrs_offline = scan_dvrs_online(falhas)

        if dvrs_online:
            print("\n[2ª TENTATIVA] Reprocessando falhas nos que estão online...")
            falhas_final = executar_em_threads(configurar_horario, dvrs_online, extra_args=[2], max_workers=3)
            if falhas_final:
                print("\n[!] Falhas permanentes:")
                for dvr in falhas_final:
                    print(f"- {dvr['ip']}")
            else:
                print("\n[✓] Todos os DVRs configurados na segunda tentativa.")
        else:
            print("[!] Nenhum DVR online entre os que falharam.")
    else:
        print("\n[✓] Todos os DVRs configurados com sucesso!")

    # Mostrar os totalmente offline (falha + Nmap negativo)
    if falhas:
        print("\n[DVRs offline e não configurados:]")
        for dvr in dvrs_offline:
            print(f"- {dvr['ip']}")

    falhas = executar_em_threads(configurar_horario, dvrs_online, extra_args=[1], max_workers=10)

    if falhas:
        print("\n[2ª TENTATIVA] Reprocessando falhas...")
        falhas_final = executar_em_threads(configurar_horario, falhas, extra_args=[2], max_workers=3)
        if falhas_final:
            print("\n[!] Falhas permanentes:")
            for dvr in falhas_final:
                print(f"- {dvr['ip']}")
        else:
            print("\n[✓] Todos os DVRs configurados na segunda tentativa.")
    else:
        print("\n[✓] Todos os DVRs configurados com sucesso!")

    if dvrs_offline:
        print("\n[DVRs offline e não configurados:]")
        for dvr in dvrs_offline:
            print(f"- {dvr['ip']}")



def executar_configuracao_feriados():
    dvrs = ler_dvr_txt("dvrs.txt")
    xml_feriados = gerar_xml_feriados("feriados.txt")
    if not dvrs or not xml_feriados:
        return

    dvrs_online, dvrs_offline = scan_dvrs_online(dvrs)

    if not dvrs_online:
        print("[!] Nenhum DVR online para configurar feriados.")
        return

    print("\n[•] Enviando feriados para os DVRs online...")
    falhas = executar_em_threads(configurar_feriados, dvrs_online, extra_args=[xml_feriados])
    if falhas:
        print("\n[!] DVRs com falha ao configurar feriados:")
        for d in falhas:
            print(f"{d['ip']}")
    else:
        print("\n[✓] Feriados configurados com sucesso em todos os DVRs online.")

    if dvrs_offline:
        print("\n[DVRs offline e não configurados:]")
        for dvr in dvrs_offline:
            print(f"- {dvr['ip']}")



def menu():
    print("\nEscolha a opção de configuração:")
    print("1 - Configurar feriados (via XML)")
    print("2 - Configurar horário manual")
    escolha = input("Digite 1 ou 2: ").strip()

    if escolha == '1':
        executar_configuracao_feriados()
    elif escolha == '2':
        executar_configuracao_horario()
    else:
        print("[X] Opção inválida. Execute novamente.")


if __name__ == "__main__":
    menu()
