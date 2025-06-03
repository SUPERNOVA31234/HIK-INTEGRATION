import os
import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET
import time

RED = "\033[31m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# === Constantes XML e status ===
NS = {'hik': 'http://www.hikvision.com/ver20/XMLSchema'}
CRITICAL_STATUS = {'error', 'unformatted', 'uninitialized', 'abnormal', 'degraded'}
WARNING_STATUS = {'full', 'formatting'}

# === Lê os DVRs do arquivo txt ===
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



def verificar_dvrs(modo_detalhado, verificar_notexist):
    print("\n🔍 Iniciando verificação...\n")
    
    # Lista simulada dos DVRs (id, endereço)
    dvrs = [
        ("9999", "corseg.ddns.net:3000"),
        ("0001", "corseg0001.ddns.net:3003")
    ]
    
    for id_dvr, endereco in dvrs:
        print(f"🔍 {id_dvr} ({endereco}) - Verificando...")
        
        # Simulando verificação de HDs
        # Aqui você usaria seu código real de verificação
        
        # Se modo detalhado:
        if modo_detalhado:
            print("✅ HD 1 está OK.")
            # Se tiver mais HDs, lista aqui...
            print("✅ Todos os HDs estão OK.\n")
        else:
            # Resumo final simples
            print(f"{id_dvr}: HD OK\n")

def main():
    while True:
        print("=== MENU PRINCIPAL ===")
        print("1 - Verificar status dos HDs dos DVRs")
        print("2 - Aplicar XML de feriados nos DVRs")
        print("3 - Configurar horário dos DVRs")
        print("4 - Sair")
        opcao = input("\nEscolha uma opção: ")

        if opcao == "1":
            modo = input("Escolha o modo: [1] Detalhado | [2] Resumo Final: ")
            verificar_notexist = input("Deseja que o script verifique status 'notexist'? (s/n): ").lower() == 's'
            
            verificar_dvrs(modo_detalhado=(modo == "1"), verificar_notexist=verificar_notexist)
            
        elif opcao == "2":
            print("Aplicando XML de feriados nos DVRs...")
            # função aplicar_xml_feriados()
        elif opcao == "3":
            print("Configurando horário dos DVRs...")
            # função configurar_horario()
        elif opcao == "4":
            print("Saindo...")
            break
        else:
            print("Opção inválida, tente novamente.\n")

if __name__ == "__main__":
    main()


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

# === Execução principal ===
if __name__ == "__main__":
    lista_dvrs = ler_dvrs_txt("dvrs.txt")
    if not lista_dvrs:
        print("Nenhum DVR válido encontrado.")
    else:
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

            print("""########################
                     RELATÓRIO FINAL DE ERROS
                     ########################""")
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

            # Pergunta um a um se quer reiniciar os DVRs com problema crítico (erros em HD)
            for dvr, resultado in zip(lista_dvrs, resultados):
                if resultado["erros"]:  # Só DVRs com erros críticos em HD
                    while True:
                        resposta = input(f"\nDeseja reiniciar o DVR '{dvr['nome']}' com problema crítico? (s/n): ").strip().lower()
                        if resposta in ('s', 'n'):
                            break
                        print("Resposta inválida. Digite 's' para sim ou 'n' para não.")
                    if resposta == 's':
                        if reiniciar_dvr(dvr):
                            aguardar_online(dvr)


            # Pergunta para repetir ou sair
            while True:
                repetir = input("\nDeseja realizar uma nova verificação? (s/n): ").strip().lower()
                if repetir == 's':
                    print("\n🔄 Reiniciando a verificação...\n")
                    break
                elif repetir == 'n':
                    print("Encerrando o script")
                    exit()
                else:
                    print("Opção inválida. Digite 's' para sim ou 'n' para não.")

