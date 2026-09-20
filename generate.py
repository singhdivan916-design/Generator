from http.server import BaseHTTPRequestHandler
import json
import os
import sys
import hmac
import hashlib
import base64
import string
import random
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import MajoRLoGinrEq_pb2
import MajoRLoGinrEs_pb2
try:
    import PorTs_pb2
except ImportError:
    PorTs_pb2 = None

PLAY_VER = "1.132.1"
OB_VER = "OB55"
LOGIN_URL = "https://loginbp.ppmainecoonghj.com"

X_GA_SV_STATIC = "1789534056"
X_GA_SV_MODE = "static"

SIGNED_RESPONSE_PREFIX_BYTES = 64
ENABLE_SIGNED_RESPONSE_STRIP = True

HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
KEY = bytes.fromhex(HEX_KEY)

REGISTER_URL = "https://100067.connect.garena.com/api/v2/oauth/guest:register"
TOKEN_URL = "https://100067.connect.garena.com/api/v2/oauth/guest/token:grant"
MAJOR_REGISTER_URL = f"{LOGIN_URL}/MajorRegister"
MAJOR_LOGIN_URL = f"{LOGIN_URL}/MajorLogin"
CHOOSE_REGION_URL = f"{LOGIN_URL}/ChooseRegion"

LANG = "en"

VALID_REGIONS = {"IND", "ID", "VN", "BD", "PK", "TW", "CIS", "BR"}

REGION_LANG = {
    "IND": "hi", "ID": "id", "VN": "vi", "TH": "th",
    "BD": "bn", "PK": "ur", "TW": "zh", "CIS": "ru", "BR": "pt",
}

NICK_BASE = "DIVAN"
PASS_BASE = "DIVAN"

requests.packages.urllib3.disable_warnings()


def current_x_ga_sv():
    if X_GA_SV_MODE == "time":
        return str(int(time.time()))
    return X_GA_SV_STATIC


def game_headers(host, authorization="Bearer"):
    return {
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "X-Ga-Sv": current_x_ga_sv(),
        "Authorization": authorization,
        "X-Ga": "v1 1",
        "ReleaseVersion": OB_VER,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "Connection": "Keep-Alive",
        "Host": host,
    }


def strip_signed_envelope(content, headers):
    if not ENABLE_SIGNED_RESPONSE_STRIP:
        return content
    if headers.get("x-ga-rv") != "1":
        return content
    if len(content) <= SIGNED_RESPONSE_PREFIX_BYTES:
        return content
    return content[SIGNED_RESPONSE_PREFIX_BYTES:]


def looks_like_major_login_res(data):
    if not data or len(data) < 2:
        return False
    try:
        r = MajoRLoGinrEs_pb2.MajorLoginRes()
        r.ParseFromString(data)
        return bool(r.token or r.account_uid or r.url)
    except Exception:
        return False


def try_parse_with_offsets(content, check_fn):
    for off in [0, 64, 32, 16, 8, 128]:
        if off > len(content):
            continue
        if check_fn(content[off:]):
            return content[off:]
    return content


def EnC_Vr(N):
    if N < 0:
        return b""
    out = []
    while True:
        b = N & 0x7F
        N >>= 7
        if N:
            b |= 0x80
        out.append(b)
        if not N:
            return bytes(out)


def CrEaTe_VarianT(field_number, value):
    return EnC_Vr((field_number << 3) | 0) + EnC_Vr(value)


def CrEaTe_LenGTh(field_number, value):
    header = (field_number << 3) | 2
    encoded = value.encode() if isinstance(value, str) else value
    return EnC_Vr(header) + EnC_Vr(len(encoded)) + encoded


def CrEaTe_ProTo(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested = CrEaTe_ProTo(value)
            packet.extend(CrEaTe_LenGTh(field, nested))
        elif isinstance(value, int):
            packet.extend(CrEaTe_VarianT(field, value))
        elif isinstance(value, (str, bytes)):
            packet.extend(CrEaTe_LenGTh(field, value))
    return packet


def E_AEs(pc):
    Z = bytes.fromhex(pc)
    key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(Z, AES.block_size))


def encrypt_api(plain_text):
    plain_text = bytes.fromhex(plain_text)
    key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plain_text, AES.block_size)).hex()


def generate_exponent_number():
    exponent_digits = {
        "6": "⁰", "1": "¹", "7": "★", "3": "³", "4": "⁴",
        "5": "⸙", "8": "☯", "9": "⁷", "0": "᭄", "2": "๛",
    }
    number = random.randint(1, 99999)
    number_str = f"{number:05d}"
    return "".join(exponent_digits[d] for d in number_str)


def generate_random_name():
    return f"{NICK_BASE}{generate_exponent_number()}"


def generate_custom_password():
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choice(chars) for _ in range(6))
    return f"{PASS_BASE}_{suffix}"


def normalize_client_url(url):
    if not url:
        return None
    try:
        u = str(url).strip()
    except Exception:
        return None
    if not u:
        return None
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "https://" + u
    return u.rstrip("/")


def get_client_url_for_region(region):
    r = (region or "").upper()
    if r == "IND":
        return "https://client.ind.freefiremobile.com"
    if r in ("BR", "US", "NA", "SAC"):
        return "https://client.us.freefiremobile.com"
    return "https://clientbp.ggblueshark.com"


def decode_jwt_payload(jwt_token):
    try:
        parts = jwt_token.split(".")
        if len(parts) < 2:
            return {}
        payload_part = parts[1]
        padding = 4 - len(payload_part) % 4
        if padding != 4:
            payload_part += "=" * padding
        decoded = base64.urlsafe_b64decode(payload_part)
        return json.loads(decoded)
    except Exception:
        return {}


def jwt_lock_region(jwt_token):
    data = decode_jwt_payload(jwt_token)
    return data.get("lock_region") or data.get("noti_region")


def guest_register(password):
    payload = {"app_id": 100067, "client_type": 2, "password": password, "source": 2}
    body_json = json.dumps(payload, separators=(",", ":"))
    signature = hmac.new(KEY, body_json.encode(), hashlib.sha256).hexdigest()
    headers = {
        "User-Agent": "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Authorization": f"Signature {signature}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Connection": "Keep-Alive",
        "Host": "100067.connect.garena.com",
    }
    resp = requests.post(REGISTER_URL, headers=headers, data=body_json, timeout=30, verify=False)
    if resp.status_code != 200:
        raise Exception(f"Register failed: HTTP {resp.status_code} — {resp.text[:200]}")
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Register error: {data}")
    return data["data"]["uid"]


def guest_token(uid, password):
    payload = {
        "client_id": 100067,
        "client_secret": HEX_KEY,
        "client_type": 2,
        "password": password,
        "response_type": "token",
        "uid": uid,
    }
    body_json = json.dumps(payload, separators=(",", ":"))
    signature = hmac.new(KEY, body_json.encode(), hashlib.sha256).hexdigest()
    headers = {
        "User-Agent": "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "Authorization": f"Signature {signature}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Connection": "Keep-Alive",
        "Host": "100067.connect.garena.com",
    }
    resp = requests.post(TOKEN_URL, headers=headers, data=body_json, timeout=30, verify=False)
    if resp.status_code != 200:
        raise Exception(f"Token failed: HTTP {resp.status_code} — {resp.text[:200]}")
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"Token error: {data}")
    return data["data"]["access_token"], data["data"]["open_id"]


def major_register(access_token, open_id, name):
    keystream = [
        0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37, 0x30,
        0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37,
        0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31,
        0x37, 0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30,
    ]
    encoded_open_id = ""
    for i, ch in enumerate(open_id):
        encoded_open_id += chr(ord(ch) ^ keystream[i % len(keystream)])
    field14 = encoded_open_id.encode("latin1")

    payload_fields = {
        1: name, 2: access_token, 3: open_id, 5: 102000007,
        6: 4, 7: 1, 13: 1, 14: field14, 15: LANG, 16: 1, 17: 1,
    }
    proto_bytes = CrEaTe_ProTo(payload_fields)
    encrypted_payload = E_AEs(bytes(proto_bytes).hex())

    headers = game_headers("loginbp.ppmainecoonghj.com", authorization="Bearer")
    resp = requests.post(
        MAJOR_REGISTER_URL, headers=headers, data=encrypted_payload,
        verify=False, timeout=30,
    )
    if resp.status_code != 200:
        raise Exception(f"MajorRegister failed: HTTP {resp.status_code} — {resp.content[:200]!r}")
    return True


def encrypt_major_login_proto(open_id, access_token):
    ml = MajoRLoGinrEq_pb2.MajorLogin()
    ml.event_time = str(datetime.now())[:-7]
    ml.game_name = "free fire"
    ml.platform_id = 1
    ml.client_version = PLAY_VER
    ml.system_software = "Android OS 9 / API-28 (PQ3B.190801.10101846/G9650ZHU2ARC6)"
    ml.system_hardware = "Handheld"
    ml.telecom_operator = "Verizon"
    ml.network_type = "WIFI"
    ml.screen_width = 1920
    ml.screen_height = 1080
    ml.screen_dpi = "280"
    ml.processor_details = "ARM64 FP ASIMD AES VMH | 2865 | 4"
    ml.memory = 3003
    ml.gpu_renderer = "Adreno (TM) 640"
    ml.gpu_version = "OpenGL ES 3.1 v1.46"
    ml.unique_device_id = "Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57"
    ml.client_ip = "223.191.51.89"
    ml.language = LANG
    ml.open_id = open_id
    ml.open_id_type = "4"
    ml.device_type = "Handheld"
    ml.memory_available.version = 55
    ml.memory_available.hidden_value = 81
    ml.access_token = access_token
    ml.platform_sdk_id = 1
    ml.network_operator_a = "Verizon"
    ml.network_type_a = "WIFI"
    ml.client_using_version = "7428b253defc164018c604a1ebbfebdf"
    ml.external_storage_total = 36235
    ml.external_storage_available = 31335
    ml.internal_storage_total = 2519
    ml.internal_storage_available = 703
    ml.game_disk_storage_available = 25010
    ml.game_disk_storage_total = 26628
    ml.external_sdcard_avail_storage = 32992
    ml.external_sdcard_total_storage = 36235
    ml.login_by = 3
    ml.library_path = "/data/app/com.dts.freefireth-YPKM8jHEwAJlhpmhDhv5MQ==/lib/arm64"
    ml.reg_avatar = 1
    ml.library_token = "5b892aaabd688e571f688053118a162b|/data/app/com.dts.freefireth-YPKM8jHEwAJlhpmhDhv5MQ==/base.apk"
    ml.channel_type = 3
    ml.cpu_type = 2
    ml.cpu_architecture = "64"
    ml.client_version_code = "2019118695"
    ml.graphics_api = "OpenGLES2"
    ml.supported_astc_bitset = 16383
    ml.login_open_id_type = 4
    ml.analytics_detail = b"FwQVTgUPX1UaUllDDwcWCRBpWA0FUgsvA1snWlBaO1kFYg=="
    ml.loading_time = 13564
    ml.release_channel = "android"
    ml.extra_info = "KqsHTymw5/5GB23YGniUYN2/q47GATrq7eFeRatf0NkwLKEMQ0PK5BKEk72dPflAxUlEBir6Vtey83XqF593qsl8hwY="
    ml.android_engine_init_flag = 110009
    ml.if_push = 1
    ml.is_vpn = 1
    ml.origin_platform_type = "4"
    ml.primary_platform_type = "4"
    serialized = ml.SerializeToString()
    key_b = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv_b = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    cipher = AES.new(key_b, AES.MODE_CBC, iv_b)
    return cipher.encrypt(pad(serialized, AES.block_size))


def major_login(access_token, open_id):
    encrypted_payload = encrypt_major_login_proto(open_id, access_token)
    headers = game_headers("loginbp.ppmainecoonghj.com", authorization="Bearer")
    resp = requests.post(
        MAJOR_LOGIN_URL, headers=headers, data=encrypted_payload,
        verify=False, timeout=30,
    )
    if resp.status_code != 200:
        raise Exception(f"MajorLogin failed: HTTP {resp.status_code} — {resp.content[:200]!r}")

    body = strip_signed_envelope(resp.content, resp.headers)
    body = try_parse_with_offsets(body, looks_like_major_login_res)
    if not looks_like_major_login_res(body):
        raise Exception("MajorLogin: body not parseable")

    res = MajoRLoGinrEs_pb2.MajorLoginRes()
    res.ParseFromString(body)
    return res


def chooseregion(jwt_token, region_code):
    fields = {1: region_code}
    proto_data = CrEaTe_ProTo(fields)
    encrypted_data = encrypt_api(proto_data.hex())
    payload = bytes.fromhex(encrypted_data)
    headers = game_headers("loginbp.ppmainecoonghj.com", authorization=f"Bearer {jwt_token}")
    try:
        resp = requests.post(
            CHOOSE_REGION_URL, data=payload, headers=headers,
            verify=False, timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def build_get_login_data_payload(open_id, access_token, jwt_token, region):
    token_payload_base64 = jwt_token.split(".")[1]
    token_payload_base64 += "=" * ((4 - len(token_payload_base64) % 4) % 4)
    decoded_payload = json.loads(base64.urlsafe_b64decode(token_payload_base64).decode("utf-8"))
    signature_md5 = decoded_payload.get("signature_md5", "")
    if not signature_md5:
        raise ValueError("No signature_md5 in JWT")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    template_hex = (
        "1a13323032362d30362d32392031333a34323a3531220966726565206669726528013a07322e3132362e36423a416e64726f6964204f532039202f204150492d32382028505133422e3139303830312e30333235303930332f47393635305a48553241524336294a0848616e6468656c6452074d6f62696e696c5a045749464960c00c68840772033234307a287838362d3634205353453320535345342e3120535345342e3220415658207c2032383635207c20368001c32e8a010f416472656e6f2028544d29203634309201104f70656e474c20455320332e312076319a012b476f6f676c657c38656162393736322d633065612d343064382d623634662d663135326263313265303362a2010d3139372e3230322e35352e3330aa01026172b201206465633265383233613766303737306338383765663163613464303131633063ba010134c2010848616e6468656c64ca01115869616f6d69203233303446504e364447d201024d45ea014066383830663031383933666337383264663063393538366562656232326134633663393464613632636334353365303166333465363538613830393561663730f00101ca02074d6f62696e696cd2020457494649ca03203161633462383065636630343738613434323033626638666163363132306635e003c88a03e803c1f002f003d713f803de058004d0ba01880484d0019004ff81039804c88a03c80403d204402f646174612f6170702f636f6d2e6474732e66726565666972656d61782d716a7a583456364a6d654d744d656865766f6c6856513d3d2f6c69622f61726d3634e00402ea046064353038353336623261336331366266326265626264323432333365393239337c2f646174612f6170702f636f6d2e6474732e66726565666972656d61782d716a7a583456364a6d654d744d656865766f6c6856513d3d2f626173652e61706bf00402f804028a050236349a050a32303139313138303435a80503b205094f70656e474c455333b805ff1fc00504e005a73dea050b616e64726f69645f6d6178f2055c4b717348542b64772f4f504d523676524b7352545a55486a727272635779346333477974374b3649794157586665307238513943696261414231364b3538674244514d57314b6939626372382b78696f4b3278776453396a7330413df805e7e4068206257b226375725f72617465223a6e756c6c2c22737570706f72745f65746332223a747275657d8806019006019a060134a2060134b20600"
    )
    payload = bytes.fromhex(template_hex)
    payload = payload.replace(b"2026-06-29 13:42:51", now.encode())
    payload = payload.replace(
        b"f880f01893fc782df0c9586ebeb22a4c6c94da62cc453e01f34e658a8095af70",
        access_token.encode("UTF-8"),
    )
    payload = payload.replace(b"dec2e823a7f0770c887ef1ca4d011c0c", open_id.encode("UTF-8"))
    payload = payload.replace(
        b"7428b253defc164018c604a1ebbfebdf", signature_md5.encode("UTF-8")
    )

    region_upper = (region or "").upper()
    lang_code = REGION_LANG.get(region_upper, "en")
    region_code_for_template = "RU" if region_upper == "CIS" else region_upper

    old_lang = b"\xaa\x01\x02ar"
    new_lang = b"\xaa\x01\x02" + lang_code.encode("utf-8")
    payload = payload.replace(old_lang, new_lang)

    old_region = b"\xd2\x01\x02ME"
    new_region = (
        b"\xd2\x01"
        + bytes([len(region_code_for_template)])
        + region_code_for_template.encode("utf-8")
    )
    payload = payload.replace(old_region, new_region)

    key_b = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv_b = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    cipher = AES.new(key_b, AES.MODE_CBC, iv_b)
    return cipher.encrypt(pad(payload, AES.block_size))


def get_login_data(base_url, encrypted_payload, jwt_token):
    url = f"{base_url}/GetLoginData"
    host = base_url.replace("https://", "").replace("http://", "").rstrip("/")
    headers = game_headers(host, authorization=f"Bearer {jwt_token}")
    resp = requests.post(
        url, headers=headers, data=encrypted_payload,
        verify=False, timeout=30,
    )
    return resp.status_code == 200


def create_account(region):
    global LANG
    region = region.upper()
    LANG = REGION_LANG.get(region, "en")
    target_region_code = "RU" if region == "CIS" else region

    password = generate_custom_password()

    uid = guest_register(password)
    access_token, open_id = guest_token(uid, password)

    name = generate_random_name()
    major_register(access_token, open_id, name)

    major_res = major_login(access_token, open_id)
    jwt_token = major_res.token
    account_id = major_res.account_uid
    url_base = normalize_client_url(major_res.url)

    lock_region_1 = jwt_lock_region(jwt_token)
    need_choose = False
    if lock_region_1:
        if str(lock_region_1).upper() != target_region_code:
            need_choose = True
    else:
        need_choose = True

    if need_choose:
        try:
            chooseregion(jwt_token, target_region_code)
        except Exception:
            pass
        try:
            major_res2 = major_login(access_token, open_id)
            if major_res2 and major_res2.token:
                jwt_token = major_res2.token
                if major_res2.account_uid:
                    account_id = major_res2.account_uid
                new_url = normalize_client_url(major_res2.url)
                if new_url:
                    url_base = new_url
        except Exception:
            pass

    if not url_base:
        url_base = get_client_url_for_region(region)

    activation = False
    try:
        payload = build_get_login_data_payload(open_id, access_token, jwt_token, region)
        activation = get_login_data(url_base, payload, jwt_token)
    except Exception:
        activation = False

    return {
        "region": region,
        "uid": uid,
        "password": password,
        "name": name,
        "account_id": account_id,
        "jwt_token": jwt_token,
        "access_token": access_token,
        "open_id": open_id,
        "activation": activation,
    }


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        region = (params.get("region", [""])[0] or "").strip().upper()
        self._handle(region)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            data = {}
        region = str(data.get("region", "")).strip().upper()
        self._handle(region)

    def _handle(self, region):
        if not region:
            self._send_json(400, {
                "success": False,
                "error": "Missing 'region' parameter",
                "valid_regions": sorted(VALID_REGIONS),
            })
            return
        if region not in VALID_REGIONS:
            self._send_json(400, {
                "success": False,
                "error": f"Invalid region '{region}'",
                "valid_regions": sorted(VALID_REGIONS),
            })
            return
        try:
            acc = create_account(region)
            self._send_json(200, {"success": True, **acc})
        except Exception as e:
            self._send_json(500, {"success": False, "error": str(e)})
