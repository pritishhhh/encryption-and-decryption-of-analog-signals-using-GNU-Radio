"""
Embedded Python Blocks:

Each time this file is saved, GRC will instantiate the first class it finds
to get ports and parameters of your block. The arguments to __init__  will
be the parameters. All of them are required to have default values!
"""

import numpy as np
from gnuradio import gr
from Crypto.Cipher import DES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import os

class blk(gr.sync_block):
    """
    DES ENCRYPT + DECRYPT IN ONE BLOCK
    ────────────────────────────────────
    Input  0 → original complex signal
    Output 0 → original signal        (QT GUI 1)
    Output 1 → encrypted visual       (QT GUI 2)
    Output 2 → decrypted signal       (QT GUI 3)
    """

    def __init__(self):
        gr.sync_block.__init__(
            self,
            name='DES: Encrypt + Decrypt',
            in_sig=[(np.complex64, 256)],
            out_sig=[
                (np.complex64, 256),   # output 0 → original
                (np.complex64, 256),   # output 1 → encrypted visual
                (np.complex64, 256)    # output 2 → decrypted
            ]
        )

        # ── Base path ──
        base = "D:/GNU Radio/des"
        os.makedirs(base, exist_ok=True)

        # ── Generate DES key ──
        # DES uses 8 bytes (64 bits) key
        self.key = get_random_bytes(8)

        # ── Save key to file for reference ──
        with open(f"{base}/des_key.bin", "wb") as f:
            f.write(self.key)

        self.chunk_count = 0
        self.success     = 0

        print(f"[DES] Key   : {self.key.hex()}")
        print(f"[DES] Ready.")

    def work(self, input_items, output_items):
        for i in range(len(input_items[0])):

            # ── Step 1: Get original signal ──
            vector    = input_items[0][i].copy()
            raw_bytes = vector.astype(np.complex64).tobytes()  # 2048 bytes

            # ── Step 2: Generate IV ──
            # DES IV is 8 bytes (not 16 like AES)
            iv = get_random_bytes(8)

            try:
                # ── Step 3: ENCRYPT ──
                cipher_enc = DES.new(self.key, DES.MODE_CBC, iv=iv)
                padded     = pad(raw_bytes, DES.block_size)
                encrypted  = cipher_enc.encrypt(padded)

                # ── Step 4: DECRYPT immediately using same IV ──
                cipher_dec       = DES.new(self.key, DES.MODE_CBC, iv=iv)
                decrypted_padded = cipher_dec.decrypt(encrypted)
                decrypted_bytes  = unpad(decrypted_padded, DES.block_size)
                recovered        = np.frombuffer(decrypted_bytes, dtype=np.complex64).copy()

                # ── Step 5: Output 0 → original signal ──
                output_items[0][i] = vector

                # ── Step 6: Output 1 → encrypted visual ──
                enc_int  = np.frombuffer(encrypted[:2048], dtype=np.int8).astype(np.float32)
                enc_real = enc_int[0::2][:256] / 128.0
                enc_imag = enc_int[1::2][:256] / 128.0
                enc_vis  = np.nan_to_num(
                               (enc_real + 1j * enc_imag).astype(np.complex64),
                               nan=0.0
                           )
                output_items[1][i] = enc_vis

                # ── Step 7: Output 2 → decrypted signal ──
                if len(recovered) == 256:
                    output_items[2][i] = recovered
                    self.success += 1
                    print(f"[DES] Chunk {self.chunk_count:04d} | "
                          f"Encrypted: {len(encrypted)}B | "
                          f"Decrypted OK | "
                          f"I[0]: {recovered[0].real:.4f} | "
                          f"Q[0]: {recovered[0].imag:.4f} | "
                          f"Total OK: {self.success}")
                else:
                    raise ValueError(f"Expected 256 got {len(recovered)}")

            except Exception as e:
                print(f"[DES] Chunk {self.chunk_count:04d} | Error: {e}")
                output_items[0][i] = vector
                output_items[1][i] = np.zeros(256, dtype=np.complex64)
                output_items[2][i] = np.zeros(256, dtype=np.complex64)

            self.chunk_count += 1

        return len(input_items[0])