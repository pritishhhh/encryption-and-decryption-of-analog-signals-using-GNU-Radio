"""
Embedded Python Blocks:

Each time this file is saved, GRC will instantiate the first class it finds
to get ports and parameters of your block. The arguments to __init__  will
be the parameters. All of them are required to have default values!
"""

import numpy as np
from gnuradio import gr
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import os

class blk(gr.sync_block):
    """
    RSA + AES ENCRYPT + DECRYPT IN ONE BLOCK
    ─────────────────────────────────────────
    RSA encrypts the AES session key (key encapsulation)
    AES encrypts the actual signal data
    Input  0 → original complex signal
    Output 0 → original signal        (QT GUI 1)
    Output 1 → encrypted visual       (QT GUI 2)
    Output 2 → decrypted signal       (QT GUI 3)
    """

    def __init__(self):
        gr.sync_block.__init__(
            self,
            name='RSA: Encrypt + Decrypt',
            in_sig=[(np.complex64, 256)],
            out_sig=[
                (np.complex64, 256),   # output 0 → original
                (np.complex64, 256),   # output 1 → encrypted visual
                (np.complex64, 256)    # output 2 → decrypted
            ]
        )

        # ── Base path ──
        base = "D:/GNU Radio/rsa"
        os.makedirs(base, exist_ok=True)

        # ── Generate RSA 2048 bit key pair ──
        print(f"[RSA] Generating 2048 bit key pair...")
        rsa_key = RSA.generate(2048)

        # ── Save keys for reference ──
        with open(f"{base}/private.pem", "wb") as f:
            f.write(rsa_key.export_key())
        with open(f"{base}/public.pem", "wb") as f:
            f.write(rsa_key.publickey().export_key())

        # ── Store RSA cipher objects ──
        self.rsa_encrypt = PKCS1_OAEP.new(rsa_key.publickey())
        self.rsa_decrypt = PKCS1_OAEP.new(rsa_key)

        self.chunk_count = 0
        self.success     = 0

        print(f"[RSA] Key pair generated and saved to {base}")
        print(f"[RSA] Ready.")

    def work(self, input_items, output_items):
        for i in range(len(input_items[0])):

            # ── Step 1: Get original signal ──
            vector    = input_items[0][i].copy()
            raw_bytes = vector.astype(np.complex64).tobytes()  # 2048 bytes

            try:
                # ── Step 2: Generate fresh AES session key and IV ──
                aes_key = get_random_bytes(32)   # AES-256 session key
                iv      = get_random_bytes(16)

                # ── Step 3: RSA encrypt the AES session key ──
                encrypted_aes_key = self.rsa_encrypt.encrypt(aes_key)

                # ── Step 4: AES encrypt the signal using session key ──
                aes_enc   = AES.new(aes_key, AES.MODE_CBC, iv=iv)
                padded    = pad(raw_bytes, AES.block_size)
                encrypted = aes_enc.encrypt(padded)

                # ── Step 5: RSA decrypt the AES session key ──
                decrypted_aes_key = self.rsa_decrypt.decrypt(encrypted_aes_key)

                # ── Step 6: AES decrypt the signal ──
                aes_dec          = AES.new(decrypted_aes_key, AES.MODE_CBC, iv=iv)
                decrypted_padded = aes_dec.decrypt(encrypted)
                decrypted_bytes  = unpad(decrypted_padded, AES.block_size)
                recovered        = np.frombuffer(decrypted_bytes, dtype=np.complex64).copy()

                # ── Step 7: Output 0 → original signal ──
                output_items[0][i] = vector

                # ── Step 8: Output 1 → encrypted visual ──
                enc_int  = np.frombuffer(encrypted[:2048], dtype=np.int8).astype(np.float32)
                enc_real = enc_int[0::2][:256] / 128.0
                enc_imag = enc_int[1::2][:256] / 128.0
                enc_vis  = np.nan_to_num(
                               (enc_real + 1j * enc_imag).astype(np.complex64),
                               nan=0.0
                           )
                output_items[1][i] = enc_vis

                # ── Step 9: Output 2 → decrypted signal ──
                if len(recovered) == 256:
                    output_items[2][i] = recovered
                    self.success += 1
                    print(f"[RSA] Chunk {self.chunk_count:04d} | "
                          f"AES key RSA encrypted: {len(encrypted_aes_key)}B | "
                          f"Signal AES encrypted: {len(encrypted)}B | "
                          f"Decrypted OK | "
                          f"I[0]: {recovered[0].real:.4f} | "
                          f"Q[0]: {recovered[0].imag:.4f} | "
                          f"Total OK: {self.success}")
                else:
                    raise ValueError(f"Expected 256 got {len(recovered)}")

            except Exception as e:
                print(f"[RSA] Chunk {self.chunk_count:04d} | Error: {e}")
                output_items[0][i] = vector
                output_items[1][i] = np.zeros(256, dtype=np.complex64)
                output_items[2][i] = np.zeros(256, dtype=np.complex64)

            self.chunk_count += 1

        return len(input_items[0])