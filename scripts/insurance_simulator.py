"""本地国家医保第三方模拟器（明文协议，仅用于开发/联调）。

启动：
    python scripts/insurance_simulator.py --port 9099

端点：
    POST /success
    POST /business-error
    POST /malformed
    POST /timeout
"""
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REQUIRED = (
    "infno", "msgid", "mdtrtarea_admvs", "insuplc_admdvs",
    "recer_sys_code", "infver", "opter_no", "fixmedins_code", "input",
)


class Handler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, _fmt, *_args):
        return

    def _send(self, status, payload, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send(400, {"error": "invalid json"})
            return
        Handler.requests.append(envelope)
        mode = self.path.strip("/").split("?")[0]
        if mode == "timeout":
            time.sleep(20)
            self._send(200, {"infcode": 0, "output": {}})
            return
        if mode == "malformed":
            self._send(200, b"<html>not json</html>", "text/html")
            return
        if mode == "business-error":
            self._send(200, {"infcode": 1, "infmsg": "模拟医保业务失败"})
            return
        missing = [key for key in REQUIRED if not envelope.get(key)]
        if missing:
            self._send(200, {"infcode": 99, "infmsg": f"缺少字段: {','.join(missing)}"})
            return
        infno = envelope["infno"]
        data = envelope.get("input", {}).get("data", {})
        output = {}
        if infno in ("2206", "2207"):
            total = float(data.get("medfee_sumamt") or 0)
            fund = round(total * 0.7, 2)
            output = {
                "setlinfo": {
                    "setl_id": f"SIM{int(time.time() * 1000)}",
                    "medfee_sumamt": total,
                    "fund_pay_sumamt": fund,
                    "psn_pay": round(total - fund, 2),
                    "acct_pay": 0,
                    "cash_payamt": round(total - fund, 2),
                    "med_type": data.get("med_type", "11"),
                },
                "setldetail": [{"fund_pay_type": "310", "fund_pay_sumamt": fund}],
            }
        elif infno == "2208":
            output = {"setlinfo": {"setl_id": data.get("setl_id", "SIM-CANCEL")}}
        else:
            output = {"data": data}
        self._send(200, {"infcode": 0, "infmsg": "success", "output": output})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9099)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"insurance simulator: http://{args.host}:{args.port}/success")
    server.serve_forever()


if __name__ == "__main__":
    main()
