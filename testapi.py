import os
import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET
import time

# Cores
RED = "\033[31m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Constantes XML
NS = {'hik': 'http://www.hikvision.com/ver20/XMLSchema'}
CRITICAL_STATUS = {'error', 'unformatted', 'uninitialized', 'abnormal', 'degraded'}
WARNING_STATUS = {'full', 'formatting'}

def ler_dvrs_txt(arquivo):
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

def aguardar_online(dvr, timeout=100):
    print(f"⏱ Aguardando {dvr['nome']} voltar online (máximo {timeout}s)...")
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

def verificar_dvr_hd_status(dvr, checar_notexist, modo_detalhado):
    url = f"http://{dvr['ip']}/ISAPI/ContentMgmt/Storage"
    session = requests.Session()
    session.auth = HTTPDigestAuth(dvr['username'], dvr['password'])
    resultado = {
        "nome": dvr['nome'], "ip": dvr['ip'],
        "erros": [], "avisos": [], "tempo": 0,
        "status_http": None, "falhou": False, "msg_falha": ""
    }
    try:
        inicio = time.time()
        resp = session.get(url, timeout=10)
        resultado["tempo"] = time.time() - inicio
        resultado["status_http"] = resp.status_code
        if resp.status_code != 200:
            resultado["falhou"] = True
            resultado["msg_falha"] = f"Erro HTTP {resp.status_code}"
            return resultado
        root = ET.fromstring(resp.text)
        hdds = root.findall('.//hik:hdd', NS)
        if not hdds:
            resultado["falhou"] = True
            resultado["msg_falha"] = "Nenhum HD listado"
            return resultado
        if modo_detalhado:
            print(f"\n🔍 {dvr['nome']} ({dvr['ip']}) - Verificando...")
        for hdd in hdds:
            hd_id = hdd.find('hik:id', NS).text
            status = hdd.find('hik:status', NS).text.lower()
            if status == 'notexist' and not checar_notexist:
                continue
            if status == 'notexist':
                resultado["erros"].append(f"HD {hd_id} não conectado")
            elif status in CRITICAL_STATUS:
                resultado["erros"].append(f"HD {hd_id} problema crítico: {status}")
            elif status in WARNING_STATUS:
                resultado["avisos"].append(f"HD {hd_id} alerta: {status}")
    except Exception as e:
        resultado["falhou"] = True
        resultado["msg_falha"] = f"Erro: {e}"
    return resultado

def verificar_status_hd_dvrs():
    lista_dvrs = ler_dvrs_txt("dvrs.txt")
    if not lista_dvrs:
        print("Nenhum DVR válido encontrado.")
        return
    while True:
        modo_detalhado = input("Modo detalhado [1] ou Resumo [2]: ").strip() == '1'
        checar_notexist = input("Verificar status 'notexist'? (s/n): ").strip().lower() == 's'
        resultados = [verificar_dvr_hd_status(dvr, checar_notexist, modo_detalhado) for dvr in lista_dvrs]
        print("\n### RELATÓRIO FINAL ###\n")
        for r in resultados:
            if r["falhou"]:
                print(f"{RED}❌ {r['nome']} ({r['ip']}) - {r['msg_falha']}{RESET}")
            elif r["erros"] or r["avisos"]:
                print(f"{YELLOW}{r['nome']} ({r['ip']}){RESET}")
                for erro in r["erros"]:
                    print(f"{RED}{erro}{RESET}")
                for aviso in r["avisos"]:
                    print(f"{YELLOW}{aviso}{RESET}")
        for dvr, resultado in zip(lista_dvrs, resultados):
            if resultado["erros"]:
                if input(f"Reiniciar '{dvr['nome']}'? (s/n): ").strip().lower() == 's':
                    if reiniciar_dvr(dvr):
                        aguardar_online(dvr)
        if input("Nova verificação? (s/n): ").strip().lower() != 's':
            break

# === MENU PRINCIPAL ===
def menu():
    while True:
        print(f"""\n{BOLD}===== MENU PRINCIPAL ====={RESET}
[1] Configurar feriados
[2] Verificar horários
[3] Verificar status dos HDs
[0] Sair
""")
        opcao = input("Escolha uma opção: ").strip()
        if opcao == '1':
            print("Executando opção 1 (configurar feriados)...")  # substitua pela lógica real
        elif opcao == '2':
            print("Executando opção 2 (verificar horários)...")  # substitua pela lógica real
        elif opcao == '3':
            verificar_status_hd_dvrs()
        elif opcao == '0':
            print("Saindo.")
            break
        else:
            print("Opção inválida.")

if _name_ == "_main_":
    menu()