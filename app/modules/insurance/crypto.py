"""国密算法封装：SM2 签名/验签（SM3 摘要）、SM4-ECB 加解密（PKCS7 填充）、SM3 摘要。"""
import base64

from gmssl import func, sm2, sm3, sm4

from . import demo_keys


def sm3_hex(data: bytes) -> str:
    """SM3 摘要（十六进制）。CA 签章内容摘要等复用。"""
    return sm3.sm3_hash(func.bytes_to_list(data))


def _pkcs7_pad(data: bytes, block: int = 16) -> bytes:
    pad_len = block - (len(data) % block)
    return data + bytes([pad_len]) * pad_len


def _pkcs7_unpad(data: bytes) -> bytes:
    pad_len = data[-1]
    if pad_len <= 0 or pad_len > 16:
        raise ValueError("SM4 解密填充非法")
    return data[:-pad_len]


def sm4_encrypt(plaintext: bytes, key_hex: str = demo_keys.SM4_KEY) -> str:
    """SM4-ECB 加密（PKCS7 填充），返回 Base64。"""
    crypt = sm4.CryptSM4()
    crypt.set_key(bytes.fromhex(key_hex), sm4.SM4_ENCRYPT)
    return base64.b64encode(crypt.crypt_ecb(_pkcs7_pad(plaintext))).decode()


def sm4_decrypt(b64: str, key_hex: str = demo_keys.SM4_KEY) -> bytes:
    """SM4-ECB 解密（去 PKCS7 填充）。"""
    crypt = sm4.CryptSM4()
    crypt.set_key(bytes.fromhex(key_hex), sm4.SM4_DECRYPT)
    return _pkcs7_unpad(crypt.crypt_ecb(base64.b64decode(b64)))


def sm2_sign(data: bytes, private_hex: str, public_hex: str) -> str:
    """SM2 签名（内部用 SM3 摘要），返回十六进制签名串。"""
    signer = sm2.CryptSM2(private_key=private_hex, public_key=public_hex)
    random_hex = func.random_hex(signer.para_len)
    return signer.sign_with_sm3(data, random_hex)


def sm2_verify(signature: str, data: bytes, public_hex: str) -> bool:
    """SM2 验签（SM3 摘要）。"""
    verifier = sm2.CryptSM2(private_key="00", public_key=public_hex)
    return verifier.verify_with_sm3(signature, data)
