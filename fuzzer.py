import os
import random
import string
import subprocess
import time
import sys
import argparse

# -----------------------------
# ARG PARSE
# -----------------------------
parser = argparse.ArgumentParser(description="Black-box binary fuzzer")
parser.add_argument("-t", "--target", nargs="+", required=True,
                    help="Target command to fuzz (e.g. ./binary or python app.py)")
parser.add_argument("-i", "--iterations", type=int, default=1000,
                    help="Number of fuzzing iterations")

args = parser.parse_args()

TARGET_CMD = args.target
ITERATIONS = args.iterations

MAX_SIZE = 4096
CRASH_LOG = "crashes.log"
SEED = int(time.time())

random.seed(SEED)

# -----------------------------
# FUZZ INPUT GENERATORS
# -----------------------------

def random_bytes():
    size = random.randint(1, MAX_SIZE)
    return os.urandom(size)

def weird_text():
    size = random.randint(1, MAX_SIZE)
    chars = string.printable + "\x00\xff\xfe\x01\x02"
    return "".join(random.choice(chars) for _ in range(size)).encode("utf-8", errors="ignore")

def structured_noise():
    blob = bytearray()
    for _ in range(random.randint(10, 200)):
        choice = random.randint(0, 2)
        if choice == 0:
            blob.extend(os.urandom(random.randint(1, 64)))
        elif choice == 1:
            blob.extend(b"A" * random.randint(1, 64))
        else:
            blob.extend(b"\x00" * random.randint(1, 32))
    return bytes(blob)

def mutate(seed):
    data = bytearray(seed)
    for _ in range(random.randint(1, 50)):
        idx = random.randint(0, len(data) - 1)
        data[idx] ^= random.randint(0, 255)
    return bytes(data)

# -----------------------------
# CORE FUZZ LOOP
# -----------------------------

def run_case(data):
    try:
        p = subprocess.Popen(
            TARGET_CMD,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        out, err = p.communicate(input=data, timeout=2)
        return p.returncode, out, err

    except subprocess.TimeoutExpired:
        p.kill()
        return -1, b"", b"TIMEOUT"

    except Exception as e:
        return -999, b"", str(e).encode()

def log_crash(data, code, err):
    with open(CRASH_LOG, "ab") as f:
        f.write(b"\n==== CRASH ====\n")
        f.write(b"Return code: " + str(code).encode() + b"\n")
        f.write(b"Error:\n" + err + b"\n")
        f.write(b"Input:\n" + repr(data).encode() + b"\n")

# -----------------------------
# MAIN LOOP
# -----------------------------

def main():
    print(f"[+] Starting fuzzer with seed {SEED}")
    print(f"[+] Target: {TARGET_CMD}")
    print(f"[+] Iterations: {ITERATIONS}")

    for i in range(ITERATIONS):
        mode = random.randint(0, 2)

        if mode == 0:
            data = random_bytes()
        elif mode == 1:
            data = weird_text()
        else:
            data = structured_noise()

        if random.random() < 0.3:
            data = mutate(data)

        code, out, err = run_case(data)

        print(f"[{i}] code={code} size={len(data)}")

        if code not in [0, 1]:
            log_crash(data, code, err)

        if b"segfault" in err.lower() or b"panic" in err.lower():
            log_crash(data, code, err)

    print("[+] Done")

if __name__ == "__main__":
    main()
