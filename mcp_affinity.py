"""Cliente mínimo do servidor MCP do Affinity (SSE + JSON-RPC).

O Affinity escuta somente IPv6 localhost: http://[::1]:6767/sse
Protocolo MCP: 2025-11-25. Exige leitura do tópico 'preamble'
uma vez por sessão antes de execute_script.
"""
import http.client
import json
import re
import socket
import threading
import time

HOST = "::1"
PORT = 6767
PROTOCOL_VERSION = "2025-11-25"


class AffinityMCPError(RuntimeError):
    pass


class AffinityMCPClient:
    def __init__(self, host=HOST, port=PORT, timeout_s=90):
        self._respostas = {}
        self._parar = False
        self._id = 0
        self._timeout_s = timeout_s

        conexao = http.client.HTTPConnection(host, port, timeout=10)
        try:
            conexao.request("GET", "/sse", headers={"Accept": "text/event-stream"})
            resposta = conexao.getresponse()
        except OSError as erro:
            raise AffinityMCPError(
                "Não foi possível conectar ao Affinity em "
                f"http://[{host}]:{port}/sse. Abra o Affinity com o MCP habilitado. ({erro})"
            )
        if resposta.status != 200:
            raise AffinityMCPError(f"MCP respondeu HTTP {resposta.status} no /sse")

        conexao.sock.settimeout(5)
        acumulado = b""
        inicio = time.time()
        sessao = None
        while time.time() - inicio < 6:
            try:
                parte = conexao.sock.recv(4096)
            except socket.timeout:
                break
            if not parte:
                break
            acumulado += parte
            achado = re.search(r"session_id=([a-f0-9\-]+)", acumulado.decode(errors="ignore"))
            if achado:
                sessao = achado.group(1)
                break
        if not sessao:
            raise AffinityMCPError("MCP não informou session_id")
        self._sessao = sessao
        self._sse = conexao
        self._host = host
        self._port = port

        escuta = threading.Thread(target=self._escutar, daemon=True)
        escuta.start()

        retorno = self.chamar(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                "clientInfo": {"name": "gerador-noticias", "version": "1.0"},
            },
            timeout=15,
        )
        if "error" in retorno:
            raise AffinityMCPError(f"initialize falhou: {retorno['error']}")
        self._enviar({"jsonrpc": "2.0", "method": "notifications/initialized"})
        time.sleep(0.5)
        # Obrigatório uma vez por sessão antes de usar o SDK.
        self.ferramenta("read_sdk_documentation_topic", {"filename": "preamble"})

    def _escutar(self):
        sock = self._sse.sock
        sock.settimeout(1)
        buf = ""
        while not self._parar:
            try:
                parte = sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not parte:
                time.sleep(0.05)
                continue
            buf += parte.decode(errors="ignore").replace("\r\n", "\n")
            while True:
                fim = buf.find("\n\n")
                if fim < 0:
                    break
                bloco, buf = buf[:fim], buf[fim + 2:]
                for item in re.finditer(r"data:\s*(.*)", bloco):
                    carga = item.group(1).strip()
                    if not carga or carga in ("0", "1", "2") or carga.startswith(("heartbeat", "/message")):
                        continue
                    try:
                        objeto = json.loads(carga)
                    except ValueError:
                        continue
                    if isinstance(objeto, dict) and "id" in objeto:
                        self._respostas[objeto["id"]] = objeto

    def _enviar(self, carga):
        conexao = http.client.HTTPConnection(self._host, self._port, timeout=30)
        conexao.request(
            "POST",
            f"/message?session_id={self._sessao}",
            body=json.dumps(carga),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        resposta = conexao.getresponse()
        resposta.read()
        return resposta.status

    def chamar(self, metodo, parametros=None, timeout=None):
        self._id += 1
        meu_id = self._id
        self._enviar({"jsonrpc": "2.0", "id": meu_id, "method": metodo, "params": parametros or {}})
        limite = timeout or self._timeout_s
        inicio = time.time()
        while time.time() - inicio < limite:
            if meu_id in self._respostas:
                return self._respostas.pop(meu_id)
            time.sleep(0.15)
        raise AffinityMCPError(f"Tempo esgotado aguardando '{metodo}'")

    def ferramenta(self, nome, argumentos=None, timeout=None):
        return self.chamar("tools/call", {"name": nome, "arguments": argumentos or {}}, timeout=timeout)

    def executar_js(self, script, timeout=120):
        retorno = self.ferramenta("execute_script", {"script": script}, timeout=timeout)
        try:
            return retorno["result"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise AffinityMCPError(f"Resposta inesperada do execute_script: {retorno}")

    def renderizar_spread(self, uuid_documento, indice=0, timeout=90):
        retorno = self.ferramenta(
            "render_spread",
            {"document_session_uuid": uuid_documento, "spread_index": indice},
            timeout=timeout,
        )
        try:
            return retorno["result"]["content"][0]["data"]
        except (KeyError, IndexError, TypeError):
            raise AffinityMCPError(f"Resposta inesperada do render_spread: {retorno}")

    def fechar(self):
        self._parar = True
