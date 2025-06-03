import requests
from requests.auth import HTTPDigestAuth
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
import sys


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
def executar_hd():
    lista_dvrs = ler_dvrs_txt1("dvrs.txt")
    if not lista_dvrs:
        print("Nenhum DVR válido encontrado.")
        return  # Encerra a função se não houver DVRs válidos

    while True:  # loop principal

        while True:
            opcao_modo = input("Escolha o modo: [1] Detalhado | [2] Resumo Final: ").strip()
            if opcao_modo in ('1', '2'):
                modo_detalhado = (opcao_modo == '1')
                break
            print("Opção inválida. Digite '1' para Detalhado ou '2' para Resumo Final.")

        while True:
            opcao = input("Deseja que o script verifique status 'notexist'? (s/n): ").strip().lower()
            if opcao in ('s', 'n'):
                checar_notexist = (opcao == 's')
                break
            print("Resposta inválida. Digite 's' para sim ou 'n' para não.")

        resultados = []
        print("\n🔍 Iniciando verificação...\n")
        for dvr in lista_dvrs:
            resultado = verificar_dvr_hd_status(dvr, checar_notexist, modo_detalhado)
            resultados.append(resultado)
            
        print(f"""
              

########################
{YELLOW}RELATÓRIO FINAL DE ERROS{RESET}
########################
 
 
 
""")
    
        for r in resultados:
            if r["falhou"]:
                print(f"❌ {r['nome']} ({r['ip']}) - {r['msg_falha']}")
            elif r["erros"] or r["avisos"]:
                print(f"{YELLOW}{r['nome']} ({r['ip']}){RESET}")
                for erro in r["erros"]:
                    print(f"{RED}{erro}{RESET}")
                for aviso in r["avisos"]:
                    print(f"{YELLOW}{aviso}{RESET}")
        print("\n✅ Verificação concluída.")

        for dvr, resultado in zip(lista_dvrs, resultados):
            if resultado["erros"]:
                while True:
                    resposta = input(f"\nDeseja reiniciar o DVR '{dvr['nome']}' com problema crítico? (s/n): ").strip().lower()
                    if resposta in ('s', 'n'):
                        break
                    print("Resposta inválida. Digite 's' para sim ou 'n' para não.")
                if resposta == 's':
                    if reiniciar_dvr(dvr):
                        aguardar_online(dvr)


        while True:
            repetir = input("\nDeseja realizar uma nova verificação? (s/n): ").strip().lower()
            if repetir == 's':
                print("\n🔄 Reiniciando a verificação...\n")
                break
            elif repetir == 'n':
                print("Encerrando o script")
                menu()
            else:
                print("Opção inválida. Digite 's' para sim ou 'n' para não.")

NS = {'hik': 'http://www.hikvision.com/ver20/XMLSchema'}
CRITICAL_STATUS = {'error', 'unformatted', 'uninitialized', 'abnormal', 'degraded'}
WARNING_STATUS = {'full', 'formatting'}

# === Lê os DVRs do arquivo txt ===
def ler_dvrs_txt1(arquivo):
    if not os.path.isfile(arquivo):
        print(f"[ERRO] Arquivo '{arquivo}' não encontrado.")
        return []

    dvrs = []
    with open(arquivo, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith('#'):
                continue
            if ' - ' not in linha:
                print(f"[!] Linha mal formatada (faltando ' - '): {linha}")
                continue

            nome, dados = linha.split(' - ', 1)
            partes = [x.strip() for x in dados.split(',')]
            if len(partes) != 3:
                print(f"[!] Linha inválida (esperado IP, usuário e senha): {linha}")
                continue

            ip, username, password = partes
            dvrs.append({
                "nome": nome.strip(),
                "ip": ip,
                "username": username,
                "password": password
            })

    return dvrs

# === Reboot DVR ===
def reiniciar_dvr(dvr):
    print(f"\n🔁 Enviando comando de reboot para: {dvr['nome']} ({dvr['ip']})")
    url = f"http://{dvr['ip']}/ISAPI/System/reboot"
    try:
        resp = requests.put(url, auth=HTTPDigestAuth(dvr['username'], dvr['password']), timeout=5)
        if resp.status_code in [200, 202, 204]:
            print("⏳ Reboot solicitado com sucesso.")
            return True
        else:
            print(f"❌ Falha ao reiniciar ({resp.status_code})")
    except Exception as e:
        print(f"❌ Erro ao enviar reboot: {e}")
    return False

# === Aguarda DVR voltar online ===
def aguardar_online(dvr, timeout=100):
    print(f"⏱️ Aguardando {dvr['nome']} voltar online (máximo {timeout}s)...")
    url = f"http://{dvr['ip']}/ISAPI/ContentMgmt/Storage"
    auth = HTTPDigestAuth(dvr['username'], dvr['password'])

    for i in range(timeout):
        try:
            resp = requests.get(url, auth=auth, timeout=2)
            if resp.status_code == 200:
                print(f"✅ {dvr['nome']} voltou online após {i+1} segundos.")
                return True
        except:
            pass
        time.sleep(1)
    print(f"❌ {dvr['nome']} não voltou online após {timeout} segundos.")
    return False


# === Verifica o status dos HDs de um único DVR ===
def verificar_dvr_hd_status(dvr, checar_notexist, modo_detalhado):
    url = f"http://{dvr['ip']}/ISAPI/ContentMgmt/Storage"
    session = requests.Session()
    session.auth = HTTPDigestAuth(dvr['username'], dvr['password'])

    resultado = {
        "nome": dvr['nome'],
        "ip": dvr['ip'],
        "erros": [],
        "avisos": [],
        "tempo": 0,
        "status_http": None,
        "falhou": False,
        "msg_falha": ""
    }

    try:
        inicio = time.time()
        resp = session.get(url, timeout=10)
        duracao = time.time() - inicio
        resultado["tempo"] = duracao
        resultado["status_http"] = resp.status_code

        if resp.status_code != 200:
            resultado["falhou"] = True
            resultado["msg_falha"] = f"Erro HTTP {resp.status_code}"
            if modo_detalhado:
                print(f"❌ {dvr['nome']} ({dvr['ip']}) - {resultado['msg_falha']}")
            return resultado

        root = ET.fromstring(resp.text)
        hdds = root.findall('.//hik:hdd', NS)

        if not hdds:
            resultado["falhou"] = True
            resultado["msg_falha"] = "Nenhum HD foi listado no XML da resposta"
            if modo_detalhado:
                print(f"❌ {dvr['nome']} ({dvr['ip']}) - {resultado['msg_falha']}")
            return resultado

        if modo_detalhado:
            print(f"\n🔍 {dvr['nome']} ({dvr['ip']}) - Verificando...")

        for hdd in hdds:
            hd_id = hdd.find('hik:id', NS).text
            status = hdd.find('hik:status', NS).text.lower()

            if status == 'notexist' and not checar_notexist:
                if modo_detalhado:
                    print(f"ℹ️ HD {hd_id} com status 'notexist' (ignorado).")
                continue

            if status == 'notexist':
                msg = f"HD {hd_id} não conectado ou não reconhecido"
                resultado["erros"].append(msg)
                if modo_detalhado:
                    print(f"❌ {msg}")
            elif status in CRITICAL_STATUS:
                msg = f"HD {hd_id} com problema crítico: {status}"
                resultado["erros"].append(msg)
                if modo_detalhado:
                    print(f"❌ {msg}")
            elif status in WARNING_STATUS:
                msg = f"HD {hd_id} com alerta: {status}"
                resultado["avisos"].append(msg)
                if modo_detalhado:
                    print(f"⚠️ {msg}")
            else:
                if modo_detalhado:
                    print(f"✅ HD {hd_id} está OK.")

        if modo_detalhado and not resultado["erros"]:
            print("✅ Todos os HDs estão OK.")

    except requests.exceptions.ConnectTimeout:
        resultado["falhou"] = True
        resultado["msg_falha"] = "Não foi possível conectar ao DVR (tempo excedido)"
    except requests.exceptions.ConnectionError:
        resultado["falhou"] = True
        resultado["msg_falha"] = "Falha de conexão com o DVR (verifique IP/DDNS e porta)"
    except ET.ParseError:
        resultado["falhou"] = True
        resultado["msg_falha"] = "Erro ao interpretar o XML da resposta"
    except Exception as e:
        resultado["falhou"] = True
        resultado["msg_falha"] = f"Erro inesperado: {e}"

    return resultado



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
    dvrs = ler_dvrs_txt1("dvrs.txt")
    if not dvrs:
        print("[!] Nenhum DVR encontrado.")
        return

    print("\n[1ª TENTATIVA] Configurando horário dos DVRs...")
    falhas = executar_em_threads(configurar_horario, dvrs, extra_args=[1], max_workers=10)

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


def executar_configuracao_feriados():
    dvrs = ler_dvrs_txt1("dvrs.txt")
    xml_feriados = gerar_xml_feriados("feriados.txt")
    if not dvrs or not xml_feriados:
        return
    print("\n[•] Enviando feriados para os DVRs...")
    falhas = executar_em_threads(configurar_feriados, dvrs, extra_args=[xml_feriados])
    if falhas:
        print("\n[!] DVRs com falha ao configurar feriados:")
        for d in falhas:
            print(f"{d['ip']}")
    else:
        print("\n[✓] Feriados configurados com sucesso em todos os DVRs.")




def menu():
    while True:
        print("\nEscolha a opção de configuração:")
        print("1 - Configurar feriados")
        print("2 - Configurar horário")
        print("3 - Verificação HD")
        print("4 - Sair")

        escolha = input("Escolha o número: ").strip()

        if escolha == '1':
            executar_configuracao_feriados()
        elif escolha == '2':
            executar_configuracao_horario()
        elif escolha == '3':
            while True:
                executar_hd()
                nova = input("\nDeseja realizar uma nova verificação? (s/n): ").strip().lower()
                if nova != 's':
                    print("Encerrando a verificação de HD.")
                    break
        elif escolha == '4':
            print("Saindo...")
            sys.exit()
        else:
            print("Opção inválida, tente novamente.")


if __name__ == "__main__":
    menu()