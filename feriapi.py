import requests
from requests.auth import HTTPDigestAuth
import os

def ler_dvr_txt(arquivo):
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
                elif len(partes) == 1:
                    ip = partes[0].strip()
                    username = "admin"  # padrão ou vazio
                    password = ""       # vazio
                    print(f"[!] Aviso: '{linha}' sem usuário/senha, usando padrão.")
                else:
                    print(f"[!] Linha inválida (esperado 1 ou 3 campos): {linha}")
                    continue

                dvrs.append({
                    "ip": ip.strip(),
                    "username": username.strip(),
                    "password": password.strip()
                })
            except Exception as e:
                print(f"[!] Erro ao processar linha: {linha} - {e}")
    return dvrs


def gerar_xml_feriados(arquivo_txt):
    feriados = []
    with open(arquivo_txt, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith('#'):
                continue
            partes = linha.split(',')
            if len(partes) != 3:
                print(f"[!] Linha inválida (esperado 3 campos): {linha}")
                continue
            nome, mes, dia = partes
            feriados.append({
                "nome": nome.strip(),
                "mes": int(mes.strip()),
                "dia": int(dia.strip())
            })

    xml = ['''<?xml version="1.0" encoding="UTF-8"?>
<HolidayList version="1.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">''']

    for i, feriado in enumerate(feriados, start=1):
        bloco = f'''
  <holiday>
    <id>{i}</id>
    <enabled>true</enabled>
    <holidayName>{feriado["nome"]}</holidayName>
    <holidayMode>month</holidayMode>
    <holidayMonth>
      <startMonth>
        <monthOfYear>{feriado["mes"]}</monthOfYear>
        <dayOfMonth>{feriado["dia"]}</dayOfMonth>
      </startMonth>
      <endMonth>
        <monthOfYear>{feriado["mes"]}</monthOfYear>
        <dayOfMonth>{feriado["dia"]}</dayOfMonth>
      </endMonth>
    </holidayMonth>
  </holiday>'''
        xml.append(bloco)

    xml.append('</HolidayList>')
    return '\n'.join(xml)

def configurar_feriados(dvr, xml_payload):
    url = f"http://{dvr['ip']}/ISAPI/System/holidays"
    headers = {'Content-Type': 'application/xml'}

    try:
        response = requests.put(
            url,
            data=xml_payload,
            auth=HTTPDigestAuth(dvr['username'], dvr['password']),
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            print(f"[✓] Sucesso: {dvr['ip']} configurado com feriados.")
        else:
            print(f"[!] Falha ({response.status_code}) em {dvr['ip']}: {response.text}")

    except Exception as e:
        print(f"[X] Erro em {dvr['ip']}: {e}")

if __name__ == "__main__":
    arquivo_dvrs = "dvr.txt"       # arquivo com IPs e credenciais dos DVRs
    arquivo_feriados = "feriados.txt"  # arquivo com os feriados para gerar XML

    dvrs = ler_dvr_txt(arquivo_dvrs)
    xml_feriados = gerar_xml_feriados(arquivo_feriados)

    for dvr in dvrs:
        configurar_feriados(dvr, xml_feriados)
